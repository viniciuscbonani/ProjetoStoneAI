"""Imagens dos criativos geradas no Cloudflare Workers AI (FLUX.2 [klein] 4B), sob demanda.

Cada criativo tem a capa (índice 0) e uma imagem por cena (índices 1..n). A capa é gerada sem referência e
define a personagem; cada cena usa como referência só um recorte do rosto e do tronco da capa, com a mesma seed.
Testado em 16/11: com a capa inteira (ou a cena anterior) como referência, o modelo copia pose, enquadramento e
fundo, e todas as cenas saem iguais; com o recorte, mantém a pessoa e cria a cena pedida. Os prompts vêm prontos
do criativo (nos.prompts_imagem).

Cada imagem passa por um revisor com visão (Gemini flash-lite): anatomia, texto ou rabiscos na imagem, objetos
deformados, pose artificial, cena diferente do pedido, espaço livre no topo da capa e, nas cenas, se é a mesma
pessoa da capa. Reprovada, a imagem ganha uma segunda versão (outra seed, com os problemas no prompt); fica a de
maior nota. Mais tentativas não compensavam: o que o modelo não sabe fazer falha em todas. Se o revisor estiver fora do ar, a imagem segue sem revisão.

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
from pydantic import BaseModel, Field

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
    if recortar:  # rosto e ombros da capa: sem as mãos, para a cena não herdar os objetos que ela segura
        w, h = img.size
        img = img.crop((int(w * 0.2), int(h * 0.1), int(w * 0.8), int(h * 0.4)))
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


def gerar_do_criativo(run_id: str, criativo: int, indice: int, dados_criativo: dict) -> tuple[Path, dict | None]:
    """Gera a capa (indice 0) ou a cena `indice` do criativo, usando o recorte da capa já gerada como referência,
    e revisa; reprovada, tenta de novo (até MAX_TENTATIVAS). Devolve o arquivo e a revisão da imagem guardada."""
    from .nos import prompts_imagem  # import tardio: nos carrega o LangChain, desnecessário para servir imagens

    cenas = dados_criativo["roteiro"]
    pessoa = f"Personagem: {dados_criativo.get('personagem', '')}"
    if indice == 0:
        prompt = dados_criativo["prompt_capa"]
        pedido = f"Capa vertical do Reel. {pessoa}. Cena: {prompt.split('This image (Reel cover): ')[-1]}"
    elif 1 <= indice <= len(cenas):
        pedido = f"Cena {cenas[indice - 1]['tempo']} do Reel. {pessoa}. Cena: {cenas[indice - 1].get('visual') or cenas[indice - 1]['descricao']}"
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
    tentativas, melhor = [], None  # melhor = (nota, imagem, revisão)
    prompt_atual = prompt
    for t in range(MAX_TENTATIVAS):
        imagem = gerar(prompt_atual, referencias, seed + t, recortar=True)
        try:
            revisao = revisar(imagem, pedido, referencias[0] if referencias else None)
        except Exception as e:  # revisor fora do ar: a imagem segue sem revisão
            tentativas.append({"seed": seed + t, "revisao": None, "erro_revisor": repr(e)[:200]})
            melhor = (-1, imagem, None)
            break
        tentativas.append({"seed": seed + t, "revisao": revisao.model_dump()})
        if melhor is None or revisao.nota > melhor[0]:
            melhor = (revisao.nota, imagem, revisao)
        if revisao.aprovada:
            break
        prompt_atual = f"{prompt}\nAvoid these problems: {revisao.evitar or '; '.join(revisao.problemas)}"
    _, imagem, revisao = melhor
    destino = arquivo(run_id, criativo, indice)
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(imagem)).convert("RGB").save(destino, "JPEG", quality=90)
    resumo = revisao.model_dump() | {"tentativas": len(tentativas)} if revisao else None
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"quando": datetime.now().isoformat(timespec="seconds"), "run_id": run_id,
                            "criativo": criativo, "indice": indice, "modelo": MODELO_IMAGEM,
                            "referencias": [p.name for p in referencias], "seed": seed,
                            "duracao_s": round(time.time() - inicio, 1), "arquivo": destino.name,
                            "tentativas": tentativas, "revisao": resumo}, ensure_ascii=False) + "\n")
    return destino, resumo


def revisoes(run_id: str) -> dict[str, dict | None]:
    """Revisão da versão atual de cada imagem da execução (a última registrada no log), por nome de arquivo."""
    if not LOG.exists():
        return {}
    return {x["arquivo"]: x.get("revisao") for x in map(json.loads, LOG.open()) if x["run_id"] == run_id}


# ---------------------------------------------------------------- revisor de imagem

MODELO_REVISOR = os.environ.get("AGENTE_MODELO_REVISOR_IMAGEM", "gemini-3.5-flash-lite")
NOTA_MINIMA = 7

PROMPT_REVISOR = """Você revisa uma imagem gerada por IA para um criativo da @impulsostone (programa da Stone para
pequenos empreendedores), antes de a equipe usá-la. Ela deve parecer uma foto real e natural de um pequeno negócio.

