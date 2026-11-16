"""Modo avaliar: o vídeo (ou roteiro) da pessoa comparado aos achados da base.

ler → comparar → avaliador → revisor → montar_saida

- ler: lê o vídeo como os Reels da amostra (agente/midia.py: quadros, cortes, transcrição e rubrica v2);
  um roteiro em texto passa só pela rubrica, com a duração estimada pelo número de palavras.
- comparar: por código, cruza cada característica lida com os achados. O que o vídeo tem e aparece mais no
  top (diferença clara ou indício) é ponto forte; o que aparece menos no top, ou a falta de algo que aparece
  mais, é ponto a melhorar; o que o vídeo tem, mas não diferencia o top, vai para "sem efeito". Cada ponto
  leva Reels de exemplo buscados na base.
- avaliador: o LLM só redige o texto de cada ponto (a lista e os números vêm do código).
Não há nota de engajamento: modelo preditivo está fora do escopo; fala-se em aderência aos padrões observados.
"""

import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from . import dados, midia
from .contrato import Avaliacao, Ponto, Saida
from .ferramentas import buscar_referencias, id_achado
from .nos import MODELO, PIOR, SHORTCODE_NO_TEXTO, Estado, _confianca, _contar, _escrever, _limpar

PASTA_UPLOADS = dados.RAIZ / "data" / "uploads"
PALAVRAS_POR_SEGUNDO = 2.5  # fala corrida em português (~150 palavras por minuto)
# Num roteiro não há imagem: estes campos sairiam chutados pelo modelo e ficam fora da comparação.
CAMPOS_VISUAIS = {"tem_rosto", "pessoa_em_cena", "hook_visual", "texto_na_tela", "ritmo_cortes"}
# Características comparadas (as de baixa confiabilidade e as de contexto, como segmento, ficam de fora).
CAMPOS_AVALIADOS = ["duracao_faixa", "formato_video", "tipo_hook", "hook_visual", "tem_rosto", "texto_na_tela",
                    "tem_cta", "tipo_cta", "abordagem", "prova_social", "convite_participacao",
                    "tem_data_comemorativa", "ritmo_cortes", "pilar_impulso", "tom"]


# ---------------------------------------------------------------- ler

def _cliente():
    from google import genai
    load_dotenv(dados.RAIZ / ".env")
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def ler(estado: Estado) -> dict:
    e = estado["entrada"]
    if e.video_path:
        video = Path(e.video_path)
        pasta = video.parent / f"leitura_{video.stem}"
        meta = midia.extrair(video, pasta)
        transcricao = midia.transcrever(pasta)
        anot = midia.anotar(_cliente(), MODELO, pasta)
        cpm = meta["cortes"] / max(meta["duracao_s"], 1) * 60
        leitura = {**anot, "fonte": "video", "duracao_s": round(meta["duracao_s"], 1),
                   "duracao_faixa": dados.faixa_duracao(meta["duracao_s"]), "cortes_por_minuto": round(cpm, 1),
                   "ritmo_cortes": dados.ritmo_cortes(cpm), "gancho_falado": transcricao["gancho_falado"],
                   "pasta": str(pasta.relative_to(dados.RAIZ))}
    else:
        anot = midia.anotar_roteiro(_cliente(), MODELO, e.roteiro)
        segundos = len(re.findall(r"\w+", e.roteiro)) / PALAVRAS_POR_SEGUNDO
        leitura = {**{k: v for k, v in anot.items() if k not in CAMPOS_VISUAIS}, "fonte": "roteiro",
                   "duracao_s": round(segundos), "duracao_estimada": True,
                   "duracao_faixa": dados.faixa_duracao(segundos)}
    leitura["tem_data_comemorativa"] = str(anot.get("data_comemorativa", "")).strip().lower() not in ("", "nenhuma")
    leitura.pop("elementos_top5", None)
    return {"leitura": leitura, **_contar(estado, "ler", MODELO)}


# ---------------------------------------------------------------- comparar

def _claro(a: dict | None) -> bool:
    return bool(a) and a["robustez"] in ("robusto", "fragil")


