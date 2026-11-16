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
from langchain_google_genai.chat_models import GoogleRateLimitError
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from . import dados
from .contrato import Entrada, Saida
from .ferramentas import FERRAMENTAS, buscar_referencias, id_achado
from .persona import PERSONA, REGRAS_DADOS

# flash-lite: ~500 requisições/dia no plano grátis; o gemini-3.5-flash tem só 20/dia, pouco para 4 a 7
# chamadas por execução. O redator pode usar outro modelo (AGENTE_MODELO_REDATOR); se a cota dele acabar,
# volta para o MODELO.
MODELO = os.environ.get("AGENTE_MODELO", "gemini-3.5-flash-lite")
MODELO_REDATOR = os.environ.get("AGENTE_MODELO_REDATOR", "gemini-3.5-flash")
MAX_CHAMADAS = 5
MAX_REDACOES = 2
EXEMPLOS_ACHADOS = 4  # achados que aparecem mais no top com exemplos buscados por código
EXEMPLOS_POR_ACHADO = 2
ORDEM_ROBUSTEZ = ["robusto", "fragil", "sem_diferenca", "insuficiente"]  # da evidência mais forte à mais fraca
PIOR = ["insuficiente", "fragil", "robusto"]  # níveis da confidence_flag, do pior ao melhor
# "Sem diferença" conta como conclusão firme quando o IC95 descarta efeitos grandes nos dois sentidos.
EQUIVALENCIA = (0.67, 1.5)


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
    campos_pergunta: list[str]  # campos que o orquestrador consultou ou buscou explicitamente
    redacao: Redacao | None
    problemas: list[str]
    redacoes: int
    tokens: int
    chamadas_llm: dict[str, int]  # por nó, para o log
    modelos: list[str]  # modelo de cada chamada, na ordem
    saida: Saida


@cache
def llm(modelo: str = MODELO) -> ChatGoogleGenerativeAI:
    # Sem temperature: os modelos Gemini 3.5 usam amostragem fixa e ignoram o parâmetro.
    load_dotenv(dados.RAIZ / ".env")
    return ChatGoogleGenerativeAI(model=modelo, max_retries=2, google_api_key=os.environ["GEMINI_API_KEY"])


def _contar(estado: Estado, no: str, modelo: str) -> dict:
    chamadas = dict(estado.get("chamadas_llm", {}))
    chamadas[no] = chamadas.get(no, 0) + 1
    return {"chamadas_llm": chamadas, "modelos": [*estado.get("modelos", []), modelo]}


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
    return {"messages": [resposta], "tokens": estado.get("tokens", 0) + _tokens(resposta),
            **_contar(estado, "orquestrador", MODELO)}


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
    campos_pergunta = _campos_pergunta(estado["messages"])
    parcial = {"entrada": estado["entrada"], "achados": achados, "campos_pergunta": campos_pergunta}
    # Exemplos por achado, buscados por código: o vínculo "este Reel exemplifica este achado" vem da base,
    # não da escolha do redator. No analisar, são os valores das características perguntadas (os dois lados:
    # com e sem rosto); no recomendar, o que aparece mais no top.
    if estado["entrada"].mode == "analisar":
        alvos = [a for a in visiveis(parcial).values() if a["campo"] in campos_pergunta and a["n_top"] >= MIN_REELS]
        alvos = sorted(alvos, key=lambda a: -a["freq_top"])[:EXEMPLOS_ACHADOS]
    else:
        alvos = [a for a in visiveis(parcial).values() if a["dif_pp"] > 0][:EXEMPLOS_ACHADOS]
    exemplos = {}
    e = estado["entrada"]
    recorte = {"segmento": e.segment, "faixas": e.filters.faixa if e.filters else None}
    for a in alvos:
        refs = buscar_referencias({a["campo"]: a["valor"]}, EXEMPLOS_POR_ACHADO, **recorte)
        referencias.update({r["shortCode"]: r for r in refs if r["shortCode"] not in referencias})
        exemplos[id_achado(a)] = [r["shortCode"] for r in refs]
    return {"achados": achados, "referencias": referencias, "perfis": perfis, "exemplos": exemplos,
            "campos_pergunta": campos_pergunta}


