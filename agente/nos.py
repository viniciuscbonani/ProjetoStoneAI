"""Nós do grafo do agente (cada caixa do desenho de arquitetura é uma função daqui).

orquestrador → (ferramentas ⇄ orquestrador) → coletar → redator | gerador → revisor → montar_saida

- orquestrador: o Gemini com as ferramentas; decide quais chamar e com quais argumentos.
- coletar: copia os dados devolvidos pelas ferramentas (artifacts) para o estado.
- redator: escreve a resposta (analisar | recomendar) a partir do estado, citando achados e Reels por id.
- gerador: escreve 3 criativos (gerar_criativo), cada um com os achados e os Reels que o inspiraram.
- revisor: confere por código que tudo o que foi citado veio das ferramentas e, nos criativos, o tom pela
  persona (LLM); se algo falhar, pede nova versão (1×).
- montar_saida: monta a Saida com os dados do estado, nunca com números do texto do LLM.
"""

import os
import re
from functools import cache
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import GoogleAPIError, GoogleRateLimitError
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from . import dados
from .contrato import Cena, Criativo, Entrada, Saida
from .ferramentas import FERRAMENTAS, buscar_referencias, id_achado
from .persona import ESTILO_VISUAL, PERSONA, REGRAS_DADOS

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


class CenaRascunho(BaseModel):
    tempo: str = Field(description="ex.: 0–3 s")
    descricao: str = Field(description="o que se fala e o que aparece na cena, em português")
    texto_na_tela: str = Field("", description="texto sobreposto ao vídeo, se houver")
    visual: str = Field(description="em inglês: o que a imagem da cena mostra (ação, enquadramento, ambiente), "
                                    "sem repetir a descrição da personagem")


class CriativoRascunho(BaseModel):
    titulo: str
    formato: str = Field(description="ex.: explicativo, talking head, lista de dicas, bastidores")
    duracao_alvo: str = Field(description="ex.: 90 a 120 s")
    gancho: str = Field(description="o que se fala ou mostra nos 3 primeiros segundos")
    roteiro: list[CenaRascunho] = Field(description="4 a 7 cenas, na ordem")
    legenda: str
    cta: str = Field(description="o convite final para se inscrever ou participar do Impulso Stone")
    personagem: str = Field(description="em inglês, uma frase: quem aparece em todas as imagens (idade entre 30 e "
                                        "60, aparência, roupa com um detalhe verde, o negócio)")
    capa: str = Field(description="em inglês: o que a capa vertical do Reel mostra")
    inspirado_em: list[str] = Field(description="shortCodes dos Reels de referência que inspiraram o criativo")
    achados_usados: list[str] = Field(description="ids curtos (A1, A2...) dos achados aplicados")


class Criativos(BaseModel):
    explanation: str = Field(description="2 a 4 frases: por que estes criativos, com os números dos achados")
    criativos: list[CriativoRascunho]


class RevisaoTom(BaseModel):
    problemas: list[str] = Field(description="problemas claros a corrigir, no máximo 5; vazio se estiver bom")


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
    rascunho: Criativos | None
    leitura: dict  # modo avaliar: como o vídeo ou roteiro foi lido
    pontos: list[dict]  # modo avaliar: pontos decididos por código
    redacao_avaliacao: BaseModel | None
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
5. No modo gerar_criativo, junte o que aparece mais no top e Reels de referência dessas características
   (do setor pedido, se houver), que vão inspirar os criativos.
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
   a diferença entre top e controle não é confiável (pode ser variação entre criadores); insuficiente = poucos
   Reels para dizer. Com selo sem_diferenca, nunca diga que o valor "aparece mais", "se destaca" ou "é indício".
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
        # Para criar, só diferenças claras e indícios; para recomendar, também os de poucos dados (com aviso).
        fora = {"sem_diferenca", "insuficiente"} if estado["entrada"].mode == "gerar_criativo" else {"sem_diferenca"}
        claros = [a for a in uteis if a["robustez"] not in fora and a["dif_pp"] and a["lift"] is not None]
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
        comparacao = ("diferença não confiável entre top e controle" if a["robustez"] == "sem_diferenca"
                      else dados.vezes(a["lift"]))
        if a.get("depende_de_poucos"):
            comparacao += " (atenção: o sinal depende de poucos criadores e some sem os 6 maiores; diga isso)"
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


