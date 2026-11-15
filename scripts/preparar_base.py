"""Limpa a coleta principal e calcula a taxa de engajamento de cada Reel.

Todos os Reels da coleta ficam em data/processed/base.csv, com colunas que dizem por que cada
um está ou não no ranking (`motivo_fora`). Só entram no ranking (`no_ranking = True`):
- Reels do próprio perfil apto (colaborações publicadas por terceiros ficam de fora)
- publicados há pelo menos 14 dias na data da coleta (métricas estabilizadas)
- de perfis sem ocultação sistemática de curtidas (confirmada em scripts/confirmar_ocultas.py)
- com curtidas visíveis: nos perfis com ocultação parcial, likesCount = 3 indica curtida oculta
- com visualizações >= --min-views
- fora dos perfis de referência (PERFIS_REFERENCIA): o @impulsostone, para quem os criativos são
  feitos, e embaixadores além dos 1–2 recomendados na aula do case

Taxa de engajamento = (curtidas + comentários) / seguidores, com os seguidores do raspador de
perfis de 11/11.

Uso:
    .venv/bin/python scripts/preparar_base.py                  # só mostra a distribuição de views
    .venv/bin/python scripts/preparar_base.py --min-views 1000
"""

import argparse
import csv
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COLETA = RAIZ / "data" / "raw" / "esdrasdw_2026-11-14.json"
PERFIS_JSON = RAIZ / "data" / "raw" / "perfis_2026-11-11.json"
DATA_COLETA = date(2026, 11, 14)
DIAS_MINIMOS = 14
LIKES_OCULTOS = 3  # valor que o esdrasdw grava quando as curtidas estão ocultas
MIN_REELS_COM_3_PARCIAL = 3  # perfis com pelo menos isso de Reels em 3 curtidas = ocultação parcial
CORTES_TESTADOS = [0, 300, 500, 1000, 2000, 5000]
# @impulsostone: perfil-alvo dos criativos, serve de linha de base e não de referência externa.
# @indiacorrea: embaixadora do Impulso com só 3 Reels; ficam @rodrigofinancas e @chefrut.
PERFIS_REFERENCIA = {"impulsostone", "indiacorrea"}


def carregar_perfis() -> dict[str, dict]:
    perfis = {r["handle"]: r for r in csv.DictReader(open(RAIZ / "data" / "perfis_candidatos.csv")) if r["status"] == "apto"}
    seguidores = {x["username"]: x["followersCount"] for x in json.load(open(PERFIS_JSON)) if not x.get("error")}
    for h, r in perfis.items():
        r["seguidores"] = seguidores[h]
    return perfis


def carregar_ocultacao() -> tuple[set[str], set[str]]:
    sistematicos, parciais = set(), set()
    for r in csv.DictReader(open(RAIZ / "data" / "interim" / "curtidas_ocultas.csv")):
        if r["confirmado"] == "True":
            sistematicos.add(r["handle"])
        elif int(r["likes_igual_3"]) >= MIN_REELS_COM_3_PARCIAL:
            parciais.add(r["handle"])
    return sistematicos, parciais


def montar_base(min_views: int) -> list[dict]:
    perfis = carregar_perfis()
    sistematicos, parciais = carregar_ocultacao()
    limite_data = (DATA_COLETA - timedelta(days=DIAS_MINIMOS)).isoformat()

    base, vistos = [], set()
    for x in json.load(open(COLETA)):
        if x["shortCode"] in vistos:
            continue
        vistos.add(x["shortCode"])
        dono = x["ownerUsername"]
        perfil = perfis.get(dono)
        likes, coments, views = x.get("likesCount"), x.get("commentsCount") or 0, x.get("videoPlayCount") or 0
        curtida_oculta = dono in sistematicos or (dono in parciais and likes == LIKES_OCULTOS)

        if perfil is None:
            motivo = "colaboracao_terceiro"
        elif x["timestamp"][:10] > limite_data:
            motivo = "menos_de_14_dias"
        elif dono in sistematicos:
            motivo = "perfil_oculta_curtidas"
        elif curtida_oculta:
            motivo = "curtida_oculta"
        elif views < min_views:
            motivo = "abaixo_corte_views"
        elif dono in PERFIS_REFERENCIA:
            motivo = "perfil_referencia"
        else:
            motivo = ""

        seg = int(perfil["seguidores"]) if perfil else None
        base.append({
            "shortCode": x["shortCode"], "url": x.get("url"), "perfil": dono,
            "publicado_em": x["timestamp"][:10], "curtidas": likes, "comentarios": coments,
            "visualizacoes": views, "duracao_s": round(x.get("videoDuration") or 0, 1),
            "seguidores": seg, "faixa": perfil["faixa"] if perfil else "", "tipo": perfil["tipo"] if perfil else "",
            "nicho": perfil["nicho"] if perfil else "",
            "perfil_oculta_parcial": dono in parciais, "curtida_oculta": curtida_oculta,
            "taxa_engajamento": round((likes + coments) / seg, 6) if seg and not curtida_oculta and likes is not None else "",
            "taxa_visualizacoes": round(views / seg, 6) if seg else "",
            "taxa_comentarios": round(coments / seg, 6) if seg else "",
            "no_ranking": motivo == "", "motivo_fora": motivo,
            "legenda": " ".join((x.get("caption") or "").split()),
        })
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-views", type=int, help="corte mínimo de visualizações; sem ele, só mostra a distribuição")
    args = parser.parse_args()

    base = montar_base(args.min_views or 0)
    candidatos = [r for r in base if r["motivo_fora"] in ("", "abaixo_corte_views") and r["perfil"] not in PERFIS_REFERENCIA]
    print("Reels antes do corte de views:", len(candidatos))
    for corte in CORTES_TESTADOS:
        ficam = [r for r in candidatos if r["visualizacoes"] >= corte]
        perfis = Counter(r["perfil"] for r in ficam)
        print(f"  corte {corte:>5}: {len(ficam):>5} Reels, {len(perfis)} perfis, "
              f"micro={sum(1 for r in ficam if r['faixa'] == 'micro')}")

    if args.min_views is None:
        return

    destino = RAIZ / "data" / "processed" / "base.csv"
    destino.parent.mkdir(exist_ok=True)
    with open(destino, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(base[0]))
        w.writeheader()
        w.writerows(base)
    print(f"\nMotivos fora do ranking (corte {args.min_views}):")
    for motivo, n in Counter(r["motivo_fora"] or "no_ranking" for r in base).most_common():
        print(f"  {motivo}: {n}")
    print(f"-> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
