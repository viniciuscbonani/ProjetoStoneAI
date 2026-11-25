"""Fecha a análise: a lista oficial de achados e os perfis em destaque, usada no playbook e no README.

Lê a base do agente (data/processed/agente.db, gerada por indexar_base.py a partir do lift) e grava:
- data/processed/achados_finais.csv: os achados em três grupos
    diferenca_clara  selo robusto (IC95 do lift exclui o 1 e passa no teste de sensibilidade)
    indicio          selo frágil (IC95 exclui o 1, mas não passa no teste de sensibilidade)
    hipotese_stone   o que a Stone viu funcionar (ou não) nos anúncios, testado aqui nos Reels orgânicos
  com números, a leitura em uma frase, 2 Reels de exemplo e um teste extra de concentração: o lift recalculado
  sem os 6 criadores com mais Reels no top (eles somam ~37% do top).
- data/processed/perfis_destaque.csv: os 15 criadores com mais Reels no top, com tema e formato predominantes
  e a marca de ocultação parcial de curtidas (perfis em que a taxa de engajamento pode estar distorcida).

Uso:
    .venv/bin/python scripts/achados_finais.py
"""

import csv
import random
import sys
from collections import defaultdict

from lift import REPETICOES, RAIZ, carregar, por_perfil, reamostrar

sys.path.insert(0, str(RAIZ))
from agente import dados  # noqa: E402
from agente.ferramentas import buscar_referencias  # noqa: E402

N_CONCENTRADORES = 6
N_PERFIS = 15

# O que os anúncios da Stone sugeriram (histórico de campanhas, Meta Ads) e que dá para testar nos Reels.
HIPOTESES_STONE = [
    ("tem_rosto", "True", "pessoas reais em cena"),
    ("convite_participacao", "True", "convite à participação (o post de maior CTR da Stone)"),
    ("abordagem", "dor_real", "dor real do empreendedor"),
    ("abordagem", "motivacional_generica", "frase motivacional genérica (o que não funcionou nos anúncios)"),
    ("tem_cta", "True", "chamada para ação"),
    ("prova_social", "True", "prova social"),
    ("pilar_impulso", "historias_reais", "histórias reais"),
]

# Leitura de cada achado para a Stone, escrita na análise (o número vem da base; a frase é a interpretação).
LEITURA = {
    ("duracao_faixa", "mais_90s"): "Vídeos longos aparecem 2× mais no top: quem engaja MPEs explica com calma.",
    ("duracao_faixa", "30_60s"): "A faixa de 30 a 60 s é menos comum no top: nem tão curto para prender, nem longo para aprofundar.",
    ("formato_video", "explicativo"): "Explicar um conceito do negócio (por que algo acontece) aparece 2× mais no top, mas o sinal depende de poucos criadores (some sem os 6 maiores); vale testar.",
    ("tipo_hook", "curiosidade"): "Gancho de curiosidade aparece um pouco mais no top; vale testar.",
    ("tipo_hook", "polemica"): "Gancho polêmico aparece mais no top, mas é raro (5%) e pode não combinar com o tom da Stone.",
    ("tem_data_comemorativa", "True"): "Datas comemorativas aparecem MENOS no top orgânico, ao contrário dos anúncios da Stone (Festa Junina); o sinal é fraco (some sem os 6 maiores criadores): a data sozinha não parece segurar o engajamento.",
    ("tem_data_comemorativa", "False"): None,  # o espelho do anterior; não entra na lista
    ("tem_rosto", "True"): "Mostrar o rosto é o padrão no top, mas não diferencia: os Reels comuns também mostram.",
    ("convite_participacao", "True"): "Convite à participação é raro nos Reels de criadores: poucos dados para dizer; o sucesso dele nos anúncios da Stone segue sendo a melhor evidência.",
    ("abordagem", "dor_real"): "Falar de uma dor real é comum no top, mas não separa o top dos Reels comuns.",
    ("abordagem", "motivacional_generica"): "Frase motivacional genérica não aparece mais nem menos no top: não é o que engaja.",
    ("tem_cta", "True"): "Ter CTA não muda o engajamento; mas para a Stone o CTA serve ao clique, não à curtida.",
    ("prova_social", "True"): "Prova social aparece um pouco mais no top, mas a diferença não é confiável.",
    ("pilar_impulso", "historias_reais"): "Histórias reais aparecem um pouco mais no top, sem diferença confiável.",
}


