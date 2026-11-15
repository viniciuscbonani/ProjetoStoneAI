"""Compara características do grupo top com o controle (lift) e mede a robustez.

Para cada valor de cada campo categórico da rubrica (mais os campos calculados por código):
- frequência no top e no controle, diferença em pontos percentuais e lift = freq_top / freq_controle
- intervalo de confiança de 95% do lift por bootstrap de PERFIS (cluster): alguns criadores têm
  dezenas de Reels no top, e reamostrar Reels individuais subestimaria a incerteza
- confidence_flag quando o valor aparece em menos de 20 Reels do top ou o intervalo cruza 1
- teste de sensibilidade: o mesmo cálculo sem os perfis que ocultam parte das curtidas

Campos numéricos (força do gancho, clareza, cortes por minuto, duração) são comparados pela mediana.
O indicador de lead (comentários com intenção de contato) é comparado como proporção de comentários.

Saída: data/processed/lift.csv e um resumo no terminal.

Uso:
    .venv/bin/python scripts/lift.py
"""

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPETICOES = 2000
SEMENTE = 11
MIN_N_TOP = 20
CATEGORICOS = ["formato_video", "tipo_hook", "hook_visual", "tema_principal", "pilar_impulso", "segmento_publico",
               "tem_rosto", "pessoa_em_cena", "criador_e_empreendedor_real", "prova_social", "texto_na_tela", "tom",
               "usa_linguagem_regional", "tem_cta", "tipo_cta", "oferta_ou_beneficio_explicito",
               "convite_participacao", "abordagem", "fala_de_negocio", "tem_data_comemorativa",
               "duracao_faixa", "ritmo_cortes", "legenda_tamanho"]
NUMERICOS = ["forca_hook_0a10", "clareza_mensagem_0a10", "cortes_por_minuto", "duracao_s"]


def faixa_duracao(s: float) -> str:
    for limite, nome in ((15, "ate_15s"), (30, "15_30s"), (60, "30_60s"), (90, "60_90s")):
        if s <= limite:
            return nome
    return "mais_90s"