def _escrever(estado: Estado, no: str, esquema: type[BaseModel], tarefa: str,
              contexto: str | None = None) -> tuple[BaseModel | None, dict]:
    """Chama o modelo de redação com saída estruturada; se a cota dele acabar ou ele estiver sobrecarregado
    (503), segue com o modelo padrão."""
    sistema = f"{PERSONA}\n\n{REGRAS_DADOS}\n\nTarefa ({estado['entrada'].mode}): {tarefa}"
    pedido = contexto or _contexto(estado)
    if estado.get("problemas"):
        pedido += "\n\nCORRIJA na nova versão:\n" + "\n".join(f"- {p}" for p in estado["problemas"])
    mensagens = [SystemMessage(sistema), HumanMessage(pedido)]
    modelo = MODELO_REDATOR
    try:
        r = llm(modelo).with_structured_output(esquema, include_raw=True).invoke(mensagens)
    except (GoogleRateLimitError, GoogleAPIError) as e:
        indisponivel = isinstance(e, GoogleRateLimitError) or "503" in str(e) or "UNAVAILABLE" in str(e)
        if modelo == MODELO or not indisponivel:
            raise
        modelo = MODELO  # cota esgotada ou modelo sobrecarregado: segue com o modelo padrão
        r = llm(modelo).with_structured_output(esquema, include_raw=True).invoke(mensagens)
    return r["parsed"], {"redacoes": estado.get("redacoes", 0) + 1,
                         "tokens": estado.get("tokens", 0) + _tokens(r["raw"]), **_contar(estado, no, modelo)}


def redator(estado: Estado) -> dict:
    redacao, extras = _escrever(estado, "redator", Redacao, INSTRUCOES_MODO[estado["entrada"].mode])
    return {"redacao": redacao, **extras}


INSTRUCOES_CRIATIVO = """Escreva 3 criativos de Reels para a @impulsostone atender ao pedido, diferentes entre si
(no formato, no gancho ou no pilar). Em cada criativo:
- Apoie-se em 1 a 3 achados da lista "aparecem MAIS no top" (prefira os de selo robusto; achados_usados = ids)
  e em 1 a 3 Reels de referência (inspirado_em = shortCodes listados). Adapte o que funciona neles para o
  programa; não copie.
- Respeite os achados: se usar "mais de 90 s", a duração do roteiro tem de passar de 90 s. Evite o que aparece
  MENOS no top.
- gancho: concreto, nos 3 primeiros segundos, com uma dor real ou uma curiosidade do dia a dia do negócio;
  nada de frase motivacional genérica.
- roteiro: 4 a 7 cenas com tempo ("0–3 s", "3–20 s"...), o que se fala e o que aparece; texto_na_tela quando
  houver. A última cena é o convite claro para se inscrever ou participar do Impulso Stone.
- legenda: até uns 600 caracteres, no tom da persona, terminando com o mesmo convite; poucas hashtags.
- cta: o convite, em uma frase.
- Imagens (em inglês; o estilo visual é aplicado depois, por código): personagem = quem aparece em todas
  as imagens do criativo, sempre a mesma pessoa; capa = o que a capa mostra; visual de cada cena = o que a
  imagem daquela cena mostra (ação, enquadramento, ambiente do negócio do setor), sem repetir a personagem.
  Mostre a pessoa fazendo a ação; evite imagens centradas num papel escrito, numa tela ou numa placa (o gerador
  de imagem inventa texto). Sem pessoas famosas.
- Se o pedido citar um setor, use o ambiente e os exemplos desse setor.
- Não escreva shortCodes nem ids de achado no roteiro, no gancho ou na legenda; eles vão só em inspirado_em
  e achados_usados.
explanation: 2 a 4 frases sobre por que estes criativos, com os números dos achados principais (top × controle).
Não prometa resultado nem use números que não estejam nos achados."""


def gerador(estado: Estado) -> dict:
    rascunho, extras = _escrever(estado, "gerador", Criativos, INSTRUCOES_CRIATIVO)
    return {"rascunho": rascunho, **extras}


