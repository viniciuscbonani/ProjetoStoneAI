"""Registro das execuções do agente em data/logs/agente.jsonl (uma linha por execução).

Grava a entrada, cada chamada de ferramenta (argumentos e o que voltou), as redações e problemas do revisor,
o modelo, os tokens, a duração e a saída completa, para que qualquer resposta possa ser auditada.
"""

import json
from datetime import datetime

from langchain_core.messages import AIMessage, ToolMessage

from .dados import RAIZ
from .ferramentas import id_achado

LOG = RAIZ / "data" / "logs" / "agente.jsonl"


def _resumo(m: ToolMessage) -> list[str]:
    if m.name == "consultar_caracteristicas":
        return [id_achado(a) for a in m.artifact or []]
    if m.name == "buscar_referencias":
        return [r["shortCode"] for r in m.artifact or []]
    return [p["perfil"] for p in m.artifact or []]


def gravar(estado: dict, modelo: str, duracao_s: float, erro: str | None = None) -> None:
    mensagens = estado.get("messages", [])
    resultados = {m.tool_call_id: m for m in mensagens if isinstance(m, ToolMessage)}
    ferramentas = [{"ferramenta": c["name"], "argumentos": {k: v for k, v in c["args"].items() if k != "estado"},
                    "resultado": _resumo(resultados[c["id"]]) if c["id"] in resultados else None}
                   for m in mensagens if isinstance(m, AIMessage) for c in m.tool_calls]
    saida = estado.get("saida")
    linha = {"run_id": estado.get("run_id"), "quando": datetime.now().isoformat(timespec="seconds"),
             "modelo": modelo, "duracao_s": round(duracao_s, 1), "tokens": estado.get("tokens", 0),
             "entrada": estado["entrada"].model_dump(mode="json"), "ferramentas": ferramentas,
             "redacoes": estado.get("redacoes", 0), "problemas_revisor": estado.get("problemas", []),
             "erro": erro, "saida": saida.model_dump(mode="json") if saida else None}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
