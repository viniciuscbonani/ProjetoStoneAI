"""Coleta principal: Reels dos perfis aptos com o esdrasdw/instagram-content-scraper.

Uma única execução com todos os perfis, até 100 Reels por perfil, publicados nos últimos
12 meses. O filtro de 14 dias (métricas estabilizadas) é aplicado depois, na limpeza.

Atenção: quando o perfil oculta as curtidas, este actor grava likesCount = 3 em vez de
marcar como oculto. A detecção é feita na limpeza (ver scripts/curtidas_ocultas.py).

Uso:
    .venv/bin/python scripts/coleta_esdrasdw.py
"""

import csv
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
ACTOR = "esdrasdw/instagram-content-scraper"
REELS_POR_PERFIL = 100
PUBLICADOS_A_PARTIR_DE = "2025-11-14"
CUSTO_MAX = Decimal("1.00")

# Sem os campos pesados (dashManifest, videoVersions, spritesheet, images), que multiplicam
# o tamanho do arquivo e não entram na análise.
CAMPOS = [
    "id", "shortCode", "url", "ownerUsername", "ownerFullName", "ownerId", "timestamp",
    "type", "productType", "isPinned", "caption", "title", "hashtags", "mentions",
    "taggedUsers", "coauthorProducers", "likesCount", "commentsCount", "videoPlayCount",
    "igPlayCount", "videoDuration", "videoUrl", "displayUrl", "hasAudio", "musicInfo",
    "paidPartnership", "locationName",
]


def perfis_aptos() -> list[str]:
    with open(RAIZ / "data" / "perfis_candidatos.csv") as f:
        return [r["handle"] for r in csv.DictReader(f) if r["status"] == "apto"]


def main() -> None:
    load_dotenv(RAIZ / ".env")
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    perfis = perfis_aptos()
    print(f"{len(perfis)} perfis, até {REELS_POR_PERFIL} Reels cada, desde {PUBLICADOS_A_PARTIR_DE}")

    entrada = {
        "directUrls": perfis,
        "resultsType": "reels",
        "resultsLimit": REELS_POR_PERFIL,
        "onlyPostsNewerThan": PUBLICADOS_A_PARTIR_DE,
        "skipPinnedPosts": True,
        "selectedFields": CAMPOS,
    }
    run = client.actor(ACTOR).call(run_input=entrada, max_total_charge_usd=CUSTO_MAX, logger=None)
    itens = client.dataset(run.default_dataset_id).list_items(clean=True).items

    hoje = date.today().isoformat()
    destino = RAIZ / "data" / "raw" / f"esdrasdw_{hoje}.json"
    destino.write_text(json.dumps(itens, ensure_ascii=False))

    custo = float(run.usage_total_usd or 0)
    with open(RAIZ / "data" / "raw" / "coletas.csv", "a", newline="") as f:
        csv.writer(f).writerow([
            hoje, "principal", ACTOR, run.id, run.default_dataset_id, f"{len(perfis)} aptos",
            f"reels resultsLimit={REELS_POR_PERFIL} newerThan={PUBLICADOS_A_PARTIR_DE} skipPinned",
            len(itens), round(custo, 4), "coleta principal",
        ])
    print(f"{run.status}: {len(itens)} Reels, US$ {custo:.4f} -> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