def lift_sem(linhas: list[dict], excluir: set[str], campo: str, valor: str, rng: random.Random) -> tuple:
    """Lift e IC95 (bootstrap por perfil) sem os perfis em `excluir`."""
    resto = [l for l in linhas if l["perfil"] not in excluir]
    top = [l for l in resto if l["grupo"] == "top"]
    ctl = [l for l in resto if l["grupo"] == "controle"]
    freq = lambda ls: sum(str(l[campo]) == valor for l in ls) / len(ls) if ls else 0.0
    grupos = por_perfil(resto)
    lifts = sorted(freq(reamostrar(grupos["top"], rng)) / max(freq(reamostrar(grupos["controle"], rng)), 1e-9)
                   for _ in range(REPETICOES // 4))
    ic = (lifts[int(0.025 * len(lifts))], lifts[int(0.975 * len(lifts))])
    return round(freq(top) / freq(ctl), 2) if freq(ctl) else None, round(ic[0], 2), round(ic[1], 2)


def indicador_lead(linhas: list[dict], rng: random.Random) -> dict:
    """Comentários com intenção de contato ÷ comentários lidos, top × controle (como em lift.py)."""
    grupos = por_perfil(linhas)

    def taxa(ls):
        lidos = sum(l["coments_lidos"] for l in ls)
        return sum(l["coments_intencao"] for l in ls) / lidos if lidos else 0.0
    t = taxa([l for l in linhas if l["grupo"] == "top"])
    c = taxa([l for l in linhas if l["grupo"] == "controle"])
    lifts = sorted(taxa(reamostrar(grupos["top"], rng)) / max(taxa(reamostrar(grupos["controle"], rng)), 1e-9)
                   for _ in range(REPETICOES))
    return {"freq_top": round(t, 3), "freq_controle": round(c, 3), "lift": round(t / c, 2),
            "ic95_min": round(lifts[int(.025 * REPETICOES)], 2), "ic95_max": round(lifts[int(.975 * REPETICOES)], 2)}


def main() -> None:
    rng = random.Random(11)
    linhas = carregar()
    achados = {(a["campo"], a["valor"]): a for a in dados.achados()}
    perfis = dados.perfis()
    concentradores = {p["perfil"] for p in perfis[:N_CONCENTRADORES]}
    parte_top = sum(p["n_top"] for p in perfis[:N_CONCENTRADORES]) / sum(p["n_top"] for p in perfis)

    selecionados = [("diferenca_clara", a, None) for a in achados.values() if a["robustez"] == "robusto"]
    selecionados += [("indicio", a, None) for a in achados.values() if a["robustez"] == "fragil"
                     and LEITURA.get((a["campo"], a["valor"]), "") is not None]
    selecionados += [("hipotese_stone", achados[(c, v)], nome) for c, v, nome in HIPOTESES_STONE]
    selecionados.sort(key=lambda x: (["diferenca_clara", "indicio", "hipotese_stone"].index(x[0]), -x[1]["dif_pp"]))

    saida = []
    for grupo, a, nome in selecionados:
        sem = lift_sem(linhas, concentradores, a["campo"], a["valor"], rng)
        # A conclusão se mantém sem os 6 maiores criadores? Para uma diferença: mesma direção e IC sem o 1;
        # para um "sem diferença" (ou poucos dados): o IC continua contendo o 1.
        if a["robustez"] in ("robusto", "fragil"):
            mantem = sem[0] is not None and (sem[0] > 1) == (a["lift"] > 1) and not (sem[1] <= 1 <= sem[2])
        else:
            mantem = sem[1] <= 1 <= sem[2]
        exemplos = [r["shortCode"] for r in buscar_referencias({a["campo"]: a["valor"]}, 2)] if a["dif_pp"] > 0 else []
        saida.append({
            "grupo": grupo, "campo": a["campo"], "valor": a["valor"], "achado": nome or a["descricao"].split(" — ")[0],
            "freq_top": a["freq_top"], "freq_controle": a["freq_controle"],
            "vezes": dados.vezes(a["lift"]) if a["robustez"] in ("robusto", "fragil")
            else "diferença não confiável entre top e controle",
            "lift": a["lift"], "ic95_min": a["ic95_min"], "ic95_max": a["ic95_max"], "n_top": a["n_top"],
            "robustez": a["robustez"], "lift_sem_6_maiores": sem[0], "ic95_sem_6_maiores": f"{sem[1]}–{sem[2]}",
            "mantem_sem_6_maiores": mantem, "leitura": LEITURA.get((a["campo"], a["valor"]), ""),
            "exemplos": " ".join(exemplos)})

    lead = indicador_lead(linhas, rng)
    saida.append({"grupo": "hipotese_stone", "campo": "comentarios_intencao", "valor": "proporcao",
                  "achado": "comentários com intenção de contato (indicador de lead)", **lead,
                  "vezes": "diferença não confiável entre top e controle", "n_top": "",
                  "robustez": "sem_diferenca" if lead["ic95_min"] <= 1 <= lead["ic95_max"] else "fragil",
                  "lift_sem_6_maiores": "", "ic95_sem_6_maiores": "", "mantem_sem_6_maiores": "",
                  "leitura": f"Comentários com intenção de contato ('quero', 'qual o link') são {lead['freq_top']:.1%} no top "
                             f"e {lead['freq_controle']:.1%} no controle: engajar mais não traz mais pedidos de contato.",
                  "exemplos": ""})

    destino = RAIZ / "data" / "processed" / "achados_finais.csv"
    with open(destino, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0]))
        w.writeheader()
        w.writerows(saida)

    reels = dados.todos_reels()
    parcial = defaultdict(bool)
    for r in reels:
        parcial[r["perfil"]] |= r["oculta_parcial"]
    lista = [{**p, "pct_reels_no_top": round(p["n_top"] / p["n_amostra"], 2), "oculta_parcial": parcial[p["perfil"]],
              "url": f"https://www.instagram.com/{p['perfil']}/"} for p in perfis[:N_PERFIS]]
    destino_perfis = RAIZ / "data" / "processed" / "perfis_destaque.csv"
    with open(destino_perfis, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lista[0]))
        w.writeheader()
        w.writerows(lista)

    print(f"Os {N_CONCENTRADORES} criadores com mais Reels no top somam {parte_top:.0%} do top: {', '.join(sorted(concentradores))}\n")
    for s in saida:
        extra = "" if s["mantem_sem_6_maiores"] == "" else f" | sem os 6: lift {s['lift_sem_6_maiores']} ({s['ic95_sem_6_maiores']}), mantém={s['mantem_sem_6_maiores']}"
        print(f"[{s['grupo']}] {s['achado']}: {s['freq_top']:.0%} × {s['freq_controle']:.0%}, {s['vezes']} ({s['robustez']}){extra}")
    print(f"\nPerfis em destaque: {len(lista)}, {sum(p['oculta_parcial'] for p in lista)} com ocultação parcial de curtidas")
    print(f"-> {destino.relative_to(RAIZ)}\n-> {destino_perfis.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
