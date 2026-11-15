"""Transcreve o áudio dos Reels da amostra com faster-whisper (local, CPU).

Lê data/midia/{shortCode}/audio.m4a e grava transcricao.json ao lado, com o texto completo,
os segmentos com tempo e o texto falado nos 3 primeiros segundos (gancho). O filtro de voz
(VAD) pula trechos só de música; Reels sem fala ficam com texto vazio e sem_fala = true.
Reels já transcritos são pulados, então o script pode ser retomado.

Para usar mais núcleos, rode vários processos, cada um com uma parte da fila:
    .venv/bin/python scripts/transcrever.py --parte 0 --partes 4 --threads 3 &
    .venv/bin/python scripts/transcrever.py --parte 1 --partes 4 --threads 3 &
    ...

Uso:
    .venv/bin/python scripts/transcrever.py --limite 5
    .venv/bin/python scripts/transcrever.py --modelo medium
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from faster_whisper import WhisperModel

RAIZ = Path(__file__).resolve().parent.parent
MIDIA = RAIZ / "data" / "midia"
SEGUNDOS_GANCHO = 3.0
TAXA = 16000


def carregar_audio(caminho: Path) -> np.ndarray:
    # Decodifica com o ffmpeg do projeto: a versão do PyAV instalada não é compatível com o
    # decodificador embutido do faster-whisper.
    bruto = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(caminho), "-f", "f32le", "-ac", "1", "-ar", str(TAXA), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(bruto, dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default="small", help="small (~1 GB de RAM) ou medium (~2,5 GB)")
    parser.add_argument("--limite", type=int)
    parser.add_argument("--parte", type=int, default=0, help="índice deste processo (0 a partes-1)")
    parser.add_argument("--partes", type=int, default=1, help="número de processos em paralelo")
    parser.add_argument("--threads", type=int, default=4, help="núcleos de CPU por processo")
    args = parser.parse_args()

    todos = sorted(p.parent for p in MIDIA.glob("*/audio.m4a"))
    fila = [p for i, p in enumerate(todos) if i % args.partes == args.parte and not (p / "transcricao.json").exists()]
    if args.limite:
        fila = fila[:args.limite]
    print(f"parte {args.parte}/{args.partes}: {len(fila)} áudios na fila, modelo {args.modelo}")

    modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8", cpu_threads=args.threads)
    inicio = time.time()
    for i, pasta in enumerate(fila, 1):
        segmentos, info = modelo.transcribe(carregar_audio(pasta / "audio.m4a"), language="pt", vad_filter=True, beam_size=1)
        segs = [{"inicio": round(s.start, 2), "fim": round(s.end, 2), "texto": s.text.strip()} for s in segmentos]
        texto = " ".join(s["texto"] for s in segs).strip()
        gancho = " ".join(s["texto"] for s in segs if s["inicio"] < SEGUNDOS_GANCHO).strip()
        (pasta / "transcricao.json").write_text(json.dumps({
            "shortCode": pasta.name, "modelo": args.modelo, "duracao_audio_s": round(info.duration, 1),
            "sem_fala": not texto, "texto": texto, "gancho_falado": gancho, "segmentos": segs,
        }, ensure_ascii=False))
        if i % 25 == 0 or i == len(fila):
            ritmo = (time.time() - inicio) / i
            print(f"  {i}/{len(fila)} ({ritmo:.1f} s por áudio, faltam ~{ritmo * (len(fila) - i) / 60:.0f} min)")


if __name__ == "__main__":
    main()
