"""Diagnóstico da @impulsostone: os 56 Reels do perfil, lidos com a mesma rubrica da base, comparados ao top e ao
controle. Tudo por código, sem LLM.

Para cada achado com diferença clara ou indício, a frequência na Stone (com IC de 95% de Wilson, porque n é pequeno)
é comparada ao top e ao controle:
- lacuna: o achado aparece mais no top e a Stone fica abaixo do ponto médio entre top e controle; "clara" quando o IC
  inteiro fica abaixo do top, "provável" quando o IC ainda alcança o top (com n = 56, só uma pista);
- excesso: o espelho, para o que aparece menos no top (a Stone acima do ponto médio);
- achado que depende de poucos criadores (dados.depende_de_poucos) nunca sai como "claro";
- em linha: a Stone já está do lado do top.
As hipóteses da Stone que não diferenciam o top (rosto, CTA, dor real...) vão para "não é alavanca".
"""

import csv
import math
import statistics
from collections import Counter
from functools import cache

from . import dados
from .ferramentas import buscar_referencias

PERFIL = "impulsostone"
# Hipóteses da Stone (persona e histórico de anúncios) mostradas em "não é alavanca" quando não diferenciam o top.
HIPOTESES = [("tem_rosto", "True"), ("tem_cta", "True"), ("abordagem", "dor_real"), ("prova_social", "True"),
             ("abordagem", "motivacional_generica"), ("fala_de_negocio", "True")]
RETRATO = ["formato_video", "tipo_hook", "duracao_faixa", "tema_principal", "pilar_impulso"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 1.0
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centro - margem), min(1.0, centro + margem)


@cache
def frequencias() -> dict:
    """Frequência de cada valor (campo=valor) nos Reels da Stone, com IC de 95%."""
    reels = dados.reels_stone()
    n = len(reels)
    valores = {}
    for a in dados.achados():
        k = sum(str(r.get(a["campo"])) == a["valor"] for r in reels)
        lo, hi = wilson(k, n)
        valores[f"{a['campo']}={a['valor']}"] = {"k": k, "freq": round(k / n, 3) if n else 0.0,
                                                 "ic_min": round(lo, 3), "ic_max": round(hi, 3)}
    return {"perfil": PERFIL, "n": n, "valores": valores}


def _classificar(a: dict, f: dict) -> tuple[str, str] | None:
    """(tipo, nivel) de um achado com diferença clara ou indício; None para os outros."""
    if a["robustez"] not in ("robusto", "fragil") or a["valor"] == "False":
        return None  # em sim/não, o "não" é o espelho do "sim"
    meio = (a["freq_top"] + a["freq_controle"]) / 2
    pode_ser_claro = not a["depende_de_poucos"]
    if a["dif_pp"] > 0:
        if f["freq"] >= meio:
            return "em_linha", ""
        return "lacuna", "claro" if pode_ser_claro and f["ic_max"] < a["freq_top"] else "provavel"
    if f["freq"] <= meio:
        return "em_linha", ""
    return "excesso", "claro" if pode_ser_claro and f["ic_min"] > a["freq_top"] else "provavel"


def _resumo_reel(r: dict) -> dict:
    return {"shortCode": r["shortCode"], "url": r["url"], "perfil": r["perfil"], "faixa": r["faixa"],
            "seguidores": r["seguidores"], "curtidas": r["curtidas"], "comentarios": r["comentarios"],
            "visualizacoes": r["visualizacoes"], "taxa_engajamento": round(r["taxa_engajamento"], 4),
            "duracao_s": r["duracao_s"], "publicado_em": r["publicado_em"], "hook_texto": r["hook_texto"],
            "categorias": {c: r[c] for c in ("formato_video", "duracao_faixa", "tipo_hook", "tema_principal",
                                             "pilar_impulso", "tem_rosto", "tem_cta", "tipo_cta")},
            "motivo": "@impulsostone"}


def _da_stone(campo: str, valor: str, n: int = 3) -> list[dict]:
    com = [r for r in dados.reels_stone() if str(r[campo]) == valor]
    return [_resumo_reel(r) for r in sorted(com, key=lambda r: -r["taxa_engajamento"])[:n]]


def posicao() -> dict:
    """Taxa mediana da Stone entre os perfis micro do ranking (mediana de cada perfil)."""
    por_perfil: dict[str, list[float]] = {}
    stone = []
    for r in csv.DictReader(open(dados.RAIZ / "data" / "processed" / "base.csv")):
        if r["perfil"] == PERFIL:
            stone.append(float(r["taxa_engajamento"]))
        elif r["faixa"] == "micro" and r["no_ranking"] == "True":
            por_perfil.setdefault(r["perfil"], []).append(float(r["taxa_engajamento"]))
    medianas = sorted(statistics.median(v) for v in por_perfil.values())
    da_stone = statistics.median(stone)
    return {"taxa_mediana": round(da_stone, 4), "perfis_micro": len(medianas),
            "abaixo": sum(m < da_stone for m in medianas),
            "mediana_micro": round(statistics.median(medianas), 4)}


@cache
def diagnostico() -> dict:
    reels = dados.reels_stone()
    freqs = frequencias()["valores"]
    pontos = []
    for a in dados.achados():
        f = freqs[f"{a['campo']}={a['valor']}"]
        c = _classificar(a, f)
        if not c:
            continue
        tipo, nivel = c
        pontos.append({"tipo": tipo, "nivel": nivel, "achado": a, "stone": f,
                       "reels_stone": _da_stone(a["campo"], a["valor"]),
                       "reels_top": [{k: v for k, v in r.items() if not k.startswith("_")}
                                     for r in buscar_referencias({a["campo"]: a["valor"]}, 4)]
                       if tipo != "excesso" else []})
    ordem = {"lacuna": 0, "excesso": 1, "em_linha": 2}
    pontos.sort(key=lambda p: (ordem[p["tipo"]], p["nivel"] != "claro", p["achado"]["robustez"] != "robusto",
                               -abs(p["achado"]["dif_pp"])))

    por_valor = {(a["campo"], a["valor"]): a for a in dados.achados()}
    nao_alavanca = [{"achado": por_valor[h], "stone": freqs[f"{h[0]}={h[1]}"]}
                    for h in HIPOTESES if h in por_valor and por_valor[h]["robustez"] == "sem_diferenca"]

    retrato = []
    for campo in RETRATO:
        contagem = Counter(str(r[campo]) for r in reels).most_common(4)
        retrato.append({"campo": campo, "rotulo": dados.CAMPOS[campo],
                        "valores": [{"valor": v, "rotulo": dados.rotulo(campo, v).split(": ", 1)[1], "freq": k / len(reels),
                                     "freq_top": por_valor.get((campo, v), {}).get("freq_top")} for v, k in contagem]})

    datas = sorted(r["publicado_em"] for r in reels)
    return {"perfil": PERFIL, "n": len(reels), "periodo": [datas[0], datas[-1]] if datas else None,
            "posicao": posicao(), "pontos": pontos, "nao_alavanca": nao_alavanca, "retrato": retrato,
            "reels": [_resumo_reel(r) for r in sorted(reels, key=lambda r: r["publicado_em"], reverse=True)]}
