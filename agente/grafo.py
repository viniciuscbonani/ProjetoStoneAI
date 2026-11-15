"""Grafo LangGraph do agente: liga os nós de nos.py (as setas do desenho de arquitetura)."""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .ferramentas import FERRAMENTAS
from .nos import (Estado, coletar, decidir_revisao, montar_saida, orquestrador, pediu_ferramenta, redator,
                  revisor)

# Modos já implementados; gerar_criativo e avaliar entram com os nós gerador e avaliador.
ESCRITOR_POR_MODO = {"analisar": "redator", "recomendar": "redator"}


def construir():
    g = StateGraph(Estado)
    g.add_node("orquestrador", orquestrador)
    g.add_node("ferramentas", ToolNode(FERRAMENTAS))
    g.add_node("coletar", coletar)
    g.add_node("redator", redator)
    g.add_node("revisor", revisor)
    g.add_node("montar_saida", montar_saida)

    g.add_edge(START, "orquestrador")
    # laço "chama / devolve dados": enquanto o Gemini pedir ferramenta, executa e volta a ele
    g.add_conditional_edges("orquestrador", pediu_ferramenta, ["ferramentas", "coletar"])
    g.add_edge("ferramentas", "orquestrador")
    # losango "Qual modo?"
    g.add_conditional_edges("coletar", lambda e: ESCRITOR_POR_MODO[e["entrada"].mode], ["redator"])
    g.add_edge("redator", "revisor")
    g.add_conditional_edges("revisor", decidir_revisao, {"refazer": "redator", "ok": "montar_saida"})
    g.add_edge("montar_saida", END)
    return g.compile()


AGENTE = construir()
