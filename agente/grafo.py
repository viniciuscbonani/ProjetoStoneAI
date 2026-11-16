"""Grafo LangGraph do agente: liga os nós de nos.py e avaliacao.py (as setas do desenho de arquitetura)."""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .avaliacao import avaliador, comparar, ler
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
    g.add_node("ler", ler)
    g.add_node("comparar", comparar)
    g.add_node("avaliador", avaliador)
    g.add_node("revisor", revisor)
    g.add_node("montar_saida", montar_saida)

    # avaliar não precisa do orquestrador: o caminho é fixo (ler o vídeo, comparar, redigir)
    g.add_conditional_edges(START, lambda e: "ler" if e["entrada"].mode == "avaliar" else "orquestrador",
                            ["ler", "orquestrador"])
    g.add_edge("ler", "comparar")
    g.add_edge("comparar", "avaliador")
    g.add_edge("avaliador", "revisor")
    # laço "chama / devolve dados": enquanto o Gemini pedir ferramenta, executa e volta a ele
    g.add_conditional_edges("orquestrador", pediu_ferramenta, ["ferramentas", "coletar"])
    g.add_edge("ferramentas", "orquestrador")
    # losango "Qual modo?"
    g.add_conditional_edges("coletar", lambda e: ESCRITOR_POR_MODO[e["entrada"].mode], ["redator", "gerador"])
    g.add_edge("redator", "revisor")
    g.add_edge("gerador", "revisor")
    # revisor reprovou e ainda cabe nova versão: volta para quem escreveu
    g.add_conditional_edges("revisor", decidir_revisao, ["redator", "gerador", "avaliador", "montar_saida"])
    g.add_edge("montar_saida", END)
    return g.compile()


AGENTE = construir()
