"""API HTTP do agente, usada pelo front (web/).

Rotas:
- POST /consultas: roda o agente (analisar | recomendar | gerar_criativo) e devolve a Saida
- GET /panorama: achados do lift e perfis em destaque, sem LLM
- GET /reels/{shortCode} e /reels/{shortCode}/quadros/{nome}: detalhe e quadros de um Reel da base
- GET /execucoes e /execucoes/{run_id}: histórico, lido do log do agente
- POST /imagens e GET /imagens/{run_id}: imagens dos criativos (Cloudflare Workers AI), geradas sob demanda
- POST /avaliacoes e GET /avaliacoes/{id}: modo avaliar (vídeo ou roteiro), em segundo plano, com progresso

Uso:
    .venv/bin/uvicorn agente.api:app --port 8000
"""

import io
import json
import re
import threading
import unicodedata
import uuid
import zipfile
from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from langchain_google_genai.chat_models import GoogleRateLimitError
from pydantic import BaseModel

from . import IMPLEMENTADOS, dados, executar, imagens
from .avaliacao import salvar_upload
from .contrato import Entrada, Saida
from .ferramentas import buscar_referencias, consultar_caracteristicas, perfis_em_destaque
from .registro import LOG

app = FastAPI(title="Agente Impulso Stone", version="0.1")
SHORTCODE = re.compile(r"^[A-Za-z0-9_-]{5,20}$")
QUADROS = ["gancho_0s", "gancho_1s", "gancho_2s", "gancho_3s", "meio_40", "meio_60", "final_2s", "final_0s"]


@app.get("/saude")
def saude() -> dict:
    from .nos import MODELO, MODELO_REDATOR
    return {"ok": True, "modos": sorted(IMPLEMENTADOS), "modelos": {"orquestrador": MODELO, "redator": MODELO_REDATOR}}


@app.post("/consultas", response_model=Saida)
def consultar(entrada: Entrada) -> Saida:
    if entrada.mode not in IMPLEMENTADOS:
        raise HTTPException(501, f"modo {entrada.mode} ainda não implementado")
    try:
        return executar(entrada)
    except GoogleRateLimitError:
        raise HTTPException(429, "cota diária do Gemini esgotada; ela zera por volta das 05h")


@app.get("/panorama")
def panorama(segmento: str | None = None, faixa: Annotated[list[str] | None, Query()] = None) -> dict:
    """Top x controle por característica, sem LLM. Com setor (segmento do público) ou tamanho do perfil, recalcula
    dentro do recorte (como a ferramenta do agente); num recorte o melhor selo é "fragil"."""
    return _panorama(segmento or None, tuple(sorted(faixa)) if faixa else None)


@app.get("/panorama/exemplos")
def panorama_exemplos(campo: str, valor: str, segmento: str | None = None,
                      faixa: Annotated[list[str] | None, Query()] = None, n: int = 6) -> list[dict]:
    """Reels do top com campo=valor (os mesmos critérios da busca do agente: por taxa, no máximo 2 por perfil)."""
    if campo not in dados.CAMPOS:
        raise HTTPException(404, "característica desconhecida")
    refs = buscar_referencias({campo: valor}, n=max(1, min(n, 12)), segmento=segmento or None, faixas=faixa or None)
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in refs]


@lru_cache(maxsize=64)
def _panorama(segmento: str | None, faixas: tuple[str, ...] | None) -> dict:
    reels = dados.filtrar(segmento=segmento, faixas=list(faixas) if faixas else None)
    if segmento or faixas:
        campos = sorted({a["campo"] for a in dados.achados()})
        achados = consultar_caracteristicas(campos, segmento=segmento, faixas=list(faixas) if faixas else None)
    else:
        achados = dados.achados()
    return {"totais": {"reels": len(reels), "top": sum(r["grupo"] == "top" for r in reels),
                       "perfis": len({r["perfil"] for r in reels})},
            "recorte": bool(segmento or faixas),
            "achados": achados, "perfis": perfis_em_destaque(20, segmento, list(faixas) if faixas else None)}


def _validar(short_code: str) -> dict:
    r = dados.reel(short_code) if SHORTCODE.match(short_code) else None
    if r is None:
        raise HTTPException(404, "Reel não encontrado na base")
    return r


@app.get("/reels/{short_code}")
def reel(short_code: str) -> dict:
    r = _validar(short_code)
    pasta = dados.RAIZ / "data" / "midia" / short_code
    return {**r, "quadros": [q for q in QUADROS if (pasta / f"q_{q}.jpg").exists()]}


