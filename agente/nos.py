"""Nós do grafo do agente (cada caixa do desenho de arquitetura é uma função daqui).

orquestrador → (ferramentas ⇄ orquestrador) → coletar → redator → revisor → montar_saida

- orquestrador: o Gemini com as ferramentas; decide quais chamar e com quais argumentos.
- coletar: copia os dados devolvidos pelas ferramentas (artifacts) para o estado.
- redator: escreve a resposta (analisar | recomendar) a partir do estado, citando achados e Reels por id.
- revisor: confere por código que tudo o que foi citado veio das ferramentas; se não, pede nova redação (1×).
- montar_saida: monta a Saida com os dados do estado, nunca com números do texto do LLM.
"""

import os
import re
from functools import cache
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from . import dados
from .contrato import Entrada, Saida
from .ferramentas import FERRAMENTAS, buscar_referencias, id_achado
from .persona import PERSONA, REGRAS_DADOS

# flash-lite: ~500 requisições/dia no plano grátis; o gemini-3.5-flash tem só 20/dia, pouco para 4 a 7
# chamadas por execução.
MODELO = os.environ.get("AGENTE_MODELO", "gemini-3.5-flash-lite")
MAX_CHAMADAS = 5
MAX_REDACOES = 2
EXEMPLOS_ACHADOS = 4  # achados que aparecem mais no top com exemplos buscados por código
EXEMPLOS_POR_ACHADO = 2
PIOR = ["insuficiente", "fragil", "robusto"]


class Redacao(BaseModel):
    explanation: str = Field(description="a resposta ao usuário, em português, em markdown simples")
    achados_citados: list[str] = Field(description="ids curtos (A1, A2...) de todos os achados usados")
    achados_principais: list[str] = Field(description="1 a 3 ids, entre os citados, que sustentam a conclusão")
    referencias_citadas: list[str] = Field(description="shortCodes dos Reels usados como referência")
    perfis_citados: list[str] = Field(default_factory=list,
                                      description="perfis da lista PERFIS EM DESTAQUE recomendados, sem @")


class Estado(TypedDict, total=False):
    run_id: str
    entrada: Entrada
    messages: Annotated[list[AnyMessage], add_messages]
    achados: dict[str, dict]
    referencias: dict[str, dict]
    perfis: dict[str, dict]
    exemplos: dict[str, list[str]]
    redacao: Redacao | None
    problemas: list[str]
    redacoes: int
    tokens: int
    saida: Saida


@cache
def llm() -> ChatGoogleGenerativeAI:
    # Sem temperature: os modelos Gemini 3.5 usam amostragem fixa e ignoram o parâmetro.
    load_dotenv(dados.RAIZ / ".env")
    return ChatGoogleGenerativeAI(model=MODELO, max_retries=4, google_api_key=os.environ["GEMINI_API_KEY"])


def _tokens(msg) -> int:
    return (getattr(msg, "usage_metadata", None) or {}).get("total_tokens", 0)


def _recorte(e: Entrada) -> str:
    partes = [f"segmento {e.segment}" if e.segment else ""]
    if e.filters:
        partes += [f"perfis {'/'.join(e.filters.faixa)}" if e.filters.faixa else "",
                   f"desde {e.filters.periodo_inicio}" if e.filters.periodo_inicio else "",
                   f"até {e.filters.periodo_fim}" if e.filters.periodo_fim else ""]
    return ", ".join(p for p in partes if p) or "amostra inteira"


def _chamadas(estado: Estado) -> int:
    return sum(len(m.tool_calls) for m in estado["messages"] if isinstance(m, AIMessage))


# ---------------------------------------------------------------- orquestrador

PROMPT_ORQUESTRADOR = """Você orquestra um agente que analisa Reels de alto engajamento para micro e pequenos
empreendedores (MPEs) e apoia a @impulsostone. Nesta etapa você só JUNTA DADOS com as ferramentas; outra etapa
redige a resposta.

Pedido: modo={modo}; pergunta="{query}"; recorte: {recorte}.

Como trabalhar:
1. Chame consultar_caracteristicas com os campos ligados à pergunta (ou sem campos, se ela for ampla).
2. Se o recorte tiver poucos Reels (achados "insuficiente"), consulte também a amostra inteira
   (ignorar_recorte=true) para comparar.
3. Chame buscar_referencias para as 1 a 3 características mais relevantes e robustas, para ter Reels reais
   que as exemplifiquem.
4. No modo recomendar, ou se a pergunta for sobre criadores, chame perfis_em_destaque.
Pode chamar várias ferramentas de uma vez. No máximo {maximo} chamadas no total (já usou {usadas}).
Quando tiver dados suficientes, responda só "pronto", sem chamar ferramentas."""