def comparar(estado: Estado) -> dict:
    leitura, e = estado["leitura"], estado["entrada"]
    todos = dados.achados()
    por_valor = {(a["campo"], a["valor"]): a for a in todos}
    pontos, referencias = [], {}

    def exemplos(a: dict | None) -> list[str]:
        if not a:
            return []
        refs = buscar_referencias({a["campo"]: a["valor"]}, 2, segmento=e.segment)
        referencias.update({r["shortCode"]: r for r in refs})
        return [r["shortCode"] for r in refs]

    for campo in CAMPOS_AVALIADOS:
        if campo not in leitura:
            continue
        valor = str(leitura[campo])
        if campo == "tem_data_comemorativa" and valor == "False":
            continue  # não usar data comemorativa não é ponto forte; só o uso dela é comparado
        atual = por_valor.get((campo, valor))
        # A melhor alternativa: o valor do mesmo campo que mais aparece no top com diferença clara ou indício.
        alternativas = sorted((a for a in todos if a["campo"] == campo and a["valor"] != valor and _claro(a)
                               and a["dif_pp"] > 0), key=lambda a: (a["robustez"] != "robusto", -a["dif_pp"]))
        alternativa = alternativas[0] if alternativas else None
        if _claro(atual) and atual["dif_pp"] > 0:
            pontos.append({"tipo": "forte", "campo": campo, "valor": valor, "achado": atual, "alternativa": None,
                           "referencias": exemplos(atual)})
        elif _claro(atual) and atual["dif_pp"] < 0 or alternativa:
            pontos.append({"tipo": "melhorar", "campo": campo, "valor": valor,
                           "achado": atual if _claro(atual) else alternativa, "alternativa": alternativa,
                           "referencias": exemplos(alternativa)})
        elif atual and atual["robustez"] == "sem_diferenca" and valor != "nenhum" and campo in (
                "tem_rosto", "tem_cta", "abordagem", "prova_social", "pilar_impulso"):
            pontos.append({"tipo": "sem_efeito", "campo": campo, "valor": valor, "achado": atual,
                           "alternativa": None, "referencias": []})
    for i, p in enumerate(pontos, 1):
        p["id"] = f"P{i}"
    return {"pontos": pontos, "referencias": referencias,
            "achados": {id_achado(p["achado"]): p["achado"] for p in pontos}}


# ---------------------------------------------------------------- avaliador

class TextoPonto(BaseModel):
    id: str = Field(description="id do ponto (P1, P2...)")
    texto: str = Field(description="1 a 2 frases para a equipe, em português")


class RedacaoAvaliacao(BaseModel):
    explanation: str = Field(description="2 a 3 frases: o resumo da avaliação")
    pontos: list[TextoPonto]


INSTRUCOES_AVALIAR = """Escreva a avaliação de um vídeo (ou roteiro) da @impulsostone, comparado aos Reels de alto
engajamento da base. A lista de pontos e os números já estão decididos abaixo: escreva o texto de CADA ponto
(id igual ao da lista), em 1 ou 2 frases, para a equipe que produz o vídeo:
- forte: o que o vídeo já faz e por que isso conta (com o número top × controle do achado);
- melhorar: uma sugestão concreta do que mudar, inspirada na alternativa e nos Reels de exemplo (pode citar
  o gancho deles), com o número do achado; se o achado depende de poucos criadores, diga que é para testar;
- sem_efeito: diga que isso não diferencia os Reels de alto engajamento, então não precisa mudar.
Ao citar um Reel de exemplo, escreva o shortCode entre colchetes, ex.: [DbnuKRmRJ_H].
explanation: o resumo em 2 ou 3 frases, começando pelo principal ponto forte e pela principal melhoria.
Nunca dê nota nem diga quanto o vídeo vai engajar: são padrões observados, não previsão."""


