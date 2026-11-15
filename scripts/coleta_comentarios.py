"""Coleta comentários dos Reels da amostra e audita as métricas do esdrasdw.

Roda o raspador oficial (apify/instagram-reel-scraper) com o link de cada Reel da amostra. Ele
traz até 10 comentários por Reel, além de curtidas, comentários e visualizações atuais, e um
link novo do vídeo. Serve a três fins:

1. indicador de lead do documento do projeto: comentários com intenção de contato
   ("quero", "como faço", "qual o link"...), em data/interim/comentarios.csv
2. auditoria de precisão: métricas do oficial x esdrasdw, Reel a Reel, em data/interim/auditoria.csv
3. links novos de vídeo, usados por processar_midia.py --links para os Reels sem mídia

Uso:
    .venv/bin/python scripts/coleta_comentarios.py
"""

import csv
import json
import os
import re
import statistics
from datetime import date
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
ACTOR = "apify/instagram-reel-scraper"
CUSTO_MAX = Decimal("3.50")
HOJE = date.today().isoformat()
BRUTO = RAIZ / "data" / "raw" / f"oficial_amostra_{HOJE}.json"

# Intenção de contato ou de compra/participação, a partir dos exemplos do documento do projeto.
INTENCAO = re.compile(
    # Só pedidos: "preço"/"valor" soltos pegavam opiniões ("nunca pagaria esse valor").
    r"\b(quero|eu quero|como fa[cç]o|como fazer|qual (o|é o) link|link|onde (compro|encontro|acho)|"
    r"me (manda|chama|passa)|manda (o|no) (link|direct|dm|privado)|quanto (custa|cobra)|"
    r"qual (o|é o) (valor|pre[cç]o)|tem curso|como (participo|me inscrevo|entro)|quero participar|"
    r"chama (no|na) (dm|direct|privado)|encomenda)\b",
    re.IGNORECASE,
)


def main() -> None:
    amostra = list(csv.DictReader(open(RAIZ / "data" / "processed" / "amostra.csv")))
    por_codigo = {r["shortCode"]: r for r in amostra}

    if BRUTO.exists():
        itens = json.loads(BRUTO.read_text())
    else:
        load_dotenv(RAIZ / ".env")
        client = ApifyClient(os.environ["APIFY_TOKEN"])
        urls = [f"https://www.instagram.com/reel/{sc}/" for sc in por_codigo]
        run = client.actor(ACTOR).call(
            run_input={"username": urls, "resultsLimit": 1},
            max_total_charge_usd=CUSTO_MAX, logger=None,
        )
        itens = client.dataset(run.default_dataset_id).list_items(clean=True).items
        BRUTO.write_text(json.dumps(itens, ensure_ascii=False))
        with open(RAIZ / "data" / "raw" / "coletas.csv", "a", newline="") as f:
            csv.writer(f).writerow([HOJE, "principal", ACTOR, run.id, run.default_dataset_id,
                                    f"{len(urls)} Reels da amostra", "links diretos dos Reels", len(itens),
                                    round(float(run.usage_total_usd or 0), 4), "comentarios + auditoria + links"])

    comentarios, auditoria, links = [], [], {}
    for x in itens:
        sc = x.get("shortCode")
        reel = por_codigo.get(sc)
        if not reel:
            continue
        if x.get("videoUrl"):
            links[sc] = x["videoUrl"]
        coms = [c for c in (x.get("latestComments") or []) if c.get("ownerUsername") != reel["perfil"]]
        com_intencao = [c for c in coms if INTENCAO.search(c.get("text") or "")]
        comentarios.append({
            "shortCode": sc, "grupo": reel["grupo"], "comentarios_lidos": len(coms),
            "com_intencao": len(com_intencao),
            "exemplos": " | ".join((c.get("text") or "")[:80] for c in com_intencao[:3]),
        })
        auditoria.append({
            "shortCode": sc,
            "curtidas_esdrasdw": reel["curtidas"], "curtidas_oficial": x.get("likesCount"),
            "comentarios_esdrasdw": reel["comentarios"], "comentarios_oficial": x.get("commentsCount"),
            "views_esdrasdw": reel["visualizacoes"], "views_oficial": x.get("videoPlayCount"),
        })

    for nome, linhas in (("comentarios", comentarios), ("auditoria", auditoria)):
        with open(RAIZ / "data" / "interim" / f"{nome}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)
    (RAIZ / "data" / "interim" / f"links_videos_oficial_{HOJE}.json").write_text(json.dumps(links))

    print(f"{len(comentarios)}/{len(amostra)} Reels encontrados pelo oficial")
    for g in ("top", "controle"):
        cs = [c for c in comentarios if c["grupo"] == g]
        print(f"  {g}: {sum(c['comentarios_lidos'] for c in cs)} comentários lidos, "
              f"{sum(c['com_intencao'] > 0 for c in cs)} Reels com intenção")

    def desvio(campo: str) -> str:
        difs = [abs(int(a[f"{campo}_oficial"]) - int(a[f"{campo}_esdrasdw"])) / max(int(a[f"{campo}_oficial"]), 1)
                for a in auditoria if a[f"{campo}_oficial"] not in (None, -1) and a[f"{campo}_esdrasdw"] not in ("", None)]
        return f"{campo}: diferença mediana {statistics.median(difs):.1%} (n={len(difs)})" if difs else f"{campo}: sem dados"
    for campo in ("curtidas", "comentarios", "views"):
        print("  auditoria", desvio(campo))


if __name__ == "__main__":
    main()
