"""Anota os Reels da amostra com o Gemini, usando a rubrica de scripts/rubrica.py.

Entrada por Reel: legenda + transcrição (data/midia/{shortCode}/transcricao.json) + 8 quadros.
Só anota Reels com mídia pronta e transcrição (ou sem áudio). Cada resposta é validada com
Pydantic e acrescentada a data/processed/anotacoes.jsonl; Reels já anotados com a mesma versão da
rubrica são pulados, então o script pode ser retomado. Erros de limite (429) esperam e tentam de novo.

Uso:
    .venv/bin/python scripts/anotar_gemini.py --piloto 20      # 10 top + 10 controle
    .venv/bin/python scripts/anotar_gemini.py
"""

import argparse
import csv
import json
import sys
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agente import midia  # noqa: E402
from agente.rubrica import VERSAO

RAIZ = Path(__file__).resolve().parent.parent
MIDIA = RAIZ / "data" / "midia"
SAIDA = RAIZ / "data" / "processed" / "anotacoes.jsonl"
MODELO_PADRAO = "gemini-3.5-flash-lite"


def pronto(sc: str) -> bool:
    pasta = MIDIA / sc
    meta = pasta / "meta.json"
    if not meta.exists():
        return False
    return (pasta / "transcricao.json").exists() or not json.loads(meta.read_text())["tem_audio"]


def anotar(client: genai.Client, modelo: str, reel: dict) -> dict:
    return midia.anotar(client, modelo, MIDIA / reel["shortCode"], reel["legenda"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=MODELO_PADRAO)
    parser.add_argument("--piloto", type=int, help="anota só N Reels, metade de cada grupo")
    parser.add_argument("--pausa", type=float, default=0.0, help="segundos entre requisições")
    args = parser.parse_args()

    load_dotenv(RAIZ / ".env")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    feitos = set()
    if SAIDA.exists():
        feitos = {(a["shortCode"], a["versao_rubrica"]) for a in map(json.loads, SAIDA.open())}
    amostra = list(csv.DictReader(open(RAIZ / "data" / "processed" / "amostra.csv")))
    fila = [r for r in amostra if (r["shortCode"], VERSAO) not in feitos and pronto(r["shortCode"])]
    if args.piloto:
        metade = args.piloto // 2
        fila = [r for r in fila if r["grupo"] == "top"][:metade] + [r for r in fila if r["grupo"] == "controle"][:metade]
    print(f"{len(fila)} Reels na fila ({len(feitos)} já anotados), modelo {args.modelo}")

    erros = 0
    with SAIDA.open("a") as f:
        for i, reel in enumerate(fila, 1):
            try:
                anot = anotar(client, args.modelo, reel)
            except (errors.APIError, ValidationError) as e:
                erros += 1
                print(f"  erro {reel['shortCode']}: {str(e)[:150]}")
                continue
            f.write(json.dumps({"shortCode": reel["shortCode"], "grupo": reel["grupo"], "modelo": args.modelo,
                                "versao_rubrica": VERSAO, **anot}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(fila)}")
            time.sleep(args.pausa)
    print(f"concluído: {len(fila) - erros} anotados, {erros} erros")


if __name__ == "__main__":
    main()