# ---------------------------------------------------------------- revisor e saída

SHORTCODE_NO_TEXTO = r"\[([A-Za-z0-9_-]{9,})\]"
# ids de achado que o modelo às vezes deixa no texto: [A1], [A1, A3], (A2), [duracao_faixa=mais_90s]
IDS_NO_TEXTO = r"\s*[\[(]\s*(?:A\d+(?:\s*,\s*A\d+)*|[a-z_]+=[^\])]*)\s*[\])]"
# ... e por extenso como aposto: ", conforme visto no achado A1" (o resto é trocado pelo nome do achado)
IDS_POR_EXTENSO = r",?\s*conforme(?: visto)?\s+n?o\s+achado A\d{1,2}\b"


def revisar(estado: Estado) -> list[str]:
    if estado["entrada"].mode == "gerar_criativo":
        return revisar_criativos(estado)
    if estado["entrada"].mode == "avaliar":
        from .avaliacao import revisar_avaliacao
        return revisar_avaliacao(estado)
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
    if re.search(r"sem_diferenca|selo (?:robusto|fragil|insuficiente)", red.explanation):
        problemas.append("o texto usa nomes internos de selo; explique a força da evidência em palavras")
    if vis and not red.achados_citados:
        problemas.append("nenhum achado citado; a resposta precisa se apoiar nos achados")
    return problemas


def revisar_criativos(estado: Estado) -> list[str]:
    """Checagem por código: estrutura, Reels de inspiração vindos da base e achados que aparecem mais no top."""
    rasc = estado.get("rascunho")
    if rasc is None:
        return ["a resposta não veio no formato pedido"]
    vis = visiveis(estado)
    problemas = [] if len(rasc.criativos) == 3 else [f"são pedidos 3 criativos, vieram {len(rasc.criativos)}"]
    for n, c in enumerate(rasc.criativos, 1):
        if not c.inspirado_em:
            problemas.append(f"criativo {n}: falta inspirado_em (Reels de referência)")
        problemas += [f"criativo {n}: Reel de inspiração não veio das ferramentas: {s}"
                      for s in c.inspirado_em if s not in estado["referencias"]]
        if not c.achados_usados:
            problemas.append(f"criativo {n}: falta achados_usados")
        problemas += [f"criativo {n}: achado inexistente: {a} (use os ids A1, A2... da lista)"
                      for a in c.achados_usados if a not in vis]
        problemas += [f"criativo {n}: {a} aparece MENOS no top e não pode inspirar o criativo"
                      for a in c.achados_usados if a in vis and vis[a]["dif_pp"] < 0]
        if len(c.roteiro) < 3:
            problemas.append(f"criativo {n}: o roteiro precisa de pelo menos 3 cenas")
        if not c.cta.strip() or not c.personagem.strip() or not c.capa.strip():
            problemas.append(f"criativo {n}: faltam o CTA, a personagem ou a capa")
        if any(not cena.visual.strip() for cena in c.roteiro):
            problemas.append(f"criativo {n}: falta o visual de alguma cena")
    return problemas


PROMPT_TOM = f"""Você revisa criativos de Reels da @impulsostone antes de irem para a equipe da Stone.
{PERSONA}

Aponte só problemas claros, que um editor da Stone exigiria corrigir (no máximo 5, cada um dizendo o criativo):
- tom fora da persona (frio, técnico, com jargão) ou linguagem que exclua quem empreende ("empreendedor(a)");
- promessa exagerada ou garantia de resultado ("fature o dobro", "venda garantida");
- frase motivacional genérica ou mensagem sem gancho;
- final sem convite claro para se inscrever ou participar do programa;
- depoimento ou história sem chamada para ação.
Se estiver bom, devolva a lista vazia."""


def _texto_criativos(rasc: Criativos) -> str:
    return "\n\n".join(
        f"CRIATIVO {n}: {c.titulo}\nGancho: {c.gancho}\nRoteiro:\n"
        + "\n".join(f"- {cena.tempo}: {cena.descricao}" for cena in c.roteiro)
        + f"\nLegenda: {c.legenda}\nCTA: {c.cta}" for n, c in enumerate(rasc.criativos, 1))


