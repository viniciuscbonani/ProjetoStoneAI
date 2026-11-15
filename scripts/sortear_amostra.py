"""Sorteia a amostra que vai para o Gemini: top 10% + controle estratificado por faixa.

- grupo "top": os 10% de maior taxa de engajamento entre os Reels do ranking
- grupo "controle": o mesmo número de Reels sorteados do resto do ranking, com a mesma
  proporção de faixas (micro/médio/grande) do top. Perfis pequenos têm taxa por seguidor
  maior e dominam o top; sem estratificar, diferenças de conteúdo se confundiriam com
  diferenças de tamanho de perfil.

O controle é sorteado em duas etapas, para preservar o sorteio feito antes da exclusão dos
perfis de referência (motivo_fora = perfil_referencia), cujos vídeos já tinham sido processados:
1. sorteio original (semente 42) sobre o ranking que ainda incluía esses perfis;
2. saem os Reels dos perfis de referência e os que entraram no top, e as vagas de cada faixa são
   completadas com um segundo sorteio (semente 43) entre os Reels restantes.

Uso:
    .venv/bin/python scripts/sortear_amostra.py
"""

import csv
import random
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROPORCAO_TOP = 0.10
SEMENTE = 42
SEMENTE_REPOSICAO = 43


def top_e_resto(ranking: list[dict]) -> tuple[list[dict], list[dict]]:
    ordenado = sorted(ranking, key=lambda r: float(r["taxa_engajamento"]), reverse=True)
    n_top = round(len(ordenado) * PROPORCAO_TOP)
    return ordenado[:n_top], ordenado[n_top:]


def sortear_controle(top: list[dict], resto: list[dict], rng: random.Random) -> list[dict]:
    controle = []
    for faixa, n in sorted(Counter(r["faixa"] for r in top).items()):
        controle += rng.sample([r for r in resto if r["faixa"] == faixa], n)
    return controle


def main() -> None:
    base = list(csv.DictReader(open(RAIZ / "data" / "processed" / "base.csv")))

    # Etapa 1: sorteio original, com os perfis de referência ainda no ranking.
    ranking_original = [r for r in base if r["no_ranking"] == "True" or r["motivo_fora"] == "perfil_referencia"]
    top_original, resto_original = top_e_resto(ranking_original)
    controle_original = sortear_controle(top_original, resto_original, random.Random(SEMENTE))

    # Etapa 2: ranking final, sem os perfis de referência.
    ranking = [r for r in base if r["no_ranking"] == "True"]
    top, resto = top_e_resto(ranking)
    no_top = {r["shortCode"] for r in top}
    validos = {r["shortCode"] for r in resto}
    controle = [r for r in controle_original if r["shortCode"] in validos]

    rng = random.Random(SEMENTE_REPOSICAO)
    ja_no_controle = {r["shortCode"] for r in controle}
    final = []
    for faixa, n in sorted(Counter(r["faixa"] for r in top).items()):
        da_faixa = [r for r in controle if r["faixa"] == faixa][:n]
        faltam = n - len(da_faixa)
        if faltam > 0:
            candidatos = [r for r in resto if r["faixa"] == faixa and r["shortCode"] not in ja_no_controle]
            da_faixa += rng.sample(candidatos, faltam)
        final += da_faixa
    assert not no_top & {r["shortCode"] for r in final}

    destino = RAIZ / "data" / "processed" / "amostra.csv"
    campos = ["grupo"] + list(base[0])
    with open(destino, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows({"grupo": "top", **r} for r in top)
        w.writerows({"grupo": "controle", **r} for r in final)

    corte_top = float(top[-1]["taxa_engajamento"])
    repostos = len({r["shortCode"] for r in final} - {r["shortCode"] for r in controle_original})
    print(f"ranking {len(ranking)} | top {len(top)} (taxa >= {corte_top:.4%}) | controle {len(final)} "
          f"({repostos} repostos na etapa 2)")
    for nome, grupo in (("top", top), ("controle", final)):
        print(f"  {nome}: faixas {dict(Counter(r['faixa'] for r in grupo))}, "
              f"{len({r['perfil'] for r in grupo})} perfis")
    print(f"-> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
