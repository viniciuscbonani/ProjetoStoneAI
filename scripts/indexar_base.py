"""Consolida a análise em data/processed/agente.db (SQLite), a base que o agente consulta.

Tabelas:
- reels: um por Reel anotado (rubrica v2), com métricas da amostra, categorias da anotação e os
  campos calculados por código (faixa de duração, ritmo de cortes, tamanho da legenda...). Os campos
  calculados vêm de lift.carregar(), para serem idênticos aos usados no lift.
- achados: data/processed/lift.csv, com a robustez resumida (robusto | fragil | sem_diferenca | insuficiente).
- perfis: criadores da amostra, com presença no top e tema e formato predominantes.

Rodar de novo sempre que a anotação ou o lift mudarem.

Uso:
    .venv/bin/python scripts/indexar_base.py
"""

import csv
import json
import sqlite3
import statistics
from collections import Counter, defaultdict

from lift import MIN_N_TOP, RAIZ, carregar

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

    DESTINO.unlink(missing_ok=True)
    con = sqlite3.connect(DESTINO)
    for nome, linhas_tab, chave in (("reels", reels, "shortCode"), ("achados", achados, None),
                                    ("perfis", perfis, "perfil")):
        colunas = list(linhas_tab[0])
        defs = ", ".join(f'"{c}"' + (" PRIMARY KEY" if c == chave else "") for c in colunas)
        con.execute(f"CREATE TABLE {nome} ({defs})")
        con.executemany(f"INSERT INTO {nome} VALUES ({', '.join('?' * len(colunas))})",
                        [[r[c] for c in colunas] for r in linhas_tab])
    con.commit()
    con.close()

    print(f"{len(reels)} Reels ({sum(r['grupo'] == 'top' for r in reels)} top), {len(achados)} achados "
          f"({Counter(r['robustez'] for r in achados)}), {len(perfis)} perfis")
    print(f"-> {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
