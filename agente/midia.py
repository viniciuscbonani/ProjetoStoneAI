"""Leitura de um vídeo: quadros, cortes, áudio, transcrição e anotação pela rubrica.

As mesmas funções servem ao pipeline da amostra (processar_midia.py, transcrever.py, anotar_gemini.py) e ao
modo avaliar do agente, para que um vídeo enviado seja lido exatamente como os Reels da base.

Saída numa pasta por vídeo: audio.m4a, q_*.jpg (8 quadros), meta.json e transcricao.json.
"""

import json
import re
import subprocess
import time
from functools import cache
from pathlib import Path

import imageio_ffmpeg
import numpy as np

from .rubrica import PROMPT, Anotacao

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
LIMIAR_CENA = 0.3
SEGUNDOS_GANCHO = 3.0
TAXA = 16000
ESPERA_429 = [30, 60, 120, 300]


def ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([FFMPEG, "-hide_banner", "-y", *args], capture_output=True, text=True)


def duracao(video: Path) -> float:
    """Duração em segundos, lida do cabeçalho pelo ffmpeg (não há ffprobe no ambiente)."""
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", ffmpeg("-i", str(video)).stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def instantes(duracao_s: float) -> dict[str, float]:
    """Quadros estratégicos: gancho (0, 1, 2 e 3 s), meio (40% e 60%) e final (2 s e 0,5 s antes do fim)."""
    fim = max(duracao_s, 1.0)
    pontos = {"gancho_0s": 0.0, "gancho_1s": 1.0, "gancho_2s": 2.0, "gancho_3s": 3.0,
              "meio_40": 0.4 * fim, "meio_60": 0.6 * fim,
              "final_2s": fim - 2.0, "final_0s": fim - 0.5}
    return {k: round(min(max(t, 0.0), fim - 0.1), 2) for k, t in pontos.items()}


def extrair(video: Path, pasta: Path, duracao_s: float | None = None) -> dict:
    """Áudio mono 16 kHz, os 8 quadros e o número de cortes (troca de cena); grava meta.json."""
    pasta.mkdir(parents=True, exist_ok=True)
    duracao_s = duracao_s or duracao(video)
    ffmpeg("-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "48k", str(pasta / "audio.m4a"))
    quadros = {}
    for nome, t in instantes(duracao_s).items():
        saida = pasta / f"q_{nome}.jpg"
        ffmpeg("-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale=-2:640", "-q:v", "4", str(saida))
        if saida.exists():
            quadros[nome] = t
    cenas = ffmpeg("-i", str(video), "-vf", f"select='gt(scene,{LIMIAR_CENA})',showinfo", "-an", "-f", "null", "-")
    meta = {"shortCode": pasta.name, "duracao_s": duracao_s, "quadros": quadros,
            "cortes": len(re.findall(r"pts_time:", cenas.stderr)), "tem_audio": (pasta / "audio.m4a").exists()}
    (pasta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    return meta


def carregar_audio(caminho: Path) -> np.ndarray:
    # Decodifica com o ffmpeg do projeto: a versão do PyAV instalada não é compatível com o
    # decodificador embutido do faster-whisper.
    bruto = subprocess.run([FFMPEG, "-i", str(caminho), "-f", "f32le", "-ac", "1", "-ar", str(TAXA), "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(bruto, dtype=np.float32)


@cache
def whisper(modelo: str = "small", threads: int = 4):
    from faster_whisper import WhisperModel
    return WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=threads)


def transcrever(pasta: Path, modelo=None, nome_modelo: str = "small") -> dict:
    """Transcreve audio.m4a (pt, com filtro de voz) e grava transcricao.json com o texto completo, os
    segmentos e a fala dos 3 primeiros segundos (gancho)."""
    modelo = modelo or whisper(nome_modelo)
    segmentos, info = modelo.transcribe(carregar_audio(pasta / "audio.m4a"), language="pt", vad_filter=True,
                                        beam_size=1)
    segs = [{"inicio": round(s.start, 2), "fim": round(s.end, 2), "texto": s.text.strip()} for s in segmentos]
    texto = " ".join(s["texto"] for s in segs).strip()
    transcricao = {"shortCode": pasta.name, "modelo": nome_modelo, "duracao_audio_s": round(info.duration, 1),
                   "sem_fala": not texto, "texto": texto,
                   "gancho_falado": " ".join(s["texto"] for s in segs if s["inicio"] < SEGUNDOS_GANCHO).strip(),
                   "segmentos": segs}
    (pasta / "transcricao.json").write_text(json.dumps(transcricao, ensure_ascii=False))
    return transcricao


def montar_conteudo(pasta: Path, legenda: str) -> list:
    """Prompt da rubrica + legenda + transcrição + os 8 quadros, como na anotação da amostra."""
    from google.genai import types

    meta = json.loads((pasta / "meta.json").read_text())
    trans = json.loads((pasta / "transcricao.json").read_text()) if (pasta / "transcricao.json").exists() else {}
    texto = (f"{PROMPT}\n\nDuração: {meta['duracao_s']:.0f} s\n"
             f"Legenda: {legenda or '(sem legenda)'}\n"
             f"Fala nos 3 primeiros segundos: {trans.get('gancho_falado') or '(sem fala)'}\n"
             f"Transcrição completa: {trans.get('texto') or '(sem fala)'}\n\nQuadros:")
    partes = [texto]
    for nome, t in meta["quadros"].items():
        partes.append(f"[{nome}, {t:.1f} s]")
        partes.append(types.Part.from_bytes(data=(pasta / f"q_{nome}.jpg").read_bytes(), mime_type="image/jpeg"))
    return partes


def _anotar_partes(client, modelo: str, partes: list) -> dict:
    import httpx2
    from google.genai import errors, types

    for espera in ESPERA_429 + [None]:
        try:
            resp = client.models.generate_content(
                model=modelo, contents=partes,
                config=types.GenerateContentConfig(response_mime_type="application/json",
                                                   response_schema=Anotacao, temperature=0),
            )
            return Anotacao.model_validate_json(resp.text).model_dump()
        except (errors.APIError, httpx2.TimeoutException) as e:
            # 429 = limite de cota por minuto; 503 = modelo sobrecarregado; tempo esgotado (cliente com timeout)
            # costuma vir junto do 503. Os três passam com espera.
            codigo = getattr(e, "code", "tempo esgotado")
            if codigo not in (429, 503, "tempo esgotado") or espera is None:
                raise
            print(f"  {codigo}, esperando {espera}s")
            time.sleep(espera)
    raise RuntimeError("inalcançável")


def anotar(client, modelo: str, pasta: Path, legenda: str = "") -> dict:
    """Anota o vídeo da pasta com a rubrica (Gemini)."""
    return _anotar_partes(client, modelo, montar_conteudo(pasta, legenda))


def anotar_roteiro(client, modelo: str, roteiro: str) -> dict:
    """Anota um roteiro em texto, sem vídeo. Campos visuais (rosto, texto na tela, gancho visual) saem como
    estimativa do modelo e não devem ser usados na avaliação."""
    partes = [f"{PROMPT}\n\nATENÇÃO: não há vídeo, só o ROTEIRO abaixo, ainda não gravado. Trate a primeira fala "
              f"ou cena como o gancho e estime o resto a partir do texto.\n\nRoteiro:\n{roteiro}"]
    return _anotar_partes(client, modelo, partes)