def revisor(estado: Estado) -> dict:
    problemas = revisar(estado)
    if estado["entrada"].mode != "gerar_criativo" or problemas:
        return {"problemas": problemas}
    # Só com a estrutura certa vale gastar uma chamada (flash-lite) para revisar o tom.
    r = llm().with_structured_output(RevisaoTom, include_raw=True).invoke(
        [SystemMessage(PROMPT_TOM), HumanMessage(_texto_criativos(estado["rascunho"]))])
    tom = [f"tom: {p}" for p in (r["parsed"].problemas if r["parsed"] else [])]
    return {"problemas": tom, "tokens": estado.get("tokens", 0) + _tokens(r["raw"]),
            **_contar(estado, "revisor_tom", MODELO)}


ESCRITOR_POR_MODO = {"analisar": "redator", "recomendar": "redator", "gerar_criativo": "gerador",
                     "avaliar": "avaliador"}


def decidir_revisao(estado: Estado) -> str:
    """Volta ao nó que escreveu (redator ou gerador) se houver problemas e ainda couber nova versão."""
    if estado["problemas"] and estado["redacoes"] < MAX_REDACOES:
        return ESCRITOR_POR_MODO[estado["entrada"].mode]
    return "montar_saida"


def _confianca(a: dict) -> str:
    """Nível de confiança de um achado para a confidence_flag. Um "sem diferença" é conclusão firme ("não
    diferencia") quando o IC95 descarta efeitos grandes; com IC largo, é só ausência de evidência."""
    if a["robustez"] != "sem_diferenca":
        return a["robustez"]
    return "robusto" if EQUIVALENCIA[0] <= a["ic95_min"] and a["ic95_max"] <= EQUIVALENCIA[1] else "fragil"


def _limpar(texto: str, vis: dict[str, dict]) -> str:
    """Tira do texto os ids de achado que o modelo deixou ([A1], (A2), "conforme o achado A3"...)."""
    texto = re.sub(IDS_NO_TEXTO, "", texto)
    texto = re.sub(IDS_POR_EXTENSO, "", texto)
    return re.sub(r"\bA\d{1,2}\b", lambda m: f"“{dados.rotulo(vis[m[0]]['campo'], vis[m[0]]['valor'])}”"
                  if m[0] in vis else m[0], texto)


def _avisos(estado: Estado, achados: list[dict], resolvidos: tuple[str, ...] = ()) -> list[str]:
    avisos = [f"revisão: {p}" for p in estado.get("problemas", []) if not p.startswith(resolvidos)]
    if any(a["robustez"] == "insuficiente" for a in achados):
        avisos.append("parte dos achados se apoia em poucos Reels (insuficiente); trate como indício")
    recorte = _recorte(estado["entrada"])
    if recorte != "amostra inteira" and any(a["recorte"] is None for a in achados):
        avisos.append(f"parte dos achados vem da amostra inteira, não do recorte pedido ({recorte})")
    return avisos


def prompts_imagem(personagem: str, capa: str, cenas: list[tuple[str, str]]) -> tuple[str, list[str], str]:
    """Monta, a partir da personagem e do visual de cada cena, os prompts dos dois modos de imagem:
    - gerar (Cloudflare): um prompt para a capa e um por cena; as cenas usam um recorte da capa como referência,
      então o texto pede a mesma pessoa, mas uma foto nova (sem copiar pose nem enquadramento);
    - copiar: um prompt único com todas as imagens, para colar numa ferramenta de chat (Gemini, ChatGPT),
      que mantém a personagem ao longo da conversa.
    O estilo e a personagem saem idênticos em todos os prompts porque vêm daqui, não do LLM."""
    prompt_capa = f"{ESTILO_VISUAL}\nMain character: {personagem}\nThis image (Reel cover): {capa}"
    prompts_cenas = [f"{ESTILO_VISUAL}\nThe reference image is a close-up of the main character: keep the same "
                     f"person (face, hair, clothes). Create a new photo with its own pose, framing and setting.\n"
                     f"Main character: {personagem}\nNew photo: {visual}" for _, visual in cenas]
    lista = [f"1. Cover: {capa}"] + [f"{i}. Scene {tempo}: {visual}" for i, (tempo, visual) in enumerate(cenas, 2)]
    prompt_copiar = (f"Create {len(lista)} vertical 9:16 images for an Instagram Reel storyboard, one image at a "
                     f"time, in this order. Keep the SAME person, clothes and place in every image.\n\n"
                     f"{ESTILO_VISUAL}\n\nMain character: {personagem}\n\n" + "\n".join(lista))
    return prompt_capa, prompts_cenas, prompt_copiar


