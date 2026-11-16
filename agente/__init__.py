"""Agente de conteúdo de alto engajamento para MPEs (TAPI Stone × Inteli Academy).

Uso:
    from agente import executar
    saida = executar({"mode": "analisar", "query": "Que duração de Reels mais aparece no top?"})
    print(saida.explanation)
"""

import time
import uuid
from datetime import datetime

from langchain_core.messages import HumanMessage

from .contrato import Entrada, Saida

IMPLEMENTADOS = {"analisar", "recomendar", "gerar_criativo"}


def executar(entrada: Entrada | dict) -> Saida:
    from . import registro
    from .grafo import AGENTE
    from .nos import MODELO

    entrada = Entrada.model_validate(entrada)
    if entrada.mode not in IMPLEMENTADOS:
        raise NotImplementedError(f"modo {entrada.mode} ainda não implementado")
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    estado = {"run_id": run_id, "entrada": entrada, "messages": [HumanMessage(entrada.query)]}
    inicio = time.time()
    try:
        estado = AGENTE.invoke(estado)
    except Exception as e:
        registro.gravar(estado, MODELO, time.time() - inicio, erro=repr(e)[:500])
        raise
    registro.gravar(estado, MODELO, time.time() - inicio)
    return estado["saida"]


__all__ = ["Entrada", "Saida", "executar"]
