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
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from rubrica import PROMPT, VERSAO, Anotacao

RAIZ = Path(__file__).resolve().parent.parent
MIDIA = RAIZ / "data" / "midia"
SAIDA = RAIZ / "data" / "processed" / "anotacoes.jsonl"
MODELO_PADRAO = "gemini-3.5-flash-lite"
ESPERA_429 = [30, 60, 120, 300]


def pronto(sc: str) -> bool:
    pasta = MIDIA / sc
    meta = pasta / "meta.json"
    if not meta.exists():
        return False
    return (pasta / "transcricao.json").exists() or not json.loads(meta.read_text())["tem_audio"]


def montar_conteudo(reel: dict) -> list:
    pasta = MIDIA / reel["shortCode"]
    meta = json.loads((pasta / "meta.json").read_text())
    trans = json.loads((pasta / "transcricao.json").read_text()) if (pasta / "transcricao.json").exists() else {}
    texto = (f"{PROMPT}\n\nDuração: {meta['duracao_s']:.0f} s\n"
             f"Legenda: {reel['legenda'] or '(sem legenda)'}\n"
             f"Fala nos 3 primeiros segundos: {trans.get('gancho_falado') or '(sem fala)'}\n"
             f"Transcrição completa: {trans.get('texto') or '(sem fala)'}\n\nQuadros:")
    partes = [texto]
    for nome, t in meta["quadros"].items():
        partes.append(f"[{nome}, {t:.1f} s]")
        partes.append(types.Part.from_bytes(data=(pasta / f"q_{nome}.jpg").read_bytes(), mime_type="image/jpeg"))
    return partes


def anotar(client: genai.Client, modelo: str, reel: dict) -> dict:
    for espera in ESPERA_429 + [None]:
        try:
            resp = client.models.generate_content(
                model=modelo, contents=montar_conteudo(reel),
                config=types.GenerateContentConfig(response_mime_type="application/json",
                                                   response_schema=Anotacao, temperature=0),
            )
            anot = Anotacao.model_validate_json(resp.text)
            return anot.model_dump()
        except errors.APIError as e:
            # 429 = limite de cota por minuto; 503 = modelo sobrecarregado. Os dois passam com espera.
            if e.code not in (429, 503) or espera is None:
                raise
            print(f"  {e.code}, esperando {espera}s")
            time.sleep(espera)
    raise RuntimeError("inalcançável")


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
