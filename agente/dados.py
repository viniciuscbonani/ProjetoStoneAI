"""Acesso à base do agente (data/processed/agente.db, gerada por scripts/indexar_base.py).

Tudo o que o agente afirma sobre os dados sai daqui: achados do lift, Reels de referência, perfis e
a comparação top x controle em recortes (segmento, faixa, período), recalculada na hora com o mesmo
bootstrap por perfil do lift.py.
"""

import json
import random
import sqlite3
from collections import defaultdict
from datetime import date
from functools import cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "data" / "processed" / "agente.db"
MIN_N_TOP = 20  # mesmo corte do lift.py: abaixo disso o achado é "insuficiente"
REPETICOES_RECORTE = 500

# Campos que o agente pode citar (rubrica v2 + calculados). criador_e_empreendedor_real ficou fora da base.
CAMPOS = {
    "duracao_faixa": "duração", "formato_video": "formato do vídeo", "tipo_hook": "tipo de gancho",
    "hook_visual": "gancho visual", "tema_principal": "tema", "pilar_impulso": "pilar da @impulsostone",
    "segmento_publico": "segmento do público", "tem_rosto": "rosto em cena", "pessoa_em_cena": "pessoa em cena",
    "prova_social": "prova social", "texto_na_tela": "texto na tela", "tom": "tom",
    "usa_linguagem_regional": "linguagem regional", "tem_cta": "chamada para ação (CTA)", "tipo_cta": "tipo de CTA",
    "oferta_ou_beneficio_explicito": "oferta ou benefício explícito", "convite_participacao": "convite à participação",
    "abordagem": "abordagem", "fala_de_negocio": "fala de negócio", "tem_data_comemorativa": "data comemorativa",
    "ritmo_cortes": "ritmo de cortes", "legenda_tamanho": "tamanho da legenda",
}
BOOLEANOS = {"tem_rosto", "prova_social", "texto_na_tela", "usa_linguagem_regional", "tem_cta",
             "oferta_ou_beneficio_explicito", "convite_participacao", "fala_de_negocio", "tem_data_comemorativa",
             "oculta_parcial"}
VALORES = {"ate_15s": "até 15 s", "15_30s": "15 a 30 s", "30_60s": "30 a 60 s", "60_90s": "60 a 90 s",
           "mais_90s": "mais de 90 s"}
NUMERICOS = {"forca_hook_0a10", "clareza_mensagem_0a10", "duracao_s", "cortes_por_minuto", "taxa_engajamento",
             "curtidas", "comentarios", "visualizacoes", "seguidores", "coments_lidos", "coments_intencao"}


@cache
def _con() -> sqlite3.Connection:
    if not BASE.exists():
        raise FileNotFoundError(f"{BASE} não existe; rode scripts/indexar_base.py")
    con = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _reel(row: sqlite3.Row) -> dict:
    r = dict(row)
    for c in BOOLEANOS:
        r[c] = bool(r[c])
    r["elementos_top5"] = json.loads(r["elementos_top5"])
    return r


@cache
def todos_reels() -> tuple[dict, ...]:
    return tuple(_reel(r) for r in _con().execute("SELECT * FROM reels"))


@cache
def valores(campo: str) -> tuple[str, ...]:
    """Valores que o campo assume na base (como texto), para validar o que o LLM pede."""
    return tuple(sorted({str(r[campo]) for r in todos_reels()}))


def rotulo(campo: str, valor) -> str:
    nome = CAMPOS.get(campo, campo)
    if campo in BOOLEANOS or str(valor) in ("True", "False"):
        return f"{nome}: {'sim' if str(valor) == 'True' else 'não'}"
    return f"{nome}: {VALORES.get(str(valor), str(valor).replace('_', ' '))}"


def descrever(campo: str, valor, freq_top: float, freq_controle: float) -> str:
    return f"{rotulo(campo, valor)} — {freq_top:.0%} no top × {freq_controle:.0%} no controle"


