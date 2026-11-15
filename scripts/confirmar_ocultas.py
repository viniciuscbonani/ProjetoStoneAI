"""Confirma os perfis suspeitos de curtidas ocultas (saída de scripts/curtidas_ocultas.py).

Usa o instagram-scraper/instagram-profile-reels-scraper, que traz o campo
like_and_view_counts_disabled por Reel. Um perfil é confirmado quando a maioria dos Reels
verificados tem esse campo verdadeiro. O resultado vira a coluna `confirmado` em
data/interim/curtidas_ocultas.csv.

Uso:
    .venv/bin/python scripts/confirmar_ocultas.py
"""

import csv
import json
import os
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
ACTOR = "instagram-scraper/instagram-profile-reels-scraper"
REELS_POR_PERFIL = 5
CUSTO_MAX = Decimal("0.10")
TRIAGEM = RAIZ / "data" / "interim" / "curtidas_ocultas.csv"


def main() -> None:
    linhas = list(csv.DictReader(open(TRIAGEM)))
    suspeitos = [l["handle"] for l in linhas if l["suspeito"] == "True"]
    print(f"{len(suspeitos)} suspeitos: {', '.join(suspeitos)}")

    load_dotenv(RAIZ / ".env")
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR).call(
        run_input={"instagramUsernames": suspeitos, "postsPerProfile": REELS_POR_PERFIL},
        max_total_charge_usd=CUSTO_MAX,
        logger=None,
    )
    itens = client.dataset(run.default_dataset_id).list_items(clean=True).items

    hoje = date.today().isoformat()
    (RAIZ / "data" / "raw" / f"confirmacao_ocultas_{hoje}.json").write_text(json.dumps(itens, ensure_ascii=False))

    ocultos = defaultdict(lambda: [0, 0])  # handle -> [ocultos, verificados]
    for x in itens:
        h = (x.get("user") or {}).get("username")
        if h in suspeitos:
            ocultos[h][1] += 1
            ocultos[h][0] += bool(x.get("like_and_view_counts_disabled"))

    for l in linhas:
        n_oc, n = ocultos.get(l["handle"], (0, 0))
        l["verificados"] = n if l["handle"] in suspeitos else ""
        l["confirmado"] = (n > 0 and n_oc / n > 0.5) if l["handle"] in suspeitos else ""
    with open(TRIAGEM, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)

    custo = float(run.usage_total_usd or 0)
    with open(RAIZ / "data" / "raw" / "coletas.csv", "a", newline="") as f:
        csv.writer(f).writerow([
            hoje, "principal", ACTOR, run.id, run.default_dataset_id, ";".join(suspeitos),
            f"postsPerProfile={REELS_POR_PERFIL}", len(itens), round(custo, 4),
            "confirmacao de curtidas ocultas",
        ])
    for h in suspeitos:
        n_oc, n = ocultos.get(h, (0, 0))
        print(f"{h}: {n_oc}/{n} Reels com curtidas ocultas")
    print(f"US$ {custo:.4f}")


if __name__ == "__main__":
    main()
