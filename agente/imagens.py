"""Imagens dos criativos geradas no Cloudflare Workers AI (FLUX.2 [klein] 4B), sob demanda.

Cada criativo tem a capa (índice 0) e uma imagem por cena (índices 1..n). A capa é gerada sem referência e
define a personagem; cada cena usa como referência só um recorte do rosto e do tronco da capa, com a mesma seed.
Testado em 16/11: com a capa inteira (ou a cena anterior) como referência, o modelo copia pose, enquadramento e
fundo, e todas as cenas saem iguais; com o recorte, mantém a pessoa e cria a cena pedida. Os prompts vêm prontos
do criativo (nos.prompts_imagem).

Credenciais no .env: CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN (token com permissão de Workers AI).
O plano grátis dá 10.000 neurons/dia; uma imagem 864×1536 custa ~130 neurons (~140 com o recorte de
referência), ou seja, uns 10 criativos completos por dia. Imagens em data/imagens/{run_id}/ (fora do Git); cada geração
vai para data/logs/imagens.jsonl.
"""

import base64
import hashlib
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image

from .dados import RAIZ

MODELO_IMAGEM = os.environ.get("AGENTE_MODELO_IMAGEM", "@cf/black-forest-labs/flux-2-klein-4b")
LARGURA, ALTURA = 864, 1536  # 9:16, múltiplos de 16 (exigência do FLUX)
LADO_REFERENCIA = 384  # o klein aceita referências menores que 512×512; menores também custam menos
PASTA = RAIZ / "data" / "imagens"
LOG = RAIZ / "data" / "logs" / "imagens.jsonl"


class SemCredenciais(RuntimeError):
    pass


def _credenciais() -> tuple[str, str]:
    load_dotenv(RAIZ / ".env")
    conta, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not conta or not token:
        raise SemCredenciais("faltam CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN no .env")
    return conta, token


def _referencia(caminho: Path, recortar: bool = False) -> bytes:
    img = Image.open(caminho).convert("RGB")
    if recortar:  # rosto e tronco da capa (o estilo deixa o terço de cima livre, então a pessoa fica no meio)
        w, h = img.size
        img = img.crop((int(w * 0.15), int(h * 0.15), int(w * 0.85), int(h * 0.50)))
    img.thumbnail((LADO_REFERENCIA, LADO_REFERENCIA))
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=85)
    return saida.getvalue()


def gerar(prompt: str, referencias: list[Path], seed: int, recortar: bool = False) -> bytes:
    """Uma imagem 9:16 a partir do prompt e de até 4 imagens de referência (recortadas, se pedido)."""
    conta, token = _credenciais()
    campos = {"prompt": (None, prompt), "width": (None, str(LARGURA)), "height": (None, str(ALTURA)),
              "seed": (None, str(seed))}
    for i, ref in enumerate(referencias[:4]):
        campos[f"input_image_{i}"] = (ref.name, _referencia(ref, recortar), "image/jpeg")
    resp = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO_IMAGEM}",
                      headers={"Authorization": f"Bearer {token}"}, files=campos, timeout=180)
    corpo = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200 or not corpo.get("success"):
        erros = "; ".join(e.get("message", str(e)) for e in corpo.get("errors", [])) or resp.text[:200]
        raise RuntimeError(f"Cloudflare respondeu {resp.status_code}: {erros}")
    return base64.b64decode(corpo["result"]["image"])


def arquivo(run_id: str, criativo: int, indice: int) -> Path:
    nome = "capa" if indice == 0 else f"cena{indice}"
    return PASTA / run_id / f"criativo{criativo}_{nome}.jpg"


def gerar_do_criativo(run_id: str, criativo: int, indice: int, dados_criativo: dict) -> Path:
    """Gera a capa (indice 0) ou a cena `indice` do criativo, usando o recorte da capa já gerada como referência.
    A seed é a mesma em todo o criativo."""
    from .nos import prompts_imagem  # import tardio: nos carrega o LangChain, desnecessário para servir imagens

    cenas = dados_criativo["roteiro"]
    if indice == 0:
        prompt = dados_criativo["prompt_capa"]
    elif 1 <= indice <= len(cenas):
        # Remonta o prompt da cena com a redação atual (vale também para criativos gerados antes de mudanças).
        visual = cenas[indice - 1].get("visual")
        prompt = (prompts_imagem(dados_criativo["personagem"], "", [("", visual)])[1][0]
                  if visual and dados_criativo.get("personagem") else cenas[indice - 1]["prompt_imagem"])
    else:
        raise IndexError(f"o criativo tem capa (0) e cenas de 1 a {len(cenas)}")
    if not prompt:
        raise ValueError("este criativo não tem prompts de imagem (foi gerado antes dessa função existir)")
    capa = arquivo(run_id, criativo, 0)
    referencias = [capa] if indice > 0 and capa.exists() else []
    seed = int(hashlib.sha256(f"{run_id}/{criativo}".encode()).hexdigest(), 16) % 2**31
    inicio = time.time()
    imagem = gerar(prompt, referencias, seed, recortar=True)
    destino = arquivo(run_id, criativo, indice)
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(imagem)).convert("RGB").save(destino, "JPEG", quality=90)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"quando": datetime.now().isoformat(timespec="seconds"), "run_id": run_id,
                            "criativo": criativo, "indice": indice, "modelo": MODELO_IMAGEM,
                            "referencias": [p.name for p in referencias], "seed": seed,
                            "duracao_s": round(time.time() - inicio, 1), "arquivo": destino.name},
                           ensure_ascii=False) + "\n")
    return destino
