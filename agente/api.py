"""API HTTP do agente, usada pelo front (web/).

Rotas:
- POST /consultas: roda o agente (analisar | recomendar) e devolve a Saida
- GET /panorama: achados do lift e perfis em destaque, sem LLM
- GET /reels/{shortCode} e /reels/{shortCode}/quadros/{nome}: detalhe e quadros de um Reel da base
- GET /execucoes e /execucoes/{run_id}: histórico, lido do log do agente

Uso:
    .venv/bin/uvicorn agente.api:app --port 8000
"""

import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from langchain_google_genai.chat_models import GoogleRateLimitError

from . import IMPLEMENTADOS, dados, executar
from .contrato import Entrada, Saida
from .registro import LOG

app = FastAPI(title="Agente Impulso Stone", version="0.1")
SHORTCODE = re.compile(r"^[A-Za-z0-9_-]{5,20}$")
QUADROS = ["gancho_0s", "gancho_1s", "gancho_2s", "gancho_3s", "meio_40", "meio_60", "final_2s", "final_0s"]


@app.get("/saude")
def saude() -> dict:
    from .nos import MODELO, MODELO_REDATOR
    return {"ok": True, "modos": sorted(IMPLEMENTADOS), "modelos": {"orquestrador": MODELO, "redator": MODELO_REDATOR}}


@app.post("/consultas", response_model=Saida)
def consultar(entrada: Entrada) -> Saida:
    if entrada.mode not in IMPLEMENTADOS:
        raise HTTPException(501, f"modo {entrada.mode} ainda não implementado")
    try:
        return executar(entrada)
    except GoogleRateLimitError:
        raise HTTPException(429, "cota diária do Gemini esgotada; ela zera por volta das 05h")


@app.get("/panorama")
def panorama() -> dict:
    reels = dados.todos_reels()
    return {"totais": {"reels": len(reels), "top": sum(r["grupo"] == "top" for r in reels),
                       "perfis": len({r["perfil"] for r in reels})},
            "achados": dados.achados(), "perfis": dados.perfis()[:20]}


def _validar(short_code: str) -> dict:
    r = dados.reel(short_code) if SHORTCODE.match(short_code) else None
    if r is None:
        raise HTTPException(404, "Reel não encontrado na base")
    return r


@app.get("/reels/{short_code}")
def reel(short_code: str) -> dict:
    r = _validar(short_code)
    pasta = dados.RAIZ / "data" / "midia" / short_code
    return {**r, "quadros": [q for q in QUADROS if (pasta / f"q_{q}.jpg").exists()]}


@app.get("/reels/{short_code}/quadros/{nome}")
def quadro(short_code: str, nome: str) -> FileResponse:
    _validar(short_code)
    caminho = dados.RAIZ / "data" / "midia" / short_code / f"q_{nome}.jpg"
    if nome not in QUADROS or not caminho.exists():
        raise HTTPException(404, "quadro não encontrado")
    return FileResponse(caminho, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


def _log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.open() if l.strip()]


@app.get("/execucoes")
def execucoes(limite: int = 50) -> list[dict]:
    linhas = _log()[-limite:][::-1]
    return [{"run_id": l["run_id"], "quando": l["quando"], "mode": l["entrada"]["mode"],
             "query": l["entrada"]["query"], "segment": l["entrada"].get("segment"),
             "duracao_s": l["duracao_s"], "erro": l["erro"],
             "confidence_flag": (l["saida"] or {}).get("confidence_flag")} for l in linhas]


@app.get("/execucoes/{run_id}")
def execucao(run_id: str) -> dict:
    for l in reversed(_log()):
        if l["run_id"] == run_id:
            return l
    raise HTTPException(404, "execução não encontrada")
