"""Ferramentas do agente: funções que leem a base e devolvem dados reais.

Cada ferramenta existe em duas formas:
- a função Python pura (consultar_caracteristicas, buscar_referencias, perfis_em_destaque), testável
  sozinha e reutilizável pela API;
- o @tool do LangChain que o orquestrador chama. Ele devolve (texto, dados): o texto curto é o que o
  LLM lê para decidir o próximo passo; os dados vão para o estado do grafo e de lá para a saída. Assim,
  números e links da resposta nunca passam pela redação do LLM.

O recorte pedido pelo usuário (segment e filters da entrada) é aplicado pelas próprias ferramentas,
lido do estado, para não depender de o LLM repassá-lo.
"""

from datetime import date
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from . import dados

CAMPOS_PADRAO = ["duracao_faixa", "formato_video", "tipo_hook", "tema_principal", "pilar_impulso", "tem_rosto",
                 "tem_cta", "tipo_cta", "convite_participacao", "abordagem", "prova_social", "texto_na_tela",
                 "ritmo_cortes", "legenda_tamanho"]
CATEGORIAS_REFERENCIA = ["formato_video", "duracao_faixa", "tipo_hook", "hook_visual", "tema_principal",
                         "pilar_impulso", "segmento_publico", "tem_rosto", "tem_cta", "tipo_cta", "abordagem", "tom"]
MAX_POR_PERFIL = 2
ORDEM_ROBUSTEZ = {"robusto": 0, "fragil": 1, "insuficiente": 2}


def _recorte(segmento: str | None, faixas: list[str] | None, inicio: date | None, fim: date | None) -> str | None:
    partes = [f"segmento={segmento}" if segmento else "", f"faixa={'+'.join(faixas)}" if faixas else "",
              f"desde={inicio}" if inicio else "", f"ate={fim}" if fim else ""]
    return ", ".join(p for p in partes if p) or None


def consultar_caracteristicas(campos: list[str] | None = None, segmento: str | None = None,
                              faixas: list[str] | None = None, inicio: date | None = None,
                              fim: date | None = None) -> list[dict]:
    """Top x controle por característica. Sem recorte, usa o lift da amostra inteira; com recorte,
    recalcula dentro dele."""
    campos = [c for c in (campos or CAMPOS_PADRAO) if c in dados.CAMPOS] or CAMPOS_PADRAO
    recorte = _recorte(segmento, faixas, inicio, fim)
    if not recorte:
        return dados.achados(campos)
    reels = dados.filtrar(segmento=segmento, faixas=faixas, inicio=inicio, fim=fim)
    return dados.comparar(reels, campos, recorte)


def _referencia(r: dict, motivo: str) -> dict:
    return {"shortCode": r["shortCode"], "url": r["url"], "perfil": r["perfil"], "faixa": r["faixa"],
            "seguidores": r["seguidores"], "curtidas": r["curtidas"], "comentarios": r["comentarios"],
            "visualizacoes": r["visualizacoes"], "taxa_engajamento": round(r["taxa_engajamento"], 4),
            "duracao_s": r["duracao_s"], "publicado_em": r["publicado_em"], "hook_texto": r["hook_texto"],
            "categorias": {c: r[c] for c in CATEGORIAS_REFERENCIA}, "motivo": motivo,
            # extras para o redator; não fazem parte do ReferencePost
            "_legenda": r["legenda"][:300], "_elementos": r["elementos_top5"]}


def buscar_referencias(caracteristicas: dict[str, str] | None = None, n: int = 5, segmento: str | None = None,
                       faixas: list[str] | None = None, inicio: date | None = None,
                       fim: date | None = None) -> list[dict]:
    """Reels do grupo top com as características pedidas, por taxa de engajamento, no máximo 2 por perfil.
    Com segmento e poucos resultados, completa com Reels de público geral (o motivo indica isso)."""
    condicoes = {c: v for c, v in (caracteristicas or {}).items() if c in dados.CAMPOS}
    descricao = "; ".join(dados.rotulo(c, v) for c, v in condicoes.items()) or "alto engajamento"
    # Referência para a Stone tem de falar de negócio (lifestyle e humor puro ficam fora), salvo pedido explícito.
    condicoes.setdefault("fala_de_negocio", True)

    def coletar(seg, motivo, ja):
        candidatos = sorted(dados.filtrar(grupo="top", segmento=seg, faixas=faixas, inicio=inicio, fim=fim,
                                          condicoes=condicoes), key=lambda r: -r["taxa_engajamento"])
        por_perfil, saida = {}, []
        for r in candidatos:
            if r["shortCode"] in ja or por_perfil.get(r["perfil"], 0) >= MAX_POR_PERFIL:
                continue
            por_perfil[r["perfil"]] = por_perfil.get(r["perfil"], 0) + 1
            saida.append(_referencia(r, motivo))
        return saida

    refs = coletar(segmento, f"top com {descricao}" + (f" (segmento {segmento})" if segmento else ""), set())[:n]
    if segmento and len(refs) < n:
        refs += coletar("geral", f"top com {descricao} (público geral; poucos Reels do segmento {segmento})",
                        {r["shortCode"] for r in refs})[:n - len(refs)]
    return refs