A IMAGEM 1 é a que você avalia. O que ela deveria mostrar:
{pedido}
{sobre_referencia}
Reprove (aprovada = false) se a IMAGEM 1 tiver algum destes problemas:
- anatomia estranha: mãos, dedos, braços, rosto ou corpo deformados, a mais ou fora de proporção;
- texto inventado em destaque e em foco (letras sem sentido num papel, placa ou tela no centro da imagem),
  logotipos ou marcas d'água;
- objetos deformados, fundidos, flutuando ou sem sentido; móveis cortando a pessoa de forma estranha;
- cena muito diferente do pedido (ação ou objeto principal errado);
{criterio_pessoa}
Só tiram nota (não reprovam sozinhos): pose posada demais, detalhes pequenos e desfocados no fundo, pouco
espaço livre no topo{extra_capa}.
Dê nota de 0 a 10 para o quanto a IMAGEM 1 está pronta para uso e liste só os problemas reais, em frases curtas,
em português; em `evitar`, os mesmos problemas em inglês, curtos."""


MAX_TENTATIVAS = 2  # a original e uma segunda, corrigida pela revisão


class RevisaoImagem(BaseModel):
    aprovada: bool
    nota: int = Field(ge=0, le=10)
    problemas: list[str] = Field(default_factory=list, description="problemas concretos, em frases curtas")
    evitar: str = Field("", description="os mesmos problemas em inglês, curtos, para corrigir o prompt da imagem")


def revisar(imagem: bytes, pedido: str, referencia: Path | None = None) -> RevisaoImagem:
    """Revisa a imagem com o Gemini (visão). Nas cenas, compara com a capa para conferir se é a mesma pessoa."""
    from google import genai
    from google.genai import errors, types

    load_dotenv(RAIZ / ".env")
    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    texto = PROMPT_REVISOR.format(
        pedido=pedido,
        sobre_referencia=("\nA IMAGEM 2 é a capa do mesmo criativo e serve SÓ para conferir a pessoa; não avalie a cena "
                          "nem os objetos dela.\n" if referencia else ""),
        criterio_pessoa=("- a pessoa da IMAGEM 1 não é a mesma da IMAGEM 2 (rosto, cabelo ou roupa claramente diferentes)."
                         if referencia else ""),
        extra_capa="" if referencia else " (na capa, o ideal é a cabeça abaixo do terço de cima)")
    partes = [texto, "IMAGEM 1:", types.Part.from_bytes(data=imagem, mime_type="image/jpeg")]
    if referencia:
        partes += ["IMAGEM 2 (capa, só para conferir a pessoa):",
                   types.Part.from_bytes(data=referencia.read_bytes(), mime_type="image/jpeg")]
    for espera in (5, 15, None):  # 503 (modelo sobrecarregado) e 429 costumam passar com espera
        try:
            resp = cliente.models.generate_content(
                model=MODELO_REVISOR, contents=partes,
                config=types.GenerateContentConfig(response_mime_type="application/json",
                                                   response_schema=RevisaoImagem))
            break
        except errors.APIError as e:
            if e.code not in (429, 503) or espera is None:
                raise
            time.sleep(espera)
    revisao = RevisaoImagem.model_validate_json(resp.text)
    return revisao.model_copy(update={"aprovada": revisao.aprovada and revisao.nota >= NOTA_MINIMA})
