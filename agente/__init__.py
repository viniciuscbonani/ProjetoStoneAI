"""Agente de conteúdo de alto engajamento para MPEs (TAPI Stone × Inteli Academy).

Uso:
    from agente import executar
    saida = executar({"mode": "analisar", "query": "Que duração de Reels mais aparece no top?"})
    print(saida.explanation)
"""

import time
import uuid
from collections.abc import Callable
from datetime import datetime

from langchain_core.messages import HumanMessage

from .contrato import Entrada, Saida

IMPLEMENTADOS = {"analisar", "recomendar", "gerar_criativo", "avaliar"}


def executar(entrada: Entrada | dict, ao_avancar: Callable[[str], None] | None = None) -> Saida:
    """Roda o agente e grava o log. `ao_avancar(nó)` é chamado a cada nó concluído (a API usa para mostrar
    o progresso de uma avaliação)."""
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
        if ao_avancar is None:
            estado = AGENTE.invoke(estado)
        else:
            for modo, parte in AGENTE.stream(estado, stream_mode=["updates", "values"]):
                if modo == "values":
                    estado = parte
                else:
                    for no in parte:
                        ao_avancar(no)
    except Exception as e:
        registro.gravar(estado, MODELO, time.time() - inicio, erro=repr(e)[:500])
        raise
    registro.gravar(estado, MODELO, time.time() - inicio)
    return estado["saida"]


__all__ = ["Entrada", "Saida", "executar"]