def orquestrador(estado: Estado) -> dict:
    e = estado["entrada"]
    prompt = PROMPT_ORQUESTRADOR.format(modo=e.mode, query=e.query, recorte=_recorte(e), maximo=MAX_CHAMADAS,
                                        usadas=_chamadas(estado))
    resposta = llm().bind_tools(FERRAMENTAS).invoke([SystemMessage(prompt), *estado["messages"]])
    return {"messages": [resposta], "tokens": estado.get("tokens", 0) + _tokens(resposta)}


def pediu_ferramenta(estado: Estado) -> str:
    ultima = estado["messages"][-1]
    if isinstance(ultima, AIMessage) and ultima.tool_calls and _chamadas(estado) <= MAX_CHAMADAS:
        return "ferramentas"
    return "coletar"


def coletar(estado: Estado) -> dict:
    achados, referencias, perfis = {}, {}, {}
    for m in estado["messages"]:
        if not isinstance(m, ToolMessage) or not m.artifact:
            continue
        if m.name == "consultar_caracteristicas":
            achados.update({id_achado(a): a for a in m.artifact})
        elif m.name == "buscar_referencias":
            referencias.update({r["shortCode"]: r for r in m.artifact})
        elif m.name == "perfis_em_destaque":
            perfis.update({p["perfil"]: p for p in m.artifact})
    # Com recorte, junta a amostra inteira dos mesmos campos: o redator precisa dela quando o recorte tem
    # poucos Reels, e isso não deve depender de o LLM lembrar de pedir.
    com_global = {a["campo"] for a in achados.values() if a["recorte"] is None}
    faltam = sorted({a["campo"] for a in achados.values()} - com_global)
    if faltam:
        achados.update({id_achado(a): a for a in dados.achados(faltam)})
    # Os achados robustos da amostra inteira entram sempre: são a evidência mais forte da base.
    achados.update({id_achado(a): a for a in dados.achados() if a["robustez"] == "robusto"})
    # Exemplos por achado, buscados por código: o vínculo "este Reel exemplifica este achado" vem da base,
    # não da escolha do redator.
    exemplos = {}
    e = estado["entrada"]
    recorte = {"segmento": e.segment, "faixas": e.filters.faixa if e.filters else None}
    principais = [a for a in visiveis({"achados": achados}).values() if a["dif_pp"] > 0][:EXEMPLOS_ACHADOS]
    for a in principais:
        refs = buscar_referencias({a["campo"]: a["valor"]}, EXEMPLOS_POR_ACHADO, **recorte)
        referencias.update({r["shortCode"]: r for r in refs if r["shortCode"] not in referencias})
        exemplos[id_achado(a)] = [r["shortCode"] for r in refs]
    return {"achados": achados, "referencias": referencias, "perfis": perfis, "exemplos": exemplos}


# ---------------------------------------------------------------- redator

INSTRUCOES_MODO = {
    "analisar": """Responda à pergunta em poucos parágrafos curtos ou em lista: o que os dados mostram, com os
números dos achados, a robustez de cada um e 1 ou 2 Reels de exemplo por achado principal.""",
    "recomendar": """Escreva de 3 a 6 recomendações práticas e numeradas para a @impulsostone produzir Reels.
Cada recomendação se apoia em UM achado da lista "aparecem MAIS no top" (com o número e a robustez) e em 1 ou 2
Reels de exemplo; prefira os robustos e diga quando um achado é só hipótese. Depois, em uma linha, o que evitar,
usando SÓ a lista "aparecem MENOS no top". A persona orienta o tom, mas não é dado: não atribua a ela números
nem diga "segundo os dados" sobre ela. Se houver perfis em destaque relevantes, sugira-os como referência.""",
}
MIN_REELS = 3  # valores com menos Reels que isso nos dois grupos só fazem ruído para o redator


def _num(x: float | None) -> str:
    return "–" if x is None else f"{x:.2f}".replace(".", ",")