def _campos_pergunta(mensagens: list) -> list[str]:
    """Campos que o orquestrador pediu explicitamente: em consultar_caracteristicas(campos=...) ou nas
    características de buscar_referencias. Sem campos explícitos (pergunta ampla), a lista fica vazia."""
    campos = []
    for m in mensagens:
        for c in getattr(m, "tool_calls", None) or []:
            if c["name"] == "consultar_caracteristicas":
                campos += c["args"].get("campos") or []
            elif c["name"] == "buscar_referencias":
                campos += [x.split("=")[0] for x in c["args"].get("caracteristicas") or [] if "=" in x]
    return [c for c in dict.fromkeys(campos) if c in dados.CAMPOS]


# ---------------------------------------------------------------- redator

INSTRUCOES_MODO = {
    "analisar": """Responda em poucos parágrafos curtos ou em lista, nesta ordem:
1. PRIMEIRO, a pergunta como foi feita, com o retrato do top: o valor mais comum no top e o percentual
   (ex.: "Sim: 81% dos Reels de alto engajamento mostram o rosto").
2. DEPOIS, se isso diferencia o top dos Reels comuns (controle), conforme o selo de cada valor:
   robusto = diferença consistente; fragil = indício, hipótese a testar; sem_diferenca = NÃO diferencia,
   os Reels comuns têm proporção parecida; insuficiente = poucos Reels para dizer.
   Com selo sem_diferenca, nunca diga que o valor "aparece mais", "se destaca" ou "é indício".
3. Exemplos: 1 ou 2 Reels listados no próprio valor de que você está falando.
Traga outras características só se ajudarem a responder à pergunta.""",
    "recomendar": """Escreva de 3 a 6 recomendações práticas e numeradas para a @impulsostone produzir Reels.
Cada recomendação se apoia em UM achado da lista "aparecem MAIS no top" (com o número e a robustez) e em 1 ou 2
Reels de exemplo; prefira os robustos e diga quando um achado é só hipótese. Depois, em uma linha, o que evitar,
usando SÓ a lista "aparecem MENOS no top". A persona orienta o tom, mas não é dado: não atribua a ela números
nem diga "segundo os dados" sobre ela. Se houver perfis em destaque relevantes, sugira-os como referência.""",
}
MIN_REELS = 3  # valores com menos Reels que isso nos dois grupos só fazem ruído para o redator


def visiveis(estado: Estado) -> dict[str, dict]:
    """Achados mostrados ao redator, com ids curtos (A1, A2...), pelos quais ele cita.
    - recomendar: os que aparecem mais no top e depois os que aparecem menos, sem os "sem diferença"
      (não servem para recomendar nem para evitar);
    - analisar: agrupados por característica (todos os valores lado a lado), primeiro as perguntadas, depois
      as que têm diferença clara."""
    uteis = [a for a in estado["achados"].values() if max(a["n_top"], a["n_controle"]) >= MIN_REELS]
    ordem = lambda a: (ORDEM_ROBUSTEZ.index(a["robustez"]), -abs(a["dif_pp"]))
    if estado["entrada"].mode != "analisar":
        claros = [a for a in uteis if a["robustez"] != "sem_diferenca" and a["dif_pp"] and a["lift"] is not None]
        mais = sorted((a for a in claros if a["dif_pp"] > 0), key=ordem)[:15]
        menos = sorted((a for a in claros if a["dif_pp"] < 0), key=ordem)[:10]
        return {f"A{i}": a for i, a in enumerate(mais + menos, 1)}
    grupos: dict[tuple, list[dict]] = {}
    for a in uteis:
        grupos.setdefault((a["campo"], a["recorte"]), []).append(a)
    perguntados = estado.get("campos_pergunta", [])
    # Características não perguntadas só entram se algum valor tiver diferença clara (robusto ou frágil).
    chaves = [k for k in grupos if k[0] in perguntados
              or any(a["robustez"] in ("robusto", "fragil") for a in grupos[k])]
    chaves.sort(key=lambda k: (k[0] not in perguntados, perguntados.index(k[0]) if k[0] in perguntados else 0,
                               min(ORDEM_ROBUSTEZ.index(a["robustez"]) for a in grupos[k]), k[1] is not None))
    ordenados = [a for k in chaves[:8] for a in sorted(grupos[k], key=lambda a: -a["freq_top"])]
    return {f"A{i}": a for i, a in enumerate(ordenados, 1)}