def carregar() -> list[dict]:
    amostra = {r["shortCode"]: r for r in csv.DictReader(open(RAIZ / "data" / "processed" / "amostra.csv"))}
    parciais = {r["handle"] for r in csv.DictReader(open(RAIZ / "data" / "interim" / "curtidas_ocultas.csv"))
                if r["confirmado"] != "True" and int(r["likes_igual_3"]) >= 3}
    coments = {r["shortCode"]: r for r in csv.DictReader(open(RAIZ / "data" / "interim" / "comentarios.csv"))}
    linhas = []
    for a in map(json.loads, open(RAIZ / "data" / "processed" / "anotacoes.jsonl")):
        if a["versao_rubrica"] != "v2" or a["shortCode"] not in amostra:
            continue
        r = amostra[a["shortCode"]]
        meta = json.loads((RAIZ / "data" / "midia" / a["shortCode"] / "meta.json").read_text())
        dur = meta["duracao_s"] or 1
        c = coments.get(a["shortCode"], {})
        linhas.append({
            **a, "grupo": r["grupo"], "perfil": r["perfil"], "faixa": r["faixa"],
            "oculta_parcial": r["perfil"] in parciais,
            "tem_data_comemorativa": a["data_comemorativa"].strip().lower() not in ("", "nenhuma"),
            "duracao_s": dur, "duracao_faixa": faixa_duracao(dur),
            "cortes_por_minuto": meta["cortes"] / dur * 60,
            "legenda_tamanho": "curta" if len(r["legenda"]) < 125 else "media" if len(r["legenda"]) < 500 else "longa",
            "coments_lidos": int(c.get("comentarios_lidos") or 0), "coments_intencao": int(c.get("com_intencao") or 0),
        })
    # Ritmo em tercis da amostra inteira, para não depender de um limiar arbitrário.
    cpm = sorted(l["cortes_por_minuto"] for l in linhas)
    t1, t2 = cpm[len(cpm) // 3], cpm[2 * len(cpm) // 3]
    for l in linhas:
        l["ritmo_cortes"] = "lento" if l["cortes_por_minuto"] <= t1 else "medio" if l["cortes_por_minuto"] <= t2 else "rapido"
    return linhas


def por_perfil(linhas: list[dict]) -> dict[str, dict[str, list[dict]]]:
    grupos = {"top": defaultdict(list), "controle": defaultdict(list)}
    for l in linhas:
        grupos[l["grupo"]][l["perfil"]].append(l)
    return grupos


def reamostrar(clusters: dict[str, list[dict]], rng: random.Random) -> list[dict]:
    perfis = list(clusters)
    return [l for p in rng.choices(perfis, k=len(perfis)) for l in clusters[p]]


def freq(linhas: list[dict], campo: str, valor) -> float:
    return sum(l[campo] == valor for l in linhas) / len(linhas) if linhas else 0.0


def calcular(linhas: list[dict], rng: random.Random) -> list[dict]:
    grupos = por_perfil(linhas)
    top = [l for l in linhas if l["grupo"] == "top"]
    ctl = [l for l in linhas if l["grupo"] == "controle"]
    amostras = [(reamostrar(grupos["top"], rng), reamostrar(grupos["controle"], rng)) for _ in range(REPETICOES)]

    resultado = []
    for campo in CATEGORICOS:
        for valor in sorted({l[campo] for l in linhas}, key=str):
            ft, fc = freq(top, campo, valor), freq(ctl, campo, valor)
            lifts = sorted(freq(t, campo, valor) / max(freq(c, campo, valor), 1e-9) for t, c in amostras)
            ic = (lifts[int(0.025 * REPETICOES)], lifts[int(0.975 * REPETICOES)])
            n_top = sum(l[campo] == valor for l in top)
            resultado.append({
                "campo": campo, "valor": str(valor), "n_top": n_top, "n_controle": sum(l[campo] == valor for l in ctl),
                "freq_top": round(ft, 3), "freq_controle": round(fc, 3), "dif_pp": round(100 * (ft - fc), 1),
                "lift": round(ft / fc, 2) if fc else None, "ic95_min": round(ic[0], 2), "ic95_max": round(min(ic[1], 99), 2),
                "confidence_flag": n_top < MIN_N_TOP or ic[0] <= 1 <= ic[1],
            })
    return resultado


def comparar_numericos(linhas: list[dict]) -> None:
    print("\nCampos numéricos (mediana top x controle):")
    for campo in NUMERICOS:
        t = statistics.median(l[campo] for l in linhas if l["grupo"] == "top")
        c = statistics.median(l[campo] for l in linhas if l["grupo"] == "controle")
        print(f"  {campo}: {t:.1f} x {c:.1f}")


def indicador_lead(linhas: list[dict], rng: random.Random) -> None:
    grupos = por_perfil(linhas)

    def taxa(ls):
        lidos = sum(l["coments_lidos"] for l in ls)
        return sum(l["coments_intencao"] for l in ls) / lidos if lidos else 0.0
    t = taxa([l for l in linhas if l["grupo"] == "top"])
    c = taxa([l for l in linhas if l["grupo"] == "controle"])
    lifts = sorted(taxa(reamostrar(grupos["top"], rng)) / max(taxa(reamostrar(grupos["controle"], rng)), 1e-9)
                   for _ in range(REPETICOES))
    print(f"\nIndicador de lead (comentários com intenção / comentários lidos): top {t:.1%} x controle {c:.1%}, "
          f"lift {t / c:.2f} (IC95 {lifts[int(.025 * REPETICOES)]:.2f}–{lifts[int(.975 * REPETICOES)]:.2f})")


def main() -> None:
    linhas = carregar()
    rng = random.Random(SEMENTE)
    print(f"{len(linhas)} Reels anotados: {sum(l['grupo'] == 'top' for l in linhas)} top, "
          f"{sum(l['grupo'] == 'controle' for l in linhas)} controle")

    geral = calcular(linhas, rng)
    sem_parciais = {(r["campo"], r["valor"]): r for r in calcular([l for l in linhas if not l["oculta_parcial"]], rng)}
    for r in geral:
        s = sem_parciais.get((r["campo"], r["valor"]))
        r["lift_sem_ocultacao_parcial"] = s["lift"] if s else None
        r["robusto_sensibilidade"] = bool(s and r["lift"] and s["lift"] and (r["lift"] > 1) == (s["lift"] > 1)
                                          and not s["confidence_flag"])

    destino = RAIZ / "data" / "processed" / "lift.csv"
    with open(destino, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(geral[0]))
        w.writeheader()
        w.writerows(geral)

    fortes = sorted((r for r in geral if not r["confidence_flag"]), key=lambda r: -abs(r["dif_pp"]))
    print("\nDiferenças com IC95 sem cruzar 1 e n_top >= 20 (maiores em pontos percentuais):")
    for r in fortes[:20]:
        print(f"  {r['campo']}={r['valor']}: top {r['freq_top']:.0%} x controle {r['freq_controle']:.0%} "
              f"(lift {r['lift']}, IC95 {r['ic95_min']}–{r['ic95_max']}, "
              f"sem ocultação parcial {r['lift_sem_ocultacao_parcial']}, robusto={r['robusto_sensibilidade']})")
    comparar_numericos(linhas)
    indicador_lead(linhas, rng)
    print(f"\n-> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