def visiveis(estado: Estado) -> dict[str, dict]:
    """Achados mostrados ao redator, com ids curtos (A1, A2...): primeiro os que aparecem mais no top,
    depois os que aparecem menos. É por esses ids que o redator cita."""
    uteis = [a for a in estado["achados"].values()
             if max(a["n_top"], a["n_controle"]) >= MIN_REELS and a["dif_pp"] and a["lift"] is not None]
    ordem = lambda a: (PIOR[::-1].index(a["robustez"]), -abs(a["dif_pp"]))
    mais = sorted((a for a in uteis if a["dif_pp"] > 0), key=ordem)[:15]
    menos = sorted((a for a in uteis if a["dif_pp"] < 0), key=ordem)[:10]
    return {f"A{i}": a for i, a in enumerate(mais + menos, 1)}


def _contexto(estado: Estado) -> str:
    e = estado["entrada"]
    recorte = _recorte(e)
    linhas = [f"Pergunta: {e.query}", f"Recorte pedido: {recorte}"]
    if recorte != "amostra inteira":
        linhas.append("Achados com base \"amostra inteira\" valem para todos os Reels analisados, não só para o "
                      "recorte. Use-os quando o recorte tiver poucos Reels, dizendo que são da amostra inteira.")
    vis = visiveis(estado)
    exemplos = estado.get("exemplos", {})
    grupos = (("ACHADOS QUE APARECEM MAIS NO TOP", lambda a: a["dif_pp"] > 0),
              ("ACHADOS QUE APARECEM MENOS NO TOP", lambda a: a["dif_pp"] < 0))
    for titulo, cond in grupos:
        linhas += ["", f"{titulo} (id: descrição):"]
        linhas += [f"- {i}: {a['descricao']}; lift {_num(a['lift'])}, IC95 {_num(a['ic95_min'])} a "
                   f"{_num(a['ic95_max'])}; {a['robustez']} (n_top={a['n_top']}); "
                   f"base: {a['recorte'] or 'amostra inteira'}"
                   + (f"; exemplos: {', '.join(f'[{s}]' for s in exemplos[id_achado(a)])}"
                      if exemplos.get(id_achado(a)) else "")
                   for i, a in vis.items() if cond(a)] or ["(nenhum)"]
    linhas += ["", "REELS DE REFERÊNCIA:"]
    linhas += [f"- [{r['shortCode']}] @{r['perfil']} ({r['faixa']}), {r['duracao_s']:.0f} s, "
               f"{r['categorias']['formato_video']}; gancho ({r['categorias']['tipo_hook']}): \"{r['hook_texto']}\"; "
               f"elementos: {', '.join(r['_elementos'])}; motivo: {r['motivo']}"
               for r in estado["referencias"].values()] or ["(nenhum)"]
    if estado["perfis"]:
        linhas += ["", "PERFIS EM DESTAQUE:"]
        linhas += [f"- @{p['perfil']} ({p['faixa']}): {p['n_top']} de {p['n_amostra']} Reels no top; tema "
                   f"{p['tema_predominante']}, formato {p['formato_predominante']}" for p in estado["perfis"].values()]
    return "\n".join(linhas)


def redator(estado: Estado) -> dict:
    e = estado["entrada"]
    sistema = f"{PERSONA}\n\n{REGRAS_DADOS}\n\nTarefa ({e.mode}): {INSTRUCOES_MODO[e.mode]}"
    pedido = _contexto(estado)
    if estado.get("problemas"):
        pedido += "\n\nCORRIJA na nova versão:\n" + "\n".join(f"- {p}" for p in estado["problemas"])
    r = llm().with_structured_output(Redacao, include_raw=True).invoke(
        [SystemMessage(sistema), HumanMessage(pedido)])
    return {"redacao": r["parsed"], "redacoes": estado.get("redacoes", 0) + 1,
            "tokens": estado.get("tokens", 0) + _tokens(r["raw"])}


# ---------------------------------------------------------------- revisor e saída

SHORTCODE_NO_TEXTO = r"\[([A-Za-z0-9_-]{9,})\]"
# ids de achado que o modelo às vezes deixa no texto: [A1], [A1, A3], (A2), [duracao_faixa=mais_90s]
IDS_NO_TEXTO = r"\s*[\[(]\s*(?:A\d+(?:\s*,\s*A\d+)*|[a-z_]+=[^\])]*)\s*[\])]"
# ... e por extenso como aposto: ", conforme visto no achado A1" (o resto é trocado pelo nome do achado)
IDS_POR_EXTENSO = r",?\s*conforme(?: visto)?\s+n?o\s+achado A\d{1,2}\b"