def _contexto(estado: Estado) -> str:
    e = estado["entrada"]
    recorte = _recorte(e)
    linhas = [f"Pergunta: {e.query}", f"Recorte pedido: {recorte}"]
    if recorte != "amostra inteira":
        linhas.append("Achados com base \"amostra inteira\" valem para todos os Reels analisados, não só para o "
                      "recorte. Use-os quando o recorte tiver poucos Reels, dizendo que são da amostra inteira.")
    vis = visiveis(estado)
    exemplos = estado.get("exemplos", {})

    def linha(i: str, a: dict) -> str:
        comparacao = ("proporção parecida no top e no controle" if a["robustez"] == "sem_diferenca"
                      else dados.vezes(a["lift"]))
        return (f"- {i}: {a['descricao']}; {comparacao}; selo: {a['robustez']} (n_top={a['n_top']})"
                + (f"; exemplos: {', '.join(f'[{s}]' for s in exemplos[id_achado(a)])}"
                   if exemplos.get(id_achado(a)) else ""))

    if e.mode == "analisar":
        atual = None
        for i, a in vis.items():
            if (a["campo"], a["recorte"]) != atual:
                atual = (a["campo"], a["recorte"])
                mais_comum = max((x for x in vis.values() if (x["campo"], x["recorte"]) == atual),
                                 key=lambda x: x["freq_top"])
                linhas += ["", f"{dados.CAMPOS.get(a['campo'], a['campo']).upper()} (base: "
                               f"{a['recorte'] or 'amostra inteira'}; mais comum no top: "
                               f"{dados.rotulo(mais_comum['campo'], mais_comum['valor']).split(': ', 1)[-1]}):"]
            linhas.append(linha(i, a))
        if not vis:
            linhas += ["", "(nenhum achado)"]
    else:
        for titulo, cond in (("ACHADOS QUE APARECEM MAIS NO TOP", lambda a: a["dif_pp"] > 0),
                             ("ACHADOS QUE APARECEM MENOS NO TOP", lambda a: a["dif_pp"] < 0)):
            linhas += ["", f"{titulo} (id: descrição):"]
            linhas += [linha(i, a) + f"; base: {a['recorte'] or 'amostra inteira'}"
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
    mensagens = [SystemMessage(sistema), HumanMessage(pedido)]
    modelo = MODELO_REDATOR
    try:
        r = llm(modelo).with_structured_output(Redacao, include_raw=True).invoke(mensagens)
    except GoogleRateLimitError:
        if modelo == MODELO:
            raise
        modelo = MODELO  # cota do modelo do redator esgotada: segue com o modelo padrão
        r = llm(modelo).with_structured_output(Redacao, include_raw=True).invoke(mensagens)
    return {"redacao": r["parsed"], "redacoes": estado.get("redacoes", 0) + 1,
            "tokens": estado.get("tokens", 0) + _tokens(r["raw"]), **_contar(estado, "redator", modelo)}


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


def _confianca(a: dict) -> str:
    """Nível de confiança de um achado para a confidence_flag. Um "sem diferença" é conclusão firme ("não
    diferencia") quando o IC95 descarta efeitos grandes; com IC largo, é só ausência de evidência."""
    if a["robustez"] != "sem_diferenca":
        return a["robustez"]
    return "robusto" if EQUIVALENCIA[0] <= a["ic95_min"] and a["ic95_max"] <= EQUIVALENCIA[1] else "fragil"


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
            f"- {a['descricao']} ({a['robustez'].replace('_', ' ')}; base: {a['recorte'] or 'amostra inteira'})"
            for a in sem_numero)
    resolvidos = ["faltam no texto os números"] + ([] if re.search(r"\bA\d{1,2}\b", texto) else ["o texto menciona ids"])
    avisos = [f"revisão: {p}" for p in estado.get("problemas", []) if not p.startswith(tuple(resolvidos))]
    if any(a["robustez"] == "insuficiente" for a in achados):
        avisos.append("parte dos achados se apoia em poucos Reels (insuficiente); trate como indício")
    recorte = _recorte(estado["entrada"])
    if recorte != "amostra inteira" and any(a["recorte"] is None for a in achados):
        avisos.append(f"parte dos achados vem da amostra inteira, não do recorte pedido ({recorte})")
    # A flag segue o achado mais fraco entre os que sustentam a conclusão (não entre todos os citados).
    principais = [vis[a] for a in red.achados_principais if a in vis] or achados
    flag = min((_confianca(a) for a in principais), key=PIOR.index, default="insuficiente")
    saida = Saida(run_id=estado["run_id"], mode=estado["entrada"].mode, findings=achados, reference_posts=refs,
                  profiles=perfis, confidence_flag=flag, explanation=texto, warnings=avisos)
    return {"saida": saida}
