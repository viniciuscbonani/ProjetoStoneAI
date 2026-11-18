"""Consolida a análise em data/processed/agente.db (SQLite), a base que o agente consulta.

Tabelas:
- reels: um por Reel anotado (rubrica v2), com métricas da amostra, categorias da anotação e os
  campos calculados por código (faixa de duração, ritmo de cortes, tamanho da legenda...). Os campos
  calculados vêm de lift.carregar(), para serem idênticos aos usados no lift.
- achados: data/processed/lift.csv, com a robustez resumida (robusto | fragil | sem_diferenca | insuficiente).
- perfis: criadores da amostra, com presença no top e tema e formato predominantes.
- impulsostone: os Reels da @impulsostone (data/processed/impulsostone.jsonl, de ler_impulsostone.py), com as mesmas
  colunas de reels e grupo = "impulsostone"; base do diagnóstico do perfil. Fica fora do top e do controle.

Rodar de novo sempre que a anotação ou o lift mudarem.

Uso:
    .venv/bin/python scripts/indexar_base.py
"""

import csv
import json
import sqlite3
import statistics
from collections import Counter, defaultdict

from lift import MIN_N_TOP, RAIZ, carregar, faixa_duracao

DESTINO = RAIZ / "data" / "processed" / "agente.db"
# Campo de confiabilidade fraca na validação cruzada: fica fora da base do agente.
DESCARTADOS = {"criador_e_empreendedor_real"}


def robustez(r: dict) -> str:
    """insuficiente: menos de 20 Reels no top; sem_diferenca: o IC95 do lift contém o 1 (top e controle não se
    distinguem); fragil: o IC95 exclui o 1, mas o resultado não se mantém sem os perfis de ocultação parcial;
    robusto: exclui o 1 e se mantém."""
    if int(r["n_top"]) < MIN_N_TOP:
        return "insuficiente"
    if float(r["ic95_min"]) <= 1 <= float(r["ic95_max"]):
        return "sem_diferenca"
    return "robusto" if r["robusto_sensibilidade"] == "True" else "fragil"


def reels_impulsostone(colunas: list[str], linhas_amostra: list[dict]) -> list[dict]:
    """Os Reels da @impulsostone com os mesmos campos calculados da amostra (ritmo de cortes nos tercis da amostra)."""
    arq = RAIZ / "data" / "processed" / "impulsostone.jsonl"
    if not arq.exists():
        return []
    base = {r["shortCode"]: r for r in csv.DictReader(open(RAIZ / "data" / "processed" / "base.csv"))}
    cpm = sorted(l["cortes_por_minuto"] for l in linhas_amostra)
    t1, t2 = cpm[len(cpm) // 3], cpm[2 * len(cpm) // 3]
    saida = []
    for a in map(json.loads, open(arq)):
        b = base[a["shortCode"]]
        meta = json.loads((RAIZ / "data" / "midia" / a["shortCode"] / "meta.json").read_text())
        dur = meta["duracao_s"] or 1
        por_min = meta["cortes"] / dur * 60
        r = {**a, "grupo": "impulsostone", "perfil": b["perfil"], "faixa": b["faixa"], "oculta_parcial": False,
             "tem_data_comemorativa": a["data_comemorativa"].strip().lower() not in ("", "nenhuma"),
             "duracao_s": dur, "duracao_faixa": faixa_duracao(dur), "cortes_por_minuto": por_min,
             "ritmo_cortes": "lento" if por_min <= t1 else "medio" if por_min <= t2 else "rapido",
             "legenda_tamanho": "curta" if len(b["legenda"]) < 125 else "media" if len(b["legenda"]) < 500 else "longa",
             "coments_lidos": 0, "coments_intencao": 0, "url": b["url"], "publicado_em": b["publicado_em"],
             "curtidas": int(b["curtidas"]), "comentarios": int(b["comentarios"]),
             "visualizacoes": int(b["visualizacoes"]), "seguidores": int(b["seguidores"]), "nicho": b["nicho"],
             "taxa_engajamento": float(b["taxa_engajamento"]), "legenda": b["legenda"],
             "elementos_top5": json.dumps(a["elementos_top5"], ensure_ascii=False)}
        saida.append({c: r[c] for c in colunas})
    return saida


def main() -> None:
    amostra = {r["shortCode"]: r for r in csv.DictReader(open(RAIZ / "data" / "processed" / "amostra.csv"))}
    linhas = carregar()

    reels = []
    for l in linhas:
        a = amostra[l["shortCode"]]
        r = {k: v for k, v in l.items() if k not in DESCARTADOS | {"modelo", "versao_rubrica"}}
        r.update(url=a["url"], publicado_em=a["publicado_em"], curtidas=int(a["curtidas"]),
                 comentarios=int(a["comentarios"]), visualizacoes=int(a["visualizacoes"]),
                 seguidores=int(a["seguidores"]), nicho=a["nicho"], taxa_engajamento=float(a["taxa_engajamento"]),
                 legenda=a["legenda"], elementos_top5=json.dumps(l["elementos_top5"], ensure_ascii=False))
        reels.append(r)

    achados = [r for r in csv.DictReader(open(RAIZ / "data" / "processed" / "lift.csv"))
               if r["campo"] not in DESCARTADOS]
    for r in achados:
        r["robustez"] = robustez(r)

    por_perfil = defaultdict(list)
    for r in reels:
        por_perfil[r["perfil"]].append(r)
    perfis = []
    for p, rs in por_perfil.items():
        top = [r for r in rs if r["grupo"] == "top"]
        ref = top or rs
        perfis.append({
            "perfil": p, "faixa": rs[0]["faixa"], "seguidores": rs[0]["seguidores"], "nicho": rs[0]["nicho"],
            "n_top": len(top), "n_amostra": len(rs),
            "tema_predominante": Counter(r["tema_principal"] for r in ref).most_common(1)[0][0],
            "formato_predominante": Counter(r["formato_video"] for r in ref).most_common(1)[0][0],
            "taxa_mediana": round(statistics.median(r["taxa_engajamento"] for r in rs), 2),
        })

    stone = reels_impulsostone(list(reels[0]), linhas)

    DESTINO.unlink(missing_ok=True)
    con = sqlite3.connect(DESTINO)
    for nome, linhas_tab, chave in (("reels", reels, "shortCode"), ("achados", achados, None),
                                    ("perfis", perfis, "perfil"), ("impulsostone", stone, "shortCode")):
        if not linhas_tab:
            continue
        colunas = list(linhas_tab[0])
        defs = ", ".join(f'"{c}"' + (" PRIMARY KEY" if c == chave else "") for c in colunas)
        con.execute(f"CREATE TABLE {nome} ({defs})")
        con.executemany(f"INSERT INTO {nome} VALUES ({', '.join('?' * len(colunas))})",
                        [[r[c] for c in colunas] for r in linhas_tab])
    con.commit()
    con.close()

    print(f"{len(reels)} Reels ({sum(r['grupo'] == 'top' for r in reels)} top), {len(achados)} achados "
          f"({Counter(r['robustez'] for r in achados)}), {len(perfis)} perfis, {len(stone)} Reels da @impulsostone")
    print(f"-> {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
