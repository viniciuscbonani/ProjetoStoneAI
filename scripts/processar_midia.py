"""Baixa os vídeos da amostra, extrai o que o Gemini precisa e apaga o vídeo.

Para cada Reel de data/processed/amostra.csv:
1. baixa o vídeo pelo link novo (os links da coleta expiram em poucas horas)
2. extrai com ffmpeg:
   - áudio mono 16 kHz (audio.m4a), para a transcrição
   - quadros estratégicos: gancho (0, 1, 2 e 3 s), meio (40% e 60%) e final (2 s e 0,5 s antes do fim)
   - número de cortes, por detecção de troca de cena
3. apaga o vídeo

Saída em data/midia/{shortCode}/ (audio.m4a, q_*.jpg, meta.json). Reels com meta.json já
existente são pulados, então o script pode ser retomado.

Os links novos vêm de uma nova execução do esdrasdw só com os perfis da amostra (o actor não
aceita links de Reels individuais); custa uns US$ 0,40.

Uso:
    .venv/bin/python scripts/processar_midia.py --limite 3   # teste
    .venv/bin/python scripts/processar_midia.py
"""

import argparse
import csv
import json
import os
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal
from pathlib import Path

import imageio_ffmpeg
from apify_client import ApifyClient
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
MIDIA = RAIZ / "data" / "midia"
LINKS = RAIZ / "data" / "interim" / f"links_videos_{date.today().isoformat()}.json"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
LIMIAR_CENA = 0.3
DOWNLOADS_SIMULTANEOS = 6


def instantes(duracao: float) -> dict[str, float]:
    fim = max(duracao, 1.0)
    pontos = {"gancho_0s": 0.0, "gancho_1s": 1.0, "gancho_2s": 2.0, "gancho_3s": 3.0,
              "meio_40": 0.4 * fim, "meio_60": 0.6 * fim,
              "final_2s": fim - 2.0, "final_0s": fim - 0.5}
    return {k: round(min(max(t, 0.0), fim - 0.1), 2) for k, t in pontos.items()}


def links_novos(amostra: list[dict]) -> dict[str, str]:
    if LINKS.exists():
        return json.loads(LINKS.read_text())
    load_dotenv(RAIZ / ".env")
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    perfis = sorted({r["perfil"] for r in amostra})
    run = client.actor("esdrasdw/instagram-content-scraper").call(
        run_input={"directUrls": perfis, "resultsType": "reels", "resultsLimit": 100,
                   "onlyPostsNewerThan": "2025-11-14", "skipPinnedPosts": True,
                   "selectedFields": ["shortCode", "videoUrl"]},
        max_total_charge_usd=Decimal("0.80"), logger=None,
    )
    itens = client.dataset(run.default_dataset_id).list_items(clean=True).items
    links = {x["shortCode"]: x["videoUrl"] for x in itens if x.get("videoUrl")}
    LINKS.write_text(json.dumps(links))
    with open(RAIZ / "data" / "raw" / "coletas.csv", "a", newline="") as f:
        csv.writer(f).writerow([date.today().isoformat(), "principal", "esdrasdw/instagram-content-scraper",
                                run.id, run.default_dataset_id, f"{len(perfis)} perfis da amostra",
                                "so shortCode e videoUrl", len(itens), round(float(run.usage_total_usd or 0), 4),
                                "links novos para download"])
    return links


def ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([FFMPEG, "-hide_banner", "-y", *args], capture_output=True, text=True)


def processar(reel: dict, url: str) -> dict:
    pasta = MIDIA / reel["shortCode"]
    pasta.mkdir(parents=True, exist_ok=True)
    video = pasta / "video.mp4"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(video, "wb") as f:
        f.write(r.read())

    try:
        ffmpeg("-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "48k", str(pasta / "audio.m4a"))
        quadros = {}
        for nome, t in instantes(float(reel["duracao_s"] or 0)).items():
            saida = pasta / f"q_{nome}.jpg"
            ffmpeg("-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale=-2:640", "-q:v", "4", str(saida))
            if saida.exists():
                quadros[nome] = t
        cenas = ffmpeg("-i", str(video), "-vf", f"select='gt(scene,{LIMIAR_CENA})',showinfo", "-an", "-f", "null", "-")
        cortes = len(re.findall(r"pts_time:", cenas.stderr))
        meta = {"shortCode": reel["shortCode"], "duracao_s": float(reel["duracao_s"] or 0),
                "quadros": quadros, "cortes": cortes, "tem_audio": (pasta / "audio.m4a").exists()}
        (pasta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
        return meta
    finally:
        video.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, help="processa só os N primeiros (teste)")
    parser.add_argument("--workers", type=int, default=DOWNLOADS_SIMULTANEOS, help="Reels processados em paralelo")
    parser.add_argument("--links", type=Path, help="JSON {shortCode: videoUrl} já coletado (ex.: saída de coleta_comentarios.py)")
    args = parser.parse_args()

    amostra = list(csv.DictReader(open(RAIZ / "data" / "processed" / "amostra.csv")))
    links = json.loads(args.links.read_text()) if args.links else links_novos(amostra)
    fila = [r for r in amostra if not (MIDIA / r["shortCode"] / "meta.json").exists()]
    print(f"{len(amostra) - len(fila)} já processados, {len(fila)} pendentes")
    if args.limite:
        fila = fila[:args.limite]

    falhas = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tarefas = {}
        for r in fila:
            if r["shortCode"] not in links:
                falhas.append((r["shortCode"], "sem link novo (Reel apagado ou fora da coleta)"))
                continue
            tarefas[pool.submit(processar, r, links[r["shortCode"]])] = r["shortCode"]
        for i, t in enumerate(as_completed(tarefas), 1):
            sc = tarefas[t]
            try:
                t.result()
            except Exception as e:  # um Reel com erro não derruba o lote
                falhas.append((sc, str(e)[:200]))
            if i % 50 == 0:
                print(f"  {i}/{len(tarefas)}")

    with open(MIDIA / "_falhas.csv", "a", newline="") as f:
        csv.writer(f).writerows(falhas)
    ok = sum(1 for r in amostra if (MIDIA / r["shortCode"] / "meta.json").exists())
    print(f"{ok}/{len(amostra)} Reels processados, {len(falhas)} falhas nesta rodada")


if __name__ == "__main__":
    main()
