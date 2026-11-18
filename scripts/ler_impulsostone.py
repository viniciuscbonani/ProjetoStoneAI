"""Lê os Reels da @impulsostone como os da amostra, para o diagnóstico do perfil.

Os 56 Reels do perfil estão em base.csv (motivo_fora = perfil_referencia, fora do top e do controle). Para cada um:
1. baixa o vídeo por um link novo (os da coleta de 14/11 expiram; uma execução do esdrasdw só com o perfil)
2. extrai quadros, cortes e áudio (midia.extrair) e apaga o vídeo
3. transcreve (faster-whisper local)
4. anota com a rubrica no flash-lite

Mídia em data/midia/{shortCode}/, como a amostra (a gaveta do Reel na API já lê de lá), e anotação em
data/processed/impulsostone.jsonl. Cada etapa pula o que já foi feito, então o script pode ser retomado.

Uso:
    .venv/bin/python scripts/ler_impulsostone.py
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import date
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agente import midia  # noqa: E402
from agente.rubrica import VERSAO  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
MIDIA = RAIZ / "data" / "midia"
PERFIL = "impulsostone"
LINKS = RAIZ / "data" / "interim" / f"links_{PERFIL}_{date.today().isoformat()}.json"
SAIDA = RAIZ / "data" / "processed" / f"{PERFIL}.jsonl"
MODELO = "gemini-3.5-flash-lite"


def links_novos() -> dict[str, str]:
    if LINKS.exists():
        return json.loads(LINKS.read_text())
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor("esdrasdw/instagram-content-scraper").call(
        run_input={"directUrls": [PERFIL], "resultsType": "reels", "resultsLimit": 100,
                   "onlyPostsNewerThan": "2025-11-14", "skipPinnedPosts": False,
                   "selectedFields": ["shortCode", "videoUrl"]},
        max_total_charge_usd=Decimal("0.10"), logger=None,
    )
    itens = client.dataset(run.default_dataset_id).list_items(clean=True).items
    links = {x["shortCode"]: x["videoUrl"] for x in itens if x.get("videoUrl")}
    LINKS.write_text(json.dumps(links))
    with open(RAIZ / "data" / "raw" / "coletas.csv", "a", newline="") as f:
        csv.writer(f).writerow([date.today().isoformat(), "principal", "esdrasdw/instagram-content-scraper",
                                run.id, run.default_dataset_id, PERFIL, "so shortCode e videoUrl", len(itens),
                                round(float(run.usage_total_usd or 0), 4), "links novos para o diagnostico"])
    return links


def baixar(reel: dict, url: str) -> None:
    pasta = MIDIA / reel["shortCode"]
    pasta.mkdir(parents=True, exist_ok=True)
    video = pasta / "video.mp4"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(video, "wb") as f:
        f.write(r.read())
    try:
        midia.extrair(video, pasta, float(reel["duracao_s"] or 0))
    finally:
        video.unlink(missing_ok=True)


def main() -> None:
    load_dotenv(RAIZ / ".env")
    reels = [r for r in csv.DictReader(open(RAIZ / "data" / "processed" / "base.csv")) if r["perfil"] == PERFIL]
    print(f"{len(reels)} Reels da @{PERFIL}")

    pendentes = [r for r in reels if not (MIDIA / r["shortCode"] / "meta.json").exists()]
    if pendentes:
        links = links_novos()
        for r in pendentes:
            if r["shortCode"] not in links:
                print(f"  sem link: {r['shortCode']}")
                continue
            try:
                baixar(r, links[r["shortCode"]])
            except Exception as e:  # um Reel com erro não derruba o lote
                print(f"  erro no download {r['shortCode']}: {str(e)[:150]}")
    print("mídia pronta")

    for r in reels:
        pasta = MIDIA / r["shortCode"]
        if (pasta / "audio.m4a").exists() and not (pasta / "transcricao.json").exists():
            midia.transcrever(pasta)
    print("transcrição pronta")

    feitos = {a["shortCode"] for a in map(json.loads, SAIDA.open())} if SAIDA.exists() else set()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    with SAIDA.open("a") as f:
        for r in reels:
            pasta = MIDIA / r["shortCode"]
            if r["shortCode"] in feitos or not (pasta / "meta.json").exists():
                continue
            try:
                anot = midia.anotar(client, MODELO, pasta, r["legenda"])
            except (errors.APIError, ValidationError) as e:
                print(f"  erro na anotação {r['shortCode']}: {str(e)[:150]}")
                continue
            f.write(json.dumps({"shortCode": r["shortCode"], "perfil": PERFIL, "modelo": MODELO,
                                "versao_rubrica": VERSAO, **anot}, ensure_ascii=False) + "\n")
            f.flush()
    total = sum(1 for _ in SAIDA.open()) if SAIDA.exists() else 0
    print(f"concluído: {total}/{len(reels)} Reels anotados -> {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
