"""Coleta os Reels mais recentes de cada perfil apto com o rowfinch/instagram-reel-scraper.

Serve a dois fins: identificar perfis com curtidas ocultas (likesCount = null) antes da
coleta principal e trazer compartilhamentos/salvamentos (métrica complementar).

No plano grátis da Apify o actor devolve no máximo 25 Reels por execução e a conta aceita
5 execuções simultâneas, então roda uma execução por perfil, 5 de cada vez.

Uso:
    .venv/bin/python scripts/coleta_rowfinch.py            # todos os aptos
    .venv/bin/python scripts/coleta_rowfinch.py --pular gabii.estevao
"""

import argparse
import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
ACTOR = "rowfinch/instagram-reel-scraper"
REELS_POR_PERFIL = 25
CUSTO_MAX_POR_EXECUCAO = Decimal("0.02")
EXECUCOES_SIMULTANEAS = 5


def perfis_aptos() -> list[str]:
    with open(RAIZ / "data" / "perfis_candidatos.csv") as f:
        return [r["handle"] for r in csv.DictReader(f) if r["status"] == "apto"]


def coletar(client: ApifyClient, handle: str, destino: Path) -> dict:
    run = client.actor(ACTOR).call(
        run_input={"username": [handle], "resultsLimit": REELS_POR_PERFIL, "skipPinnedPosts": True},
        max_total_charge_usd=CUSTO_MAX_POR_EXECUCAO,
        logger=None,
    )
    itens = client.dataset(run.default_dataset_id).list_items(clean=True).items
    (destino / f"{handle}.json").write_text(json.dumps(itens, ensure_ascii=False, indent=1))
    return {
        "handle": handle,
        "run_id": run.id,
        "dataset_id": run.default_dataset_id,
        "status": str(run.status),
        "itens": len(itens),
        "custo_usd": float(run.usage_total_usd or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pular", nargs="*", default=[], help="perfis já coletados")
    args = parser.parse_args()

    load_dotenv(RAIZ / ".env")
    client = ApifyClient(os.environ["APIFY_TOKEN"])

    hoje = date.today().isoformat()
    destino = RAIZ / "data" / "raw" / f"rowfinch_{hoje}"
    destino.mkdir(parents=True, exist_ok=True)

    ja_salvos = {p.stem for p in destino.glob("*.json")}
    fila = [h for h in perfis_aptos() if h not in set(args.pular) | ja_salvos]
    print(f"{len(fila)} perfis na fila ({len(ja_salvos)} já salvos em {destino.name})")

    resultados = []
    with ThreadPoolExecutor(max_workers=EXECUCOES_SIMULTANEAS) as pool:
        tarefas = {pool.submit(coletar, client, h, destino): h for h in fila}
        for t in as_completed(tarefas):
            h = tarefas[t]
            try:
                r = t.result()
                resultados.append(r)
                print(f"ok   {h}: {r['itens']} reels, US$ {r['custo_usd']:.4f}")
            except Exception as e:  # um perfil com erro não derruba a coleta
                print(f"ERRO {h}: {e}")

    with open(destino / "_execucoes.csv", "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["handle", "run_id", "dataset_id", "status", "itens", "custo_usd"])
        if f.tell() == 0:
            w.writeheader()
        w.writerows(resultados)

    total = sum(r["custo_usd"] for r in resultados)
    print(f"\n{len(resultados)} execuções, {sum(r['itens'] for r in resultados)} reels, US$ {total:.4f}")


if __name__ == "__main__":
    main()