def perfis_em_destaque(n: int = 8, segmento: str | None = None, faixas: list[str] | None = None) -> list[dict]:
    """Criadores com mais Reels no top (no segmento, se houver), com tema e formato predominantes."""
    lista = dados.perfis(faixas)
    if segmento:
        no_segmento = {}
        for r in dados.filtrar(grupo="top", segmento=segmento, faixas=faixas):
            no_segmento[r["perfil"]] = no_segmento.get(r["perfil"], 0) + 1
        lista = sorted((p for p in lista if p["perfil"] in no_segmento), key=lambda p: -no_segmento[p["perfil"]])
    return lista[:n]


# ---------------------------------------------------------------- versões @tool para o orquestrador

def id_achado(a: dict) -> str:
    """Identificador estável de um achado, usado nas citações: campo=valor [recorte]."""
    return f"{a['campo']}={a['valor']}" + (f" [{a['recorte']}]" if a["recorte"] else "")


def _do_estado(estado: dict) -> dict:
    e = estado["entrada"]
    f = e.filters
    return {"segmento": e.segment, "faixas": f.faixa if f else None,
            "inicio": f.periodo_inicio if f else None, "fim": f.periodo_fim if f else None}


@tool("consultar_caracteristicas", response_format="content_and_artifact")
def consultar_caracteristicas_tool(estado: Annotated[dict, InjectedState], campos: list[str] | None = None,
                                   ignorar_recorte: bool = False) -> tuple[str, list[dict]]:
    """Compara a frequência de características entre os Reels de alto engajamento (top 10%) e um grupo de
    controle. Use para saber O QUE aparece mais (ou menos) no top. `campos` limita a comparação (ex.:
    ["duracao_faixa", "formato_video"]); sem campos, compara os principais. O recorte do pedido (segmento,
    faixa, período) é aplicado automaticamente; com ignorar_recorte=true, consulta a amostra inteira (útil
    quando o recorte tem poucos Reels).

    Campos disponíveis: duracao_faixa, formato_video, tipo_hook, hook_visual, tema_principal, pilar_impulso,
    segmento_publico, tem_rosto, pessoa_em_cena, prova_social, texto_na_tela, tom, usa_linguagem_regional,
    tem_cta, tipo_cta, oferta_ou_beneficio_explicito, convite_participacao, abordagem, fala_de_negocio,
    tem_data_comemorativa, ritmo_cortes, legenda_tamanho."""
    recorte = {} if ignorar_recorte else _do_estado(estado)
    linhas = consultar_caracteristicas(campos, **recorte)
    if not linhas:
        return "Nenhum Reel no recorte pedido.", []
    ordem = sorted(linhas, key=lambda a: (ORDEM_ROBUSTEZ[a["robustez"]], -abs(a["dif_pp"])))
    texto = [f"Recorte: {linhas[0]['recorte'] or 'amostra inteira'} (top × controle; robustez entre colchetes)"]
    texto += [f"- {id_achado(a)}: {a['descricao']}, lift {a['lift']} [{a['robustez']}, n_top={a['n_top']}]"
              for a in ordem[:25]]
    return "\n".join(texto), linhas


@tool("buscar_referencias", response_format="content_and_artifact")
def buscar_referencias_tool(estado: Annotated[dict, InjectedState], caracteristicas: list[str] | None = None,
                            n: int = 5) -> tuple[str, list[dict]]:
    """Busca Reels REAIS do grupo de alto engajamento que tenham as características pedidas, para citar como
    referência. `caracteristicas` é uma lista de "campo=valor", como aparecem em consultar_caracteristicas
    (ex.: ["duracao_faixa=mais_90s", "formato_video=explicativo"]). Devolve até `n` Reels (máx. 8), com link
    e métricas. O recorte do pedido é aplicado automaticamente."""
    pares = dict(c.split(" [")[0].split("=", 1) for c in caracteristicas or [] if "=" in c)
    refs = buscar_referencias(pares, min(n, 8), **_do_estado(estado))
    if not refs:
        return "Nenhum Reel do top com todas essas características; tente com menos características.", []
    texto = [f"- {r['shortCode']} (@{r['perfil']}, {r['faixa']}, {r['duracao_s']:.0f} s, "
             f"{r['categorias']['formato_video']}, gancho {r['categorias']['tipo_hook']}: \"{r['hook_texto']}\"; "
             f"tema {r['categorias']['tema_principal']}; elementos: {', '.join(r['_elementos'])})"
             for r in refs]
    return "\n".join(texto), refs


@tool("perfis_em_destaque", response_format="content_and_artifact")
def perfis_em_destaque_tool(estado: Annotated[dict, InjectedState], n: int = 8) -> tuple[str, list[dict]]:
    """Lista os criadores que mais aparecem entre os Reels de alto engajamento, com o tema e o formato
    predominantes de cada um. Use para recomendar referências de criadores ou parcerias."""
    d = _do_estado(estado)
    lista = perfis_em_destaque(min(n, 15), d["segmento"], d["faixas"])
    if not lista:
        return "Nenhum perfil no recorte pedido.", []
    texto = [f"- @{p['perfil']} ({p['faixa']}, {p['seguidores']} seguidores): {p['n_top']} de {p['n_amostra']} "
             f"Reels no top; tema {p['tema_predominante']}, formato {p['formato_predominante']}" for p in lista]
    return "\n".join(texto), lista


FERRAMENTAS = [consultar_caracteristicas_tool, buscar_referencias_tool, perfis_em_destaque_tool]