def achados(campos: list[str] | None = None) -> list[dict]:
    """Achados do lift na amostra inteira (tabela achados)."""
    linhas = []
    for r in _con().execute("SELECT * FROM achados"):
        if campos and r["campo"] not in campos:
            continue
        f = lambda c: float(r[c]) if r[c] not in ("", None) else None
        linhas.append({"campo": r["campo"], "valor": r["valor"],
                       "descricao": descrever(r["campo"], r["valor"], f("freq_top"), f("freq_controle")),
                       "freq_top": f("freq_top"), "freq_controle": f("freq_controle"), "dif_pp": f("dif_pp"),
                       "lift": f("lift"), "ic95_min": f("ic95_min"), "ic95_max": f("ic95_max"),
                       "n_top": int(r["n_top"]), "n_controle": int(r["n_controle"]), "robustez": r["robustez"],
                       "recorte": None})
    return linhas


def filtrar(reels=None, *, grupo: str | None = None, segmento: str | None = None, faixas: list[str] | None = None,
            inicio: date | None = None, fim: date | None = None, condicoes: dict | None = None) -> list[dict]:
    """Filtra Reels por grupo, segmento do público, faixa do perfil, período e valores de campos."""
    saida = []
    for r in reels if reels is not None else todos_reels():
        if grupo and r["grupo"] != grupo:
            continue
        if segmento and r["segmento_publico"] != segmento:
            continue
        if faixas and r["faixa"] not in faixas:
            continue
        if inicio and r["publicado_em"] < inicio.isoformat():
            continue
        if fim and r["publicado_em"] > fim.isoformat():
            continue
        if condicoes and any(str(r.get(c)) != str(v) for c, v in condicoes.items()):
            continue
        saida.append(r)
    return saida


def comparar(reels: list[dict], campos: list[str], recorte: str, semente: int = 11) -> list[dict]:
    """Top x controle dentro de um recorte, com IC95 do lift por bootstrap de perfis (como no lift.py).

    Não repete o teste de sensibilidade do lift; por isso um recorte nunca sai "robusto" só pelo IC:
    o melhor que ele alcança é "fragil" quando o IC não cruza 1 (e "insuficiente" com n_top < 20)."""
    top = [r for r in reels if r["grupo"] == "top"]
    ctl = [r for r in reels if r["grupo"] == "controle"]
    if not top or not ctl:
        return []
    clusters = {"top": defaultdict(list), "controle": defaultdict(list)}
    for r in reels:
        clusters[r["grupo"]][r["perfil"]].append(r)
    rng = random.Random(semente)

    def reamostrar(c):
        perfis = list(c)
        return [r for p in rng.choices(perfis, k=len(perfis)) for r in c[p]]

    def freq(ls, campo, valor):
        return sum(str(r[campo]) == valor for r in ls) / len(ls) if ls else 0.0

    amostras = [(reamostrar(clusters["top"]), reamostrar(clusters["controle"])) for _ in range(REPETICOES_RECORTE)]
    linhas = []
    for campo in campos:
        for valor in sorted({str(r[campo]) for r in reels}):
            ft, fc = freq(top, campo, valor), freq(ctl, campo, valor)
            n_top = sum(str(r[campo]) == valor for r in top)
            lifts = sorted(freq(t, campo, valor) / max(freq(c, campo, valor), 1e-9) for t, c in amostras)
            ic = (lifts[int(0.025 * len(lifts))], min(lifts[int(0.975 * len(lifts))], 99))
            linhas.append({"campo": campo, "valor": valor, "descricao": descrever(campo, valor, ft, fc),
                           "freq_top": round(ft, 3), "freq_controle": round(fc, 3), "dif_pp": round(100 * (ft - fc), 1),
                           "lift": round(ft / fc, 2) if fc else None, "ic95_min": round(ic[0], 2),
                           "ic95_max": round(ic[1], 2), "n_top": n_top,
                           "n_controle": sum(str(r[campo]) == valor for r in ctl),
                           "robustez": "insuficiente" if n_top < MIN_N_TOP else "fragil", "recorte": recorte})
    return linhas


def perfis(faixas: list[str] | None = None) -> list[dict]:
    linhas = [dict(r) for r in _con().execute("SELECT * FROM perfis ORDER BY n_top DESC, taxa_mediana DESC")]
    return [p for p in linhas if not faixas or p["faixa"] in faixas]


def reel(short_code: str) -> dict | None:
    row = _con().execute("SELECT * FROM reels WHERE shortCode = ?", (short_code,)).fetchone()
    return _reel(row) if row else None