def _limpar_criativo(texto: str, vis: dict[str, dict]) -> str:
    # No criativo, os Reels de inspiração ficam em inspirado_em; o texto que vai para produção não leva códigos.
    return re.sub(r"\s*" + SHORTCODE_NO_TEXTO, "", _limpar(texto, vis)).strip()


def _saida_criativos(estado: Estado) -> Saida:
    """Criativos com Reels e achados filtrados pelo que veio da base; findings e reference_posts são a união
    do que os criativos usaram."""
    vis = visiveis(estado)
    rasc = estado.get("rascunho") or Criativos(explanation="Não foi possível gerar os criativos.", criativos=[])
    criativos, achados, refs = [], {}, {}
    for c in rasc.criativos:
        usados = [vis[a] for a in c.achados_usados if a in vis and vis[a]["dif_pp"] > 0]
        inspiracao = [s for s in c.inspirado_em if s in estado["referencias"]]
        achados.update({id_achado(a): a for a in usados})
        refs.update({s: estado["referencias"][s] for s in inspiracao})
        prompt_capa, prompts_cenas, prompt_copiar = prompts_imagem(
            c.personagem, c.capa, [(cena.tempo, cena.visual) for cena in c.roteiro])
        criativos.append(Criativo(
            titulo=c.titulo, formato=c.formato, duracao_alvo=c.duracao_alvo, gancho=_limpar_criativo(c.gancho, vis),
            roteiro=[Cena(tempo=cena.tempo, descricao=_limpar_criativo(cena.descricao, vis),
                          texto_na_tela=cena.texto_na_tela, visual=cena.visual, prompt_imagem=prompt)
                     for cena, prompt in zip(c.roteiro, prompts_cenas)],
            legenda=_limpar_criativo(c.legenda, vis), cta=_limpar_criativo(c.cta, vis), personagem=c.personagem,
            prompt_capa=prompt_capa, prompt_copiar=prompt_copiar, inspirado_em=inspiracao,
            achados_usados=[f"{a['descricao'].split(' — ')[0]} ({dados.vezes(a['lift'])})" for a in usados]))
    achados = list(achados.values())
    flag = min((_confianca(a) for a in achados), key=PIOR.index, default="insuficiente")
    return Saida(run_id=estado["run_id"], mode="gerar_criativo", findings=achados, reference_posts=list(refs.values()),
                 creatives=criativos, confidence_flag=flag, explanation=_limpar(rasc.explanation, vis),
                 warnings=_avisos(estado, achados))


def montar_saida(estado: Estado) -> dict:
    if estado["entrada"].mode == "gerar_criativo":
        return {"saida": _saida_criativos(estado)}
    if estado["entrada"].mode == "avaliar":
        from .avaliacao import saida_avaliacao
        return {"saida": saida_avaliacao(estado)}
    red = estado.get("redacao") or Redacao(explanation="Não foi possível redigir a resposta.", achados_citados=[],
                                            achados_principais=[], referencias_citadas=[])
    vis = visiveis(estado)
    achados = [vis[a] for a in dict.fromkeys(red.achados_citados) if a in vis]
    texto = _limpar(red.explanation, vis)
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
    avisos = _avisos(estado, achados, tuple(resolvidos))
    # A flag segue o achado mais fraco entre os que sustentam a conclusão (não entre todos os citados).
    principais = [vis[a] for a in red.achados_principais if a in vis] or achados
    flag = min((_confianca(a) for a in principais), key=PIOR.index, default="insuficiente")
    saida = Saida(run_id=estado["run_id"], mode=estado["entrada"].mode, findings=achados, reference_posts=refs,
                  profiles=perfis, confidence_flag=flag, explanation=texto, warnings=avisos)
    return {"saida": saida}