@app.get("/reels/{short_code}/quadros/{nome}")
def quadro(short_code: str, nome: str) -> FileResponse:
    _validar(short_code)
    caminho = dados.RAIZ / "data" / "midia" / short_code / f"q_{nome}.jpg"
    if nome not in QUADROS or not caminho.exists():
        raise HTTPException(404, "quadro não encontrado")
    return FileResponse(caminho, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


def _log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.open() if l.strip()]


@app.get("/execucoes")
def execucoes(limite: int = 50) -> list[dict]:
    linhas = _log()[-limite:][::-1]
    return [{"run_id": l["run_id"], "quando": l["quando"], "mode": l["entrada"]["mode"],
             "query": l["entrada"]["query"], "segment": l["entrada"].get("segment"),
             "duracao_s": l["duracao_s"], "erro": l["erro"],
             "confidence_flag": (l["saida"] or {}).get("confidence_flag")} for l in linhas]


@app.get("/execucoes/{run_id}")
def execucao(run_id: str) -> dict:
    for l in reversed(_log()):
        if l["run_id"] == run_id:
            return l
    raise HTTPException(404, "execução não encontrada")


class PedidoImagem(BaseModel):
    run_id: str
    criativo: int  # 1 a 3
    indice: int  # 0 = capa; 1..n = cenas do roteiro


@app.post("/imagens")
def gerar_imagem(pedido: PedidoImagem) -> dict:
    """Gera uma imagem do criativo. O front pede na ordem (capa, cena 1, cena 2...), porque cada cena usa a capa
    e a cena anterior como referência."""
    saida = execucao(pedido.run_id).get("saida") or {}
    criativos = saida.get("creatives") or []
    if not 1 <= pedido.criativo <= len(criativos):
        raise HTTPException(404, "criativo não encontrado nesta execução")
    try:
        caminho, revisao = imagens.gerar_do_criativo(pedido.run_id, pedido.criativo, pedido.indice,
                                                     criativos[pedido.criativo - 1])
    except imagens.SemCredenciais as e:
        raise HTTPException(503, f"geração de imagem indisponível: {e}")
    except (IndexError, ValueError) as e:
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"indice": pedido.indice, "url": f"/imagens/{pedido.run_id}/{caminho.name}", "revisao": revisao}


RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")
ARQUIVO_IMAGEM = re.compile(r"^criativo[1-9]_(capa|cena[0-9]{1,2})\.jpg$")


@app.get("/imagens/{run_id}")
def imagens_da_execucao(run_id: str) -> dict[str, dict]:
    """Imagens já geradas de uma execução, por nome (criativo1_capa, criativo1_cena2...), com a revisão."""
    if not RUN_ID.match(run_id):
        raise HTTPException(404, "execução não encontrada")
    pasta = imagens.PASTA / run_id
    if not pasta.exists():
        return {}
    revisoes = imagens.revisoes(run_id)
    return {p.stem: {"url": f"/imagens/{run_id}/{p.name}", "revisao": revisoes.get(p.name)}
            for p in sorted(pasta.glob("*.jpg"))}


@app.get("/imagens/{run_id}/{nome}")
def imagem(run_id: str, nome: str) -> FileResponse:
    caminho = imagens.PASTA / run_id / nome
    if not RUN_ID.match(run_id) or not ARQUIVO_IMAGEM.match(nome) or not caminho.exists():
        raise HTTPException(404, "imagem não encontrada")
    return FileResponse(caminho, media_type="image/jpeg")


def _criativo_em_texto(c: dict) -> str:
    cenas = [f"{cena['tempo']}: {cena['descricao']}" + (f" [na tela: {cena['texto_na_tela']}]" if cena.get("texto_na_tela") else "")
             for cena in c["roteiro"]]
    return "\n".join([
        c["titulo"], f"{c['formato']} · {c['duracao_alvo']}", "", f"GANCHO: {c['gancho']}", "", "ROTEIRO:", *cenas,
        "", f"LEGENDA:\n{c['legenda']}", "", f"CTA: {c['cta']}", "",
        "Inspirado em: " + " ".join(f"https://www.instagram.com/reel/{s}/" for s in c["inspirado_em"]),
        "Achados usados: " + "; ".join(c["achados_usados"]), "",
    ])


