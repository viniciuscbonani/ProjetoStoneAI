"""Mede a concordância entre as anotações do Gemini e uma anotação de referência, por campo.

A referência é um JSON {shortCode: {campo: valor}} exportado da página de validação
(data/interim/validacao.html): data/interim/validacao_claude.json, a validação cruzada por outro modelo
(o Claude), às cegas.

Para cada campo: % de concordância e kappa de Cohen (concordância corrigida pelo acaso). Leitura usual
do kappa: < 0,4 fraca, 0,4–0,6 moderada, 0,6–0,8 boa, > 0,8 muito boa.

Uso:
    .venv/bin/python scripts/concordancia.py data/interim/validacao_claude.json
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def normalizar(v) -> str:
    return {True: "sim", False: "nao"}.get(v, str(v))


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def leitura(k: float) -> str:
    return "fraca" if k < 0.4 else "moderada" if k < 0.6 else "boa" if k < 0.8 else "muito boa"


def main(caminho: str) -> None:
    ref = json.loads(Path(caminho).read_text())
    gemini = {a["shortCode"]: a for a in map(json.loads, open(RAIZ / "data" / "processed" / "anotacoes.jsonl"))
              if a["versao_rubrica"] == "v2"}
    campos = sorted({c for v in ref.values() for c in v})
    linhas = []
    for c in campos:
        pares = [(normalizar(gemini[sc][c]), v[c]) for sc, v in ref.items() if c in v and sc in gemini]
        g, r = [p[0] for p in pares], [p[1] for p in pares]
        k = kappa(g, r)
        linhas.append({"campo": c, "n": len(pares), "concordancia": round(sum(x == y for x, y in pares) / len(pares), 3),
                       "kappa": round(k, 2), "leitura": leitura(k)})

    destino = RAIZ / "data" / "processed" / f"concordancia_{Path(caminho).stem}.csv"
    with open(destino, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    for l in sorted(linhas, key=lambda l: -l["kappa"]):
        print(f"  {l['campo']:<28} {l['concordancia']:>6.0%}  kappa {l['kappa']:>5}  ({l['leitura']}, n={l['n']})")
    print(f"-> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main(sys.argv[1])
