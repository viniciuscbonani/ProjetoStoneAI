"""Busca nos 944 Reels anotados por características da rubrica e por texto (página Ganchos do front).

Sem LLM. O texto procurado vale para o gancho, a legenda e a transcrição (sem diferença de acentos nem de
maiúsculas; todas as palavras precisam aparecer). Valores do mesmo campo somam (gancho de pergunta OU de
curiosidade); campos diferentes se combinam (gancho de pergunta E CTA de comentar).

Cada Reel volta com o trecho onde o texto aparece e a fala dos últimos segundos, onde a chamada para ação
costuma estar (a rubrica guarda o tipo de CTA, não a frase).
"""

import json
import unicodedata
from functools import cache

from . import dados
from .ferramentas import _referencia

# Campos oferecidos como filtro, na ordem da tela.
FILTROS = ["tipo_hook", "tipo_cta", "duracao_faixa", "formato_video", "tema_principal", "segmento_publico",
           "tem_rosto", "convite_participacao", "prova_social", "abordagem", "tem_data_comemorativa", "tom"]
ORDENS = {"taxa": "taxa_engajamento", "visualizacoes": "visualizacoes", "recentes": "publicado_em"}
SEGUNDOS_FINAIS = 8


@cache
def _letra(c: str) -> str:
    base = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode().lower()
    return base if len(base) == 1 and not base.isspace() else " "


def _normalizar(texto: str) -> str:
    """Sem acentos e em minúsculas, letra a letra: o resultado tem o tamanho do original, para que a posição de
    um termo encontrado valha também no texto original (o trecho mostrado)."""
    return "".join(_letra(c) for c in texto or "")


@cache
def _transcricoes() -> dict[str, dict]:
    saida = {}
    for r in dados.todos_reels():
        arq = dados.RAIZ / "data" / "midia" / r["shortCode"] / "transcricao.json"
        saida[r["shortCode"]] = json.loads(arq.read_text()) if arq.exists() else {}
    return saida


def transcricao(short_code: str) -> str:
    return _transcricoes().get(short_code, {}).get("texto", "")


def fala_final(r: dict) -> str:
    segs = _transcricoes().get(r["shortCode"], {}).get("segmentos", [])
    return " ".join(s["texto"] for s in segs if s["fim"] >= r["duracao_s"] - SEGUNDOS_FINAIS).strip()


@cache
def _textos() -> dict[str, str]:
    return {r["shortCode"]: _normalizar(" \n ".join([r["hook_texto"], r["legenda"], transcricao(r["shortCode"])]))
            for r in dados.todos_reels()}


def _trecho(r: dict, termos: list[str], largura: int = 90) -> str | None:
    """O pedaço da transcrição (ou da legenda) em que aparece o primeiro termo."""
    for fonte in (transcricao(r["shortCode"]), r["legenda"]):
        i = _normalizar(fonte).find(termos[0])
        if i < 0:
            continue
        ini, fim = max(0, i - largura), min(len(fonte), i + len(termos[0]) + largura)
        return ("…" if ini else "") + fonte[ini:fim].strip() + ("…" if fim < len(fonte) else "")
    return None


def opcoes() -> list[dict]:
    """Os filtros com os valores que existem na base e quantos Reels têm cada um (no top e no total)."""
    reels = dados.todos_reels()
    saida = []
    for campo in FILTROS:
        valores = []
        for v in dados.valores(campo):
            com = [r for r in reels if str(r[campo]) == v]
            rotulo = ("sim" if v == "True" else "não") if campo in dados.BOOLEANOS else \
                dados.VALORES.get(v, v.replace("_", " "))
            valores.append({"valor": v, "rotulo": rotulo, "n": len(com), "n_top": sum(r["grupo"] == "top" for r in com)})
        saida.append({"campo": campo, "rotulo": dados.CAMPOS[campo], "valores": sorted(valores, key=lambda x: -x["n"])})
    return saida


def buscar(texto: str = "", filtros: dict[str, list[str]] | None = None, faixas: list[str] | None = None,
           grupo: str | None = None, ordem: str = "taxa", limite: int = 30, inicio: int = 0) -> dict:
    termos = [t for t in _normalizar(texto).split() if len(t) > 1]
    filtros = {c: set(vs) for c, vs in (filtros or {}).items() if c in FILTROS and vs}
    textos = _textos()
    achados = [r for r in dados.filtrar(grupo=grupo or None, faixas=faixas or None)
               if all(str(r[c]) in vs for c, vs in filtros.items())
               and all(t in textos[r["shortCode"]] for t in termos)]
    achados.sort(key=lambda r: r[ORDENS.get(ordem, "taxa_engajamento")], reverse=True)
    itens = [{**{k: v for k, v in _referencia(r, "busca").items() if not k.startswith("_")},
              "grupo": r["grupo"], "oculta_parcial": r["oculta_parcial"], "trecho": _trecho(r, termos) if termos else None, "fala_final": fala_final(r)}
             for r in achados[inicio:inicio + limite]]
    return {"total": len(achados), "n_top": sum(r["grupo"] == "top" for r in achados), "termos": termos,
            "itens": itens}