@app.get("/execucoes/{run_id}/criativos/{n}.zip")
def baixar_criativo(run_id: str, n: int) -> Response:
    """O criativo n em .zip: o texto (gancho, roteiro, legenda, CTA e Reels de inspiração), o prompt das imagens e
    as imagens já geradas (capa.jpg, cena1.jpg...)."""
    if not RUN_ID.match(run_id):
        raise HTTPException(404, "execução não encontrada")
    criativos = (execucao(run_id).get("saida") or {}).get("creatives") or []
    if not 1 <= n <= len(criativos):
        raise HTTPException(404, "criativo não encontrado nesta execução")
    c = criativos[n - 1]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("criativo.txt", _criativo_em_texto(c))
        if c.get("prompt_copiar"):
            z.writestr("prompt-imagens.txt", c["prompt_copiar"])
        for img in sorted((imagens.PASTA / run_id).glob(f"criativo{n}_*.jpg")):
            z.write(img, img.name.removeprefix(f"criativo{n}_"))
    nome = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", c["titulo"]).encode("ascii", "ignore").decode().lower())
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="criativo-{n}-{nome.strip("-")[:40]}.zip"'})


# ---------------------------------------------------------------- avaliar (em segundo plano)

# O aviso chega quando um nó termina; a tela mostra a etapa seguinte, que é a que está rodando.
PROXIMA_ETAPA = {"ler": "Comparando com os achados da base", "comparar": "Escrevendo os pontos fortes e a melhorar",
                 "avaliador": "Revisando", "revisor": "Finalizando", "montar_saida": "Pronto"}
TAMANHO_MAXIMO = 300 * 1024 * 1024
_avaliacoes: dict[str, dict] = {}
_trava = threading.Lock()


def _rodar_avaliacao(id_: str, entrada: dict) -> None:
    def avancar(no: str) -> None:
        with _trava:
            _avaliacoes[id_]["etapa"] = PROXIMA_ETAPA.get(no, no)

    with _trava:
        _avaliacoes[id_]["etapa"] = ("Lendo o vídeo: quadros, transcrição e rubrica (1 a 3 min)"
                                     if entrada.get("video_path") else "Lendo o roteiro")
    try:
        saida = executar(entrada, ao_avancar=avancar)
        with _trava:
            _avaliacoes[id_].update(pronto=True, etapa="Pronto", saida=saida.model_dump(mode="json"))
    except Exception as e:  # o erro vai para a tela e para o log do agente
        with _trava:
            _avaliacoes[id_].update(pronto=True, erro=f"{type(e).__name__}: {str(e)[:300]}")


@app.post("/avaliacoes")
def criar_avaliacao(query: str = Form("Avaliar meu vídeo"), segment: str | None = Form(None),
                    roteiro: str | None = Form(None), arquivo: UploadFile | None = File(None)) -> dict:
    """Recebe um vídeo (arquivo) ou um roteiro em texto e começa a avaliação; o front consulta o progresso em
    GET /avaliacoes/{id}. A leitura do vídeo leva de 1 a 3 minutos (transcrição local + Gemini)."""
    entrada = {"mode": "avaliar", "query": query or "Avaliar meu vídeo", "segment": segment or None}
    if arquivo is not None and arquivo.filename:
        conteudo = arquivo.file.read(TAMANHO_MAXIMO + 1)
        if len(conteudo) > TAMANHO_MAXIMO:
            raise HTTPException(413, "vídeo maior que 300 MB")
        entrada["video_path"] = str(salvar_upload(arquivo.filename, conteudo))
    elif roteiro and roteiro.strip():
        entrada["roteiro"] = roteiro
    else:
        raise HTTPException(422, "envie um vídeo ou um roteiro")
    try:
        Entrada.model_validate(entrada)
    except ValueError as e:
        raise HTTPException(422, str(e))
    id_ = uuid.uuid4().hex[:12]
    with _trava:
        _avaliacoes[id_] = {"id": id_, "pronto": False, "etapa": "Na fila", "erro": None, "saida": None,
                            "fonte": "video" if "video_path" in entrada else "roteiro"}
    threading.Thread(target=_rodar_avaliacao, args=(id_, entrada), daemon=True).start()
    return {"id": id_}


@app.get("/avaliacoes/{id_}")
def ver_avaliacao(id_: str) -> dict:
    with _trava:
        if id_ not in _avaliacoes:
            raise HTTPException(404, "avaliação não encontrada (a API pode ter sido reiniciada)")
        return dict(_avaliacoes[id_])