def _contexto_avaliacao(estado: Estado) -> str:
    leitura, refs = estado["leitura"], estado["referencias"]
    duracao = f"{leitura['duracao_s']:.0f} s" + (" (estimada pelo roteiro)" if leitura.get("duracao_estimada") else "")
    linhas = [f"Pedido: {estado['entrada'].query}", f"Fonte: {leitura['fonte']}; duração {duracao}",
              f"Gancho lido: \"{leitura.get('hook_texto', '')}\" ({leitura.get('tipo_hook')})",
              f"Formato: {leitura.get('formato_video')}; tema: {leitura.get('tema_principal')}; "
              f"CTA: {leitura.get('tipo_cta')}", "", "PONTOS:"]
    for p in estado["pontos"]:
        a, alt = p["achado"], p["alternativa"]
        linha = (f"- {p['id']} [{p['tipo']}] o vídeo tem {dados.rotulo(p['campo'], p['valor'])}; achado: "
                 f"{a['descricao']} ({dados.vezes(a['lift']) if _claro(a) else 'diferença não confiável'}; "
                 f"selo {a['robustez']}{'; depende de poucos criadores' if a.get('depende_de_poucos') else ''})")
        if alt and alt is not a:
            linha += f"; alternativa: {alt['descricao']} ({dados.vezes(alt['lift'])}; selo {alt['robustez']})"
        if p["referencias"]:
            linha += "; exemplos: " + ", ".join(f"[{s}] \"{refs[s]['hook_texto']}\"" for s in p["referencias"])
        linhas.append(linha)
    return "\n".join(linhas)


def avaliador(estado: Estado) -> dict:
    redacao, extras = _escrever(estado, "avaliador", RedacaoAvaliacao, INSTRUCOES_AVALIAR,
                                contexto=_contexto_avaliacao(estado))
    return {"redacao_avaliacao": redacao, **extras}


def revisar_avaliacao(estado: Estado) -> list[str]:
    red = estado.get("redacao_avaliacao")
    if red is None:
        return ["a resposta não veio no formato pedido"]
    escritos = {t.id: t.texto for t in red.pontos if t.texto.strip()}
    problemas = [f"falta o texto do ponto {p['id']}" for p in estado["pontos"] if p["id"] not in escritos]
    textos = red.explanation + " " + " ".join(escritos.values())
    problemas += [f"Reel citado que não está nos exemplos: {s}" for s in set(re.findall(SHORTCODE_NO_TEXTO, textos))
                  if s not in estado["referencias"]]
    if re.search(r"\bnota\b|\d+\s*/\s*10|vai (?:engajar|viralizar|bombar)", textos, re.I):
        problemas.append("não dê nota nem previsão de engajamento")
    return problemas


def saida_avaliacao(estado: Estado) -> Saida:
    red = estado.get("redacao_avaliacao")
    textos = {t.id: t.texto for t in red.pontos} if red else {}
    grupos = {"forte": [], "melhorar": [], "sem_efeito": []}
    for p in estado["pontos"]:
        a = p["achado"]
        texto = _limpar(textos.get(p["id"]) or a["descricao"], {})  # [shortCode] fica: o front vira link
        grupos[p["tipo"]].append(Ponto(texto=texto, achado=id_achado(a), robustez=a["robustez"],
                                       referencias=p["referencias"]))
    leitura = {k: v for k, v in estado["leitura"].items() if isinstance(v, (str, bool, int, float))}
    usados = [p["achado"] for p in estado["pontos"] if p["tipo"] != "sem_efeito"]
    flag = min((_confianca(a) for a in usados), key=PIOR.index, default="insuficiente")
    avisos = [f"revisão: {p}" for p in estado.get("problemas", [])]
    if estado["leitura"]["fonte"] == "roteiro":
        avisos.append("avaliação de roteiro: a duração é estimada pelo texto e os aspectos visuais não foram avaliados")
    return Saida(run_id=estado["run_id"], mode="avaliar", findings=usados,
                 reference_posts=list(estado["referencias"].values()),
                 avaliacao=Avaliacao(fonte=estado["leitura"]["fonte"], leitura=leitura,
                                     pontos_fortes=grupos["forte"], pontos_a_melhorar=grupos["melhorar"],
                                     sem_efeito=grupos["sem_efeito"]),
                 confidence_flag=flag, explanation=red.explanation if red else "Não foi possível redigir a avaliação.",
                 warnings=avisos)


def salvar_upload(nome: str, conteudo: bytes) -> Path:
    """Guarda o vídeo enviado em data/uploads/{id}/ (fora do Git)."""
    sufixo = Path(nome).suffix.lower() if Path(nome).suffix.lower() in (".mp4", ".mov", ".m4v", ".webm") else ".mp4"
    destino = PASTA_UPLOADS / uuid.uuid4().hex[:12] / f"video{sufixo}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    return destino