def revisar(estado: Estado) -> list[str]:
    red = estado.get("redacao")
    if red is None:
        return ["a resposta não veio no formato pedido"]
    vis = visiveis(estado)
    problemas = [f"achado citado não existe: {a} (use só os ids A1, A2... da lista)" for a in red.achados_citados
                 if a not in vis]
    problemas += [f"Reel citado não veio das ferramentas: {s}" for s in red.referencias_citadas
                  if s not in estado["referencias"]]
    autores = {r["perfil"] for r in estado["referencias"].values()}
    problemas += [f"perfil citado não veio das ferramentas: {p}" for p in red.perfis_citados
                  if p.lstrip("@") not in estado["perfis"] and p.lstrip("@") not in autores]
    problemas += [f"achado principal não está entre os citados: {a}" for a in red.achados_principais
                  if a not in red.achados_citados]
    problemas += [f"Reel mencionado no texto sem ter vindo das ferramentas: {s}"
                  for s in set(re.findall(SHORTCODE_NO_TEXTO, red.explanation)) if s not in estado["referencias"]]
    sem_numero = [a for a in red.achados_principais
                  if a in vis and f"{vis[a]['freq_top']:.0%}" not in red.explanation]
    if sem_numero:
        problemas.append(f"faltam no texto os números (top × controle) dos achados principais: {', '.join(sem_numero)}")
    if re.search(r"\bA\d{1,2}\b", red.explanation):
        problemas.append("o texto menciona ids de achado (A1, A2...); descreva o achado em palavras")
    if vis and not red.achados_citados:
        problemas.append("nenhum achado citado; a resposta precisa se apoiar nos achados")
    return problemas


def revisor(estado: Estado) -> dict:
    return {"problemas": revisar(estado)}


def decidir_revisao(estado: Estado) -> str:
    return "refazer" if estado["problemas"] and estado["redacoes"] < MAX_REDACOES else "ok"


def montar_saida(estado: Estado) -> dict:
    red = estado.get("redacao") or Redacao(explanation="Não foi possível redigir a resposta.", achados_citados=[],
                                            achados_principais=[], referencias_citadas=[])
    vis = visiveis(estado)
    achados = [vis[a] for a in dict.fromkeys(red.achados_citados) if a in vis]
    texto = re.sub(IDS_NO_TEXTO, "", red.explanation)
    texto = re.sub(IDS_POR_EXTENSO, "", texto)
    texto = re.sub(r"\bA\d{1,2}\b", lambda m: f"“{dados.rotulo(vis[m[0]]['campo'], vis[m[0]]['valor'])}”"
                   if m[0] in vis else m[0], texto)
    refs = [estado["referencias"][s] for s in dict.fromkeys(red.referencias_citadas) if s in estado["referencias"]]
    refs += [estado["referencias"][s] for s in dict.fromkeys(re.findall(SHORTCODE_NO_TEXTO, texto))
             if s in estado["referencias"] and estado["referencias"][s] not in refs]
    perfis = [estado["perfis"][p.lstrip("@")] for p in red.perfis_citados if p.lstrip("@") in estado["perfis"]]
    # Se o texto final ainda não traz os números dos achados principais, eles entram por código, da base.
    sem_numero = [vis[a] for a in red.achados_principais if a in vis and f"{vis[a]['freq_top']:.0%}" not in texto]
    if sem_numero:
        texto += "\n\nNúmeros dos achados principais:\n" + "\n".join(
            f"- {a['descricao']} ({a['robustez']}; base: {a['recorte'] or 'amostra inteira'})" for a in sem_numero)
    resolvidos = ["faltam no texto os números"] + ([] if re.search(r"\bA\d{1,2}\b", texto) else ["o texto menciona ids"])
    avisos = [f"revisão: {p}" for p in estado.get("problemas", []) if not p.startswith(tuple(resolvidos))]
    if any(a["robustez"] == "insuficiente" for a in achados):
        avisos.append("parte dos achados se apoia em poucos Reels (insuficiente); trate como indício")
    recorte = _recorte(estado["entrada"])
    if recorte != "amostra inteira" and any(a["recorte"] is None for a in achados):
        avisos.append(f"parte dos achados vem da amostra inteira, não do recorte pedido ({recorte})")
    # A flag segue o achado mais fraco entre os que sustentam a conclusão (não entre todos os citados).
    principais = [vis[a] for a in red.achados_principais if a in vis] or achados
    flag = min((a["robustez"] for a in principais), key=PIOR.index, default="insuficiente")
    saida = Saida(run_id=estado["run_id"], mode=estado["entrada"].mode, findings=achados, reference_posts=refs,
                  profiles=perfis, confidence_flag=flag, explanation=texto, warnings=avisos)
    return {"saida": saida}
