"""Grafo LangGraph do agente: liga os nós de nos.py (as setas do desenho de arquitetura)."""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .ferramentas import FERRAMENTAS
from .nos import (ESCRITOR_POR_MODO, Estado, coletar, decidir_revisao, gerador, montar_saida, orquestrador,
                  pediu_ferramenta, redator, revisor)


def construir():
    g = StateGraph(Estado)
    g.add_node("orquestrador", orquestrador)
    g.add_node("ferramentas", ToolNode(FERRAMENTAS))
    g.add_node("coletar", coletar)
    g.add_node("redator", redator)
    g.add_node("gerador", gerador)
    g.add_node("revisor", revisor)
    g.add_node("montar_saida", montar_saida)

    g.add_edge(START, "orquestrador")
    # laço "chama / devolve dados": enquanto o Gemini pedir ferramenta, executa e volta a ele
    g.add_conditional_edges("orquestrador", pediu_ferramenta, ["ferramentas", "coletar"])
    g.add_edge("ferramentas", "orquestrador")
    # losango "Qual modo?"
    g.add_conditional_edges("coletar", lambda e: ESCRITOR_POR_MODO[e["entrada"].mode], ["redator", "gerador"])
    g.add_edge("redator", "revisor")
    g.add_edge("gerador", "revisor")
    # revisor reprovou e ainda cabe nova versão: volta para quem escreveu
    g.add_conditional_edges("revisor", decidir_revisao, ["redator", "gerador", "montar_saida"])
    g.add_edge("montar_saida", END)
    return g.compile()


AGENTE = construir()
