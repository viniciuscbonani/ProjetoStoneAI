"""Marca perfis suspeitos de ocultar curtidas na coleta do esdrasdw.

O esdrasdw grava likesCount = 3 quando as curtidas estão ocultas (visto no teste de rotas com
@gabii.estevao, que oculta todas). Um perfil com quase todos os Reels em exatamente 3 curtidas
não acontece por acaso, então ele vira suspeito e é confirmado depois com o campo
like_and_view_counts_disabled do instagram-scraper/instagram-profile-reels-scraper.

Uso:
    .venv/bin/python scripts/curtidas_ocultas.py data/raw/esdrasdw_2026-11-14.json
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VALOR_OCULTO = 3
LIMIAR_SUSPEITO = 0.8


def main(caminho: str) -> None:
    itens = json.load(open(caminho))
    por_perfil = defaultdict(list)
    for x in itens:
        por_perfil[x["ownerUsername"]].append(x.get("likesCount"))

    perfis = [r["handle"] for r in csv.DictReader(open(RAIZ / "data" / "perfis_candidatos.csv")) if r["status"] == "apto"]
    linhas = []
    for h in perfis:
        likes = por_perfil.get(h, [])
        n = len(likes)
        com_3 = sum(v == VALOR_OCULTO for v in likes)
        prop = com_3 / n if n else 0
        linhas.append({
            "handle": h, "reels": n, "likes_igual_3": com_3, "proporcao": round(prop, 3),
            "suspeito": n > 0 and prop >= LIMIAR_SUSPEITO,
        })

    destino = RAIZ / "data" / "interim" / "curtidas_ocultas.csv"
    with open(destino, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)

    suspeitos = [l for l in linhas if l["suspeito"]]
    sem_reels = [l["handle"] for l in linhas if l["reels"] == 0]
    parciais = [l for l in linhas if 0 < l["proporcao"] < LIMIAR_SUSPEITO and l["likes_igual_3"] >= 3]
    print(f"{len(suspeitos)} suspeitos: {', '.join(l['handle'] for l in suspeitos)}")
    print(f"{len(parciais)} com alguns Reels em 3: {', '.join(f'{l['handle']} ({l['likes_igual_3']}/{l['reels']})' for l in parciais)}")
    print(f"{len(sem_reels)} sem Reels na coleta: {', '.join(sem_reels)}")
    print(f"-> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main(sys.argv[1])
