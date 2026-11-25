"""Monta o playbook de conteúdo da @impulsostone (#20) em docs/playbook.md.

Os números, os exemplos e os criativos vêm da base, nunca escritos à mão:
- achados e selos: agente.db (lift.py) e data/processed/achados_finais.csv;
- Reels de exemplo e frases de gancho: agente.db, pelas mesmas funções que o agente usa;
- diagnóstico da @impulsostone: agente/diagnostico.py;
- perfis em destaque: data/processed/perfis_destaque.csv;
- criativos: data/processed/playbook_criativos.json (scripts/criativos_playbook.py).
O texto fixo (como aplicar, leituras) fica neste script. Rodar de novo se a base, o lift ou os criativos mudarem.

Uso: .venv/bin/python scripts/gerar_playbook.py
"""

import csv
import json
import re
from collections import Counter
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PIL import Image  # noqa: E402

from agente import dados  # noqa: E402
from agente.diagnostico import diagnostico  # noqa: E402
from agente.ferramentas import buscar_referencias  # noqa: E402

SAIDA = RAIZ / "docs" / "playbook.md"
CRIATIVOS = RAIZ / "data" / "processed" / "playbook_criativos.json"
CRIATIVOS_POR_BRIEFING = 2
PASTA_IMAGENS = RAIZ / "data" / "imagens"

SELO = {"robusto": "Diferença clara", "fragil": "Indício", "sem_diferenca": "Sem diferença",
        "insuficiente": "Poucos dados"}

# Como aplicar cada achado na @impulsostone (texto fixo, escrito a partir dos Reels de exemplo e da persona).
COMO_APLICAR = {
    "duracao_faixa=mais_90s": [
        "Reserve os vídeos longos para conteúdo que ensina: um passo a passo, uma conta feita na tela, um erro comum "
        "explicado do começo ao fim.",
        "Mantenha o ritmo com texto na tela e exemplos concretos (valores, situações do dia a dia do negócio), não "
        "com cortes rápidos: vários Reels longos do top têm poucos cortes.",
        "Use a legenda para repetir o conteúdo em tópicos; quem salva o vídeo volta para ela.",
    ],
    "duracao_faixa=30_60s": [
        "Se o assunto cabe em 30 a 60 s, avalie se ele fica melhor curto (até 30 s, uma ideia só) ou aprofundado "
        "(mais de 90 s).",
    ],
    "tipo_hook=curiosidade": [
        "Abra com uma situação ou um dado que pede explicação (\"Por que o cliente acha caro um preço que é justo?\"), "
        "e só entregue a resposta depois de alguns segundos.",
        "A curiosidade precisa ser cumprida no vídeo: gancho que promete e não entrega afasta.",
    ],
    "tipo_hook=polemica": [
        "Discordar de um conselho comum (\"Parar de dar desconto pode aumentar suas vendas\") funciona no top, mas é "
        "raro (5% dos Reels).",
        "No tom da @impulsostone, prefira a polêmica que desafia uma crença do negócio, nunca uma pessoa ou um grupo.",
    ],
    "formato_video=explicativo": [
        "Parta de uma cena do dia a dia (o cliente que pede desconto, o caixa que não fecha) e explique o porquê dela, "
        "com um exemplo de valores.",
        "Combina com os vídeos longos: o explicativo é o formato mais natural para passar de 90 s sem enrolar.",
        "Como o sinal vem de poucos criadores, trate como teste: compare a taxa desses Reels com a dos outros.",
    ],
    "tem_data_comemorativa=True": [
        "Datas comemorativas aparecem menos no top orgânico (ao contrário dos anúncios da Stone, em que a Festa Junina "
        "foi bem). Use a data como pano de fundo de um conteúdo útil, não como o assunto do Reel.",
    ],
}

# Duração mínima (s) dos Reels de exemplo de um achado: um "explicativo" de 7 s não mostra o formato.
DURACAO_MIN_EXEMPLO = {"formato_video=explicativo": 45}

# Ganchos do top que a rubrica marca como de negócio, mas que não falam com pequenos negócios (revisão manual).
GANCHOS_FORA = {
    "DfH5T5ck5bP",  # "5 skills que transformam o Claude no meu editor de vídeo": ferramenta de criador
    "DZGaFVJxct9",  # "eu sou feiofóbica": gosto pessoal, sem gancho de negócio
}

# Concorrentes da Stone que entraram na base: seguem na análise, mas não aparecem como exemplo nem inspiração
# num material da Stone.
CONCORRENTES = {"infinitepay", "pagbank", "contaazul"}

# Hashtags com gênero nos criativos: a @impulsostone fala com empreendedores e empreendedoras (persona).
HASHTAGS_NEUTRAS = {"#EmpreendedorismoFeminino": "#Empreendedorismo", "#Empreendedora": "#Empreendedorismo",
                    "#DonaDeSalao": "#SalaoDeBeleza"}


# ---------------------------------------------------------------- formatação


def pct(x: float | None, casas: int = 0) -> str:
    return "–" if x is None else f"{x:.{casas}%}".replace(".", ",")


def taxa(x: float) -> str:
    """Taxa de engajamento em %, com uma casa abaixo de 10%."""
    return pct(x, 1 if x < 0.1 else 0)


def segundos(s: float) -> str:
    s = round(s)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def limpar(texto: str) -> str:
    texto = re.sub(r"(\d)\.(\d)%", r"\1,\2%", str(texto or ""))
    return " ".join(texto.split()).replace("|", "/")


def maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def link_reel(short_code: str) -> str:
    return f"[{short_code}](https://www.instagram.com/reel/{short_code}/)"


def tabela_reels(reels: list[dict]) -> list[str]:
    linhas = ["| Reel | Perfil | Gancho (primeiros segundos) | Duração | Engajamento |",
              "|---|---|---|---|---|"]
    for r in reels:
        linhas.append(f"| {link_reel(r['shortCode'])} | @{r['perfil']} | \"{limpar(r['hook_texto'])}\" | "
                      f"{segundos(r['duracao_s'])} | {taxa(r['taxa_engajamento'])} |")
    return linhas


# ---------------------------------------------------------------- dados


def carregar() -> dict:
    achados = {f"{a['campo']}={a['valor']}": a for a in dados.achados()}
    finais = list(csv.DictReader(open(RAIZ / "data/processed/achados_finais.csv")))
    perfis = list(csv.DictReader(open(RAIZ / "data/processed/perfis_destaque.csv")))
    criativos = json.loads(CRIATIVOS.read_text()) if CRIATIVOS.exists() else []
    base = list(csv.DictReader(open(RAIZ / "data/processed/base.csv")))
    return {"achados": achados, "finais": finais, "perfis": perfis, "diag": diagnostico(), "criativos": criativos,
            "amostra": list(csv.DictReader(open(RAIZ / "data/processed/amostra.csv"))), "base": base,
            "ocultas": {r["perfil"] for r in base if r["perfil_oculta_parcial"] == "True"},
            "fora": CONCORRENTES | {r["perfil"] for r in base if r["perfil_oculta_parcial"] == "True"}}


def exemplos(d: dict, caracteristicas: dict, n: int = 3) -> list[dict]:
    """Reels do top para assistir: um por criador, sem repetir Reel nem gancho já usados no playbook.

    Ficam de fora os concorrentes da Stone, os perfis com ocultação parcial de curtidas (a taxa pode estar
    distorcida) e, nos achados de
    formato, os Reels curtos demais para mostrar o formato (DURACAO_MIN_EXEMPLO)."""
    usados = d.setdefault("usados", set())
    minimo = max((DURACAO_MIN_EXEMPLO.get(f"{c}={v}", 0) for c, v in caracteristicas.items()), default=0)
    saida = []
    for r in buscar_referencias(caracteristicas, 40):
        gancho = limpar(r["hook_texto"]).lower().rstrip(".!?")
        if r["shortCode"] in usados or gancho in usados or r["perfil"] in {x["perfil"] for x in saida}:
            continue
        if r["perfil"] in d["fora"] or r["duracao_s"] < minimo:
            continue
        usados |= {r["shortCode"], gancho}
        saida.append(r)
        if len(saida) == n:
            break
    return saida


def media_forca(reels: list[dict], tipo_hook: str) -> str:
    """Força média do gancho (0 a 10, da rubrica) dos Reels com esse tipo de gancho."""
    notas = [r["forca_hook_0a10"] for r in reels if r["tipo_hook"] == tipo_hook and r["forca_hook_0a10"]]
    return f"{sum(notas) / len(notas):.1f}".replace(".", ",") if notas else "–"


def chave(f: dict) -> str:
    return f"{f['campo']}={f['valor']}"


# ---------------------------------------------------------------- seções


def cabecalho(d: dict) -> list[str]:
    n_base = len(d["base"])
    n_ranking = sum(r["no_ranking"] == "True" for r in d["base"])
    n_perfis = len({r["perfil"] for r in d["base"] if r["no_ranking"] == "True"})
    return [
        "# Playbook de conteúdo da @impulsostone",
        "",
        "O que os Reels de maior engajamento entre micro e pequenos empreendedores têm em comum, e como levar "
        "isso para a @impulsostone.",
        "",
        f"TAPI Stone × Inteli Academy · gerado em {date.today():%d/%m/%Y} por `scripts/gerar_playbook.py` a partir "
        f"da base do projeto ({n_base:,} Reels coletados; {n_ranking:,} de {n_perfis} perfis no ranking).".replace(",", "."),
        "",
        "Este documento é para a equipe que planeja e grava os Reels da @impulsostone. Cada recomendação vem com o "
        "número que a sustenta, o grau de confiança e Reels reais para assistir. Os criativos do fim são roteiros "
        "prontos para gravar.",
        "",
        "**Como ler os selos.** *Diferença clara*: o padrão aparece bem mais (ou bem menos) no top e resiste aos "
        "testes. *Indício*: aparece mais no top, mas o sinal é mais fraco; vale testar. *Sem diferença*: o top e os "
        "Reels comuns não se distinguem nisso. *Poucos dados*: não dá para dizer.",
        "",
    ]


def resumo(d: dict) -> list[str]:
    a, stone = d["achados"], {chave(p["achado"]): p["stone"] for p in d["diag"]["pontos"]}
    longo, curto, cur = a["duracao_faixa=mais_90s"], a["duracao_faixa=30_60s"], a["tipo_hook=curiosidade"]
    cta = a["tem_cta=True"]
    return [
        "## Resumo em uma página",
        "",
        f"1. **Faça vídeos longos, de mais de 90 s, que ensinem algo com calma.** São {pct(longo['freq_top'])} dos "
        f"Reels do top e {pct(longo['freq_controle'])} dos comuns ({dados.vezes(longo['lift'])}). Na @impulsostone, "
        f"hoje, são {pct(stone['duracao_faixa=mais_90s']['freq'])}. *Diferença clara.*",
        f"2. **Abra com curiosidade.** Uma situação ou um dado que pede explicação: {pct(cur['freq_top'])} dos Reels "
        f"do top × {pct(cur['freq_controle'])} dos comuns. Na @impulsostone, {pct(stone['tipo_hook=curiosidade']['freq'])}. "
        "*Indício.*",
        f"3. **Fuja do meio-termo de 30 a 60 s.** Essa faixa é {dados.vezes(curto['lift'])} "
        f"({pct(curto['freq_top'])} × {pct(curto['freq_controle'])}): ou uma ideia só em até 30 s, ou o assunto "
        "aprofundado em mais de 90 s. *Diferença clara.*",
        "4. **Rosto, dor real, prova social e frase motivacional não fazem um Reel engajar.** São tão comuns no top "
        "quanto nos Reels comuns: podem estar no vídeo, mas não são o diferencial. Data comemorativa aparece até menos "
        "no top, mas esse sinal depende de poucos criadores.",
        f"5. **Termine sempre com um próximo passo claro.** O CTA não muda o engajamento ({pct(cta['freq_top'])} × "
        f"{pct(cta['freq_controle'])}), mas o objetivo da @impulsostone é a inscrição, e reação não é clique: sem "
        "chamada, quem gostou do vídeo não vira lead.",
        "",
    ]


def metodo(d: dict) -> list[str]:
    amostra = d["amostra"]
    n_top = sum(r["grupo"] == "top" for r in amostra)
    n_ctrl = len(amostra) - n_top
    datas = sorted(r["publicado_em"][:10] for r in d["base"] if r["no_ranking"] == "True")
    return [
        "## Como chegamos aqui",
        "",
        f"- **Base:** Reels públicos de perfis que falam com micro e pequenos empreendedores (finanças, precificação, "
        f"marketing, alimentação, beleza, contabilidade e outros), publicados entre {datas[0][8:10]}/{datas[0][5:7]}/"
        f"{datas[0][:4]} e {datas[-1][8:10]}/{datas[-1][5:7]}/{datas[-1][:4]} (a coleta foi até 14/11/2026, mas os Reels com menos de 14 dias ficaram fora do ranking), "
        "coletados pela rota definida no case.",
        "- **Métrica:** taxa de engajamento = (curtidas + comentários) ÷ seguidores do perfil. Ela compara perfis "
        "pequenos e grandes de igual para igual; o número absoluto de curtidas favorece as contas grandes.",
        f"- **Top × controle:** os {n_top} Reels de maior taxa (os 10% de cima) foram comparados a {n_ctrl} Reels "
        "sorteados do restante, na mesma proporção de perfis micro, médios e grandes. Uma característica só conta "
        "como padrão do top se aparecer mais nele do que nos Reels comuns; aparecer muito no top não basta, porque "
        "pode ser só o jeito de todo mundo fazer.",
        "- **Leitura dos vídeos:** o Gemini assistiu a cada Reel da amostra (8 quadros, transcrição do áudio e "
        "legenda) e preencheu uma ficha fixa: formato, gancho, tema, duração, CTA, rosto em cena e outros. Uma amostra "
        "de 50 Reels foi conferida por outro modelo (Claude), sem ver a resposta do Gemini.",
        "- **Concentração:** os 6 criadores com mais Reels no top somam 37% dele. Cada achado foi refeito sem eles; "
        "os que somem sem esses 6 aparecem aqui como *depende de poucos criadores*.",
        "- **Taxas acima de 100%:** acontecem quando um Reel viraliza e recebe mais curtidas do que o perfil tem de "
        "seguidores (o alcance vem de quem não segue). São os casos mais fortes do top; o padrão vale para os 472.",
        "",
    ]


RETRATO_CAMPOS = ["formato_video", "tema_principal", "tipo_hook", "duracao_faixa", "tem_rosto", "texto_na_tela",
                  "tem_cta", "tipo_cta", "tom", "ritmo_cortes", "legenda_tamanho"]


def nome_valor(campo: str, valor) -> str:
    return dados.rotulo(campo, valor).split(": ", 1)[1].replace("_", " ")


def selo_curto(a: dict | None) -> str:
    if a is None:
        return "Poucos dados"
    selo = SELO[a["robustez"]]
    if a["robustez"] in ("robusto", "fragil"):
        selo += f" ({'mais' if a['lift'] is None or a['lift'] >= 1 else 'menos'} no top)"
    return selo + (", depende de poucos criadores" if a.get("depende_de_poucos") else "")


def mais_comum(reels: list[dict], campo: str) -> str:
    cont = Counter(str(r[campo]) for r in reels if r.get(campo) not in (None, ""))
    return nome_valor(campo, cont.most_common(1)[0][0]) if cont else "–"


def recorte(d: dict, campo: str, colunas: list[str]) -> list[str]:
    """Uma linha por valor do campo no top: quanto do top e dos comuns, o mais comum de outras características
    dentro do valor e um Reel real de exemplo (o de maior taxa, fora dos concorrentes e dos perfis com curtidas ocultas)."""
    reels = dados.todos_reels()
    top = [r for r in reels if r["grupo"] == "top"]
    ctrl = [r for r in reels if r["grupo"] == "controle"]
    linhas = []
    for valor, n in Counter(str(r[campo]) for r in top).most_common():
        dentro = [r for r in top if str(r[campo]) == valor]
        a = d["achados"].get(f"{campo}={valor}")
        exemplo = max((r for r in dentro if r["perfil"] not in d["fora"]),
                      key=lambda r: r["taxa_engajamento"], default=None)
        f_top = a["freq_top"] if a else n / len(top)
        f_ctrl = a["freq_controle"] if a else sum(str(r[campo]) == valor for r in ctrl) / len(ctrl)
        linhas.append(
            f"| {maiuscula(nome_valor(campo, valor))} | {n} ({pct(f_top)}) | {pct(f_ctrl)} | "
            + " | ".join(mais_comum(dentro, c) for c in colunas)
            + f" | {link_reel(exemplo['shortCode']) + ' @' + exemplo['perfil'] if exemplo else '–'} | "
            f"{selo_curto(a) if n >= dados.MIN_N_TOP else 'Poucos dados'} |")
    return linhas


def retrato_top(d: dict) -> list[str]:
    reels = dados.todos_reels()
    n_top = sum(r["grupo"] == "top" for r in reels)
    linhas = [
        "## Como é o Reel do top",
        "",
        f"O retrato dos {n_top} Reels de maior engajamento: o valor mais comum de cada característica da ficha de "
        "leitura. Ao lado, a frequência nos Reels comuns, porque o mais comum no top pode ser só o jeito de todo "
        "mundo fazer; a última coluna diz se a característica separa o top dos comuns (detalhes nas seções "
        "seguintes).",
        "",
        "| Característica | Mais comum no top | No top | Nos comuns | Separa o top? |",
        "|---|---|---|---|---|",
    ]
    for campo in RETRATO_CAMPOS:
        candidatos = [a for a in d["achados"].values() if a["campo"] == campo]
        a = max(candidatos, key=lambda a: a["freq_top"])
        linhas.append(f"| {maiuscula(dados.CAMPOS[campo])} | {nome_valor(campo, a['valor'])} | "
                      f"{pct(a['freq_top'])} | {pct(a['freq_controle'])} | {selo_curto(a)} |")
    linhas += [
        "",
        "### Recorte por tema",
        "",
        "Quantos Reels do top tratam de cada tema e, dentro de cada tema, o formato, o gancho e a duração mais "
        "comuns, com um Reel real para assistir (o de maior engajamento do tema).",
        "",
        "| Tema | Reels no top | Nos comuns | Formato mais comum | Gancho mais comum | Duração mais comum | "
        "Exemplo | Separa o top? |",
        "|---|---|---|---|---|---|---|---|",
        *recorte(d, "tema_principal", ["formato_video", "tipo_hook", "duracao_faixa"]),
        "",
        "### Recorte por formato",
        "",
        "O mesmo, por formato de vídeo: quanto cada formato aparece no top, sobre o que costuma falar e quanto dura.",
        "",
        "| Formato | Reels no top | Nos comuns | Tema mais comum | Gancho mais comum | Duração mais comum | "
        "Exemplo | Separa o top? |",
        "|---|---|---|---|---|---|---|---|",
        *recorte(d, "formato_video", ["tema_principal", "tipo_hook", "duracao_faixa"]),
        "",
        f"Com menos de {dados.MIN_N_TOP} Reels no top, a linha aparece como *Poucos dados*. Algumas linhas dizem "
        "*Sem diferença* mesmo com números distantes (talking head, história de empreendedor): a margem de erro é "
        "calculada por perfil, e essas diferenças vêm de poucos criadores, então não dá para afirmar que valem para "
        "o top como um todo.",
        "",
    ]
    return linhas


def bloco_achado(d: dict, f: dict, evitar: bool = False) -> list[str]:
    a = d["achados"][chave(f)]
    selo = SELO[f["robustez"]]
    poucos = " · depende de poucos criadores" if f["mantem_sem_6_maiores"] == "False" else ""
    titulo = dados.rotulo(f["campo"], f["valor"]).split(": ", 1)[-1]
    if f["campo"] in dados.BOOLEANOS:
        titulo = dados.CAMPOS[f["campo"]] + ("" if f["valor"] == "True" else " (sem)")
    elif f["campo"] == "tipo_hook":
        titulo = f"gancho de {titulo}"
    elif f["campo"] == "formato_video":
        titulo = f"formato {titulo}"
    elif f["campo"] == "duracao_faixa":
        titulo = f"vídeos de {titulo}"
    linhas = [
        f"### {maiuscula(titulo)}",
        "",
        f"**{pct(a['freq_top'])} dos Reels do top × {pct(a['freq_controle'])} dos Reels comuns** · "
        f"{dados.vezes(a['lift'])} · *{selo}*{poucos}",
        "",
        limpar(f["leitura"]),
        "",
    ]
    if COMO_APLICAR.get(chave(f)):
        linhas += ["**Como aplicar:**", ""] + [f"- {t}" for t in COMO_APLICAR[chave(f)]] + [""]
    if not evitar:
        refs = exemplos(d, {f["campo"]: f["valor"]})
        if refs:
            linhas += ["Para assistir:", ""] + tabela_reels(refs) + [""]
    return linhas


def o_que_fazer(d: dict) -> list[str]:
    mais = [f for f in d["finais"] if f["robustez"] in ("robusto", "fragil") and float(f["lift"]) > 1]
    mais.sort(key=lambda f: (f["robustez"] != "robusto", f["mantem_sem_6_maiores"] == "False", -int(f["n_top"])))
    linhas = ["## O que fazer", "",
              "Características que aparecem mais no top do que nos Reels comuns, da mais à menos confiável.", ""]
    for f in mais:
        linhas += bloco_achado(d, f)
    return linhas


def o_que_evitar(d: dict) -> list[str]:
    menos = [f for f in d["finais"] if f["robustez"] in ("robusto", "fragil") and float(f["lift"]) < 1]
    menos.sort(key=lambda f: (f["robustez"] != "robusto", float(f["lift"])))
    linhas = ["## O que evitar", "", "Características que aparecem menos no top do que nos Reels comuns.", ""]
    for f in menos:
        linhas += bloco_achado(d, f, evitar=True)
    return linhas


def nao_faz_diferenca(d: dict) -> list[str]:
    hip = [f for f in d["finais"] if f["grupo"] == "hipotese_stone"]
    linhas = [
        "## O que não faz diferença no engajamento",
        "",
        "Hipóteses comuns (algumas vindas dos anúncios da própria Stone) que os dados não confirmam nos Reels "
        "orgânicos. Não quer dizer que devam sair dos vídeos: quer dizer que não são o que separa um Reel de alto "
        "engajamento de um comum. Nenhuma muda quando se tiram os 6 maiores criadores.",
        "",
        "| Característica | No top | Nos comuns | Leitura |",
        "|---|---|---|---|",
    ]
    for f in hip:
        linhas.append(f"| {maiuscula(f['achado'])} | {pct(float(f['freq_top']), 1)} | "
                      f"{pct(float(f['freq_controle']), 1)} | {limpar(f['leitura'])} |")
    linhas += [
        "",
        "**O que isso muda na prática:** pessoa real em cena e depoimento continuam bem-vindos, mas sozinhos não "
        "seguram a atenção; o que segura é o conteúdo (o que a pessoa ensina ou revela) e a abertura. E o CTA fica "
        "em todo vídeo pelo motivo certo: levar à inscrição, não ganhar curtidas.",
        "",
    ]
    return linhas


def diagnostico_stone(d: dict) -> list[str]:
    g = d["diag"]
    ini, fim = g["periodo"]
    pos = g["posicao"]
    linhas = [
        "## Onde a @impulsostone está hoje",
        "",
        f"Os {g['n']} Reels da @impulsostone publicados entre {ini[8:10]}/{ini[5:7]} e {fim[8:10]}/{fim[5:7]}/{fim[:4]} "
        "passaram pela mesma leitura da amostra e foram comparados ao top. A taxa de engajamento mediana do perfil é "
        f"{pct(pos['taxa_mediana'], 1)}, o que a põe no meio dos {pos['perfis_micro']} perfis micro do ranking: "
        f"acima de {pos['abaixo']} deles e abaixo de {pos['perfis_micro'] - pos['abaixo']}. Como são só {g['n']} Reels, "
        "as porcentagens têm margem larga; por isso só chamamos de lacuna clara o que fica longe do top mesmo "
        "contando essa margem.",
        "",
        "| Característica | @impulsostone | Top | Comuns | Situação |",
        "|---|---|---|---|---|",
    ]
    nomes = {("lacuna", "claro"): "**Usa pouco** (lacuna clara)", ("lacuna", "provavel"): "Usa pouco (para observar)",
             ("excesso", "claro"): "**Usa demais**", ("excesso", "provavel"): "Usa demais (para observar)"}
    for p in g["pontos"]:
        a = p["achado"]
        situacao = "Igual ao top" if p["tipo"] == "em_linha" else nomes[(p["tipo"], p["nivel"])]
        linhas.append(f"| {maiuscula(a['descricao'].split(' — ')[0])} | {pct(p['stone']['freq'])} "
                      f"({p['stone']['k']} de {g['n']}) | {pct(a['freq_top'])} | {pct(a['freq_controle'])} | {situacao} |")
    for h in g["nao_alavanca"]:
        a = h["achado"]
        linhas.append(f"| {maiuscula(a['descricao'].split(' — ')[0])} | {pct(h['stone']['freq'])} | {pct(a['freq_top'])} | "
                      f"{pct(a['freq_controle'])} | Não faz diferença |")
    claros = [p for p in g["pontos"] if p["tipo"] == "lacuna" and p["nivel"] == "claro"]
    linhas += ["", "**As duas mudanças com mais potencial:**", ""]
    for p in claros:
        a = p["achado"]
        nome = a["descricao"].split(" — ")[0]
        linhas.append(f"- **{maiuscula(nome)}:** {p['stone']['k']} de {g['n']} Reels da @impulsostone "
                      f"({pct(p['stone']['freq'])}), contra {pct(a['freq_top'])} dos Reels do top.")
        if a["campo"] == "tipo_hook":
            stone_f = media_forca(dados.reels_stone(), a["valor"])
            top_f = media_forca(dados.filtrar(grupo="top"), a["valor"])
            linhas.append(f"  Os ganchos desse tipo que a @impulsostone já usou são mais fracos que os do top (força "
                          f"média de {stone_f} × {top_f} de 10, na leitura dos vídeos). Para se inspirar, veja as "
                          "aberturas do top no banco de ganchos, mais abaixo.")
        elif p["reels_stone"]:
            melhores = ", ".join(f"{link_reel(r['shortCode'])} (\"{limpar(r['hook_texto'])}\")" for r in p["reels_stone"][:2])
            linhas.append(f"  Os que a @impulsostone já fez nessa linha e que mais engajaram: {melhores}.")
    linhas += [
        "",
        "O retrato do perfil hoje: "
        + "; ".join(f"{r['rotulo']} mais comum: {r['valores'][0]['rotulo']} ({pct(r['valores'][0]['freq'])})"
                    for r in g["retrato"][:3]) + ".",
        "",
    ]
    return linhas


def perfis(d: dict) -> list[str]:
    linhas = [
        "## Perfis para se inspirar",
        "",
        "Os criadores com mais Reels entre os de maior engajamento, com o tema e o formato que mais usam. Servem "
        "como referência de linguagem e de formato (e, quem sabe, de parcerias).",
        "",
        "| Perfil | Tamanho | Seguidores | Reels no top | Tema mais comum | Formato mais comum |",
        "|---|---|---|---|---|---|",
    ]
    for p in d["perfis"]:
        aviso = " ¹" if p["oculta_parcial"] == "True" else ""
        linhas.append(
            f"| [@{p['perfil']}]({p['url']}){aviso} | {dados.VALORES.get(p['faixa'], p['faixa'])} | "
            f"{int(p['seguidores']):,} | {p['n_top']} de {p['n_amostra']} | "
            f"{dados.rotulo('tema_principal', p['tema_predominante']).split(': ')[1]} | "
            f"{dados.rotulo('formato_video', p['formato_predominante']).split(': ')[1].replace('_', ' ')} |"
            .replace(",", "."))
    linhas += ["", "¹ Esconde as curtidas de parte dos Reels; a taxa desses perfis pode estar distorcida.", ""]
    return linhas


def ganchos(d: dict) -> list[str]:
    tipos = [a for a in dados.achados(["tipo_hook"]) if a["valor"] not in ("nenhum",)]
    tipos.sort(key=lambda a: (a["robustez"] not in ("robusto", "fragil") or a["lift"] < 1, -a["freq_top"]))
    top = [r for r in dados.filtrar(grupo="top")
           if r["fala_de_negocio"] and r["hook_texto"] and r["shortCode"] not in GANCHOS_FORA
           and r["perfil"] not in d["fora"]]
    linhas = [
        "## Banco de ganchos",
        "",
        "Frases reais de abertura dos Reels do top, por tipo de gancho, para inspirar (não para copiar). Em cada "
        "tipo, as aberturas mais fortes segundo a leitura dos vídeos, uma por criador (sem os perfis que escondem "
        "parte das curtidas, cujo lugar no top pode estar distorcido).",
        "",
    ]
    for a in tipos:
        nome = dados.rotulo("tipo_hook", a["valor"]).split(": ")[1]
        linhas += [f"### {maiuscula(nome)}", "",
                   f"{pct(a['freq_top'])} dos Reels do top × {pct(a['freq_controle'])} dos comuns · *{SELO[a['robustez']]}*", ""]
        candidatos = sorted((r for r in top if r["tipo_hook"] == a["valor"]),
                            key=lambda r: (-(r["forca_hook_0a10"] or 0), -r["taxa_engajamento"]))
        vistos = set()
        for r in candidatos:
            if r["perfil"] in vistos:
                continue
            vistos.add(r["perfil"])
            linhas.append(f"- \"{limpar(r['hook_texto'])}\" · @{r['perfil']} · {link_reel(r['shortCode'])}")
            if len(vistos) == 5:
                break
        linhas.append("")
    return linhas


def achados_do_criativo(c: dict) -> list[str]:
    """Achados que o criativo de fato aplica, com o aviso dos que dependem de poucos criadores.

    O gerador às vezes lista um achado que o roteiro não cumpre (formato explicativo num talking head, "mais de
    90 s" num roteiro de 70 a 90 s); esses saem."""
    formato = rotulo_curto("formato_video", c["formato"].replace(" ", "_"))
    maximo = max((int(x) for x in re.findall(r"\d+", c["duracao_alvo"])), default=0)
    poucos = [dados.rotulo(*k.split("=")) for k in dados.depende_de_poucos()]
    saida = []
    for texto in c["achados_usados"]:
        if texto.startswith("formato do vídeo: ") and not texto.startswith(f"formato do vídeo: {formato} "):
            continue
        if texto.startswith("duração: mais de 90 s") and maximo <= 90:
            continue
        if any(texto.startswith(p) for p in poucos):
            texto += ", depende de poucos criadores"
        saida.append(texto)
    return saida


def capa_do_criativo(run_id: str, i: int, n: int) -> str | None:
    """Copia a capa gerada (data/imagens, fora do Git) para docs/imagens, reduzida, e devolve o caminho relativo.

    As capas são geradas à parte (agente.imagens, Cloudflare), conferidas e, se ruins, refeitas antes de rodar
    este script; sem capa gerada, o criativo sai só com o prompt."""
    origem = PASTA_IMAGENS / run_id / f"criativo{i}_capa.jpg"
    if not origem.exists():
        return None
    destino = SAIDA.parent / "imagens" / f"criativo{n}_capa.jpg"
    destino.parent.mkdir(exist_ok=True)
    img = Image.open(origem).convert("RGB")
    img.thumbnail((540, 960))
    img.save(destino, "JPEG", quality=82)
    return destino.relative_to(SAIDA.parent).as_posix()


def rotulo_curto(campo: str, valor: str) -> str:
    return dados.rotulo(campo, valor).split(": ", 1)[-1]


def criativos(d: dict) -> list[str]:
    linhas = [
        "## Criativos prontos para gravar",
        "",
        "Gerados pelo agente do projeto (modo `gerar_criativo`) a partir dos achados acima e conferidos por um revisor "
        "automático (citações e tom da @impulsostone). Cada um traz os Reels reais que o inspiraram. São versões "
        "preliminares: a equipe ajusta a fala, grava e edita. As capas são uma sugestão visual geradas por IA "
        "(FLUX.2 no Cloudflare Workers AI, a partir do prompt de cada criativo); a foto real do Reel deve seguir a "
        "mesma ideia, com uma pessoa real.",
        "",
    ]
    n = 0
    for execucao in d["criativos"]:
        e, s = execucao["entrada"], execucao["saida"]
        for i, c in enumerate(s["creatives"][:CRIATIVOS_POR_BRIEFING], 1):
            n += 1
            setor = f" · setor: {dados.VALORES.get(e['segment'], e['segment'])}" if e.get("segment") else ""
            linhas += [f"### {n}. {c['titulo']}", ""]
            capa = capa_do_criativo(s["run_id"], i, n)
            if capa:
                linhas += [f'<img src="{capa}" width="270" alt="Capa do criativo {n}: {limpar(c["titulo"])}">', ""]
            linhas += [
                f"**Formato:** {c['formato']} · **duração:** {c['duracao_alvo']}{setor}",
                "",
                f"**Gancho:** {c['gancho']}",
                "",
                "| Tempo | O que acontece | Texto na tela |",
                "|---|---|---|",
            ]
            for cena in c["roteiro"]:
                linhas.append(f"| {cena['tempo']} | {limpar(cena['descricao'])} | {limpar(cena['texto_na_tela'])} |")
            legenda = c["legenda"].strip().replace("\n", "\n> ")
            for de, para in HASHTAGS_NEUTRAS.items():
                legenda = re.sub(re.escape(de) + r"\b", para, legenda)
            legenda = re.sub(r"(#\w+)(?=.*\1\b)\s*", "", legenda)  # tira hashtag repetida pela troca
            linhas += ["", "**Legenda:**", "", f"> {legenda}", "", f"**CTA:** {c['cta']}", ""]
            insp = []
            for sc in c["inspirado_em"]:
                r = dados.reel(sc)
                if r and r["perfil"] in CONCORRENTES:
                    continue
                insp.append(f"{link_reel(sc)} (@{r['perfil']}, \"{limpar(r['hook_texto'])}\")" if r else link_reel(sc))
            linhas += [f"**Inspirado em:** {'; '.join(insp)}", ""]
            usados = achados_do_criativo(c)
            if usados:
                linhas += ["**Achados aplicados:** " + "; ".join(usados), ""]
            if c.get("prompt_capa"):
                linhas += ["<details><summary>Prompt da capa (9:16) para gerar a imagem</summary>", "",
                           c["prompt_capa"].replace("smiling confidentially", "smiling confidently")
                           .replace(" with bold text on screen", ""), "", "</details>", ""]
    if not n:
        linhas += ["*Ainda não gerados: rode `scripts/criativos_playbook.py`.*", ""]
    return linhas


def limites() -> list[str]:
    return [
        "## Limites deste playbook",
        "",
        "- **Padrões observados, não garantia.** Os achados mostram o que é mais comum nos Reels de maior "
        "engajamento; não provam que a característica causa o engajamento, e não preveem o resultado de um vídeo.",
        "- **Engajamento não é lead.** A métrica é curtida e comentário; o objetivo da @impulsostone é a inscrição. "
        "Nos comentários, os pedidos de contato (\"quero\", \"qual o link\") são igualmente raros no top e nos "
        "comuns (perto de 5%).",
        "- **Só Reels do Instagram**, sem compartilhamentos e salvamentos (não são públicos); carrossel e Shorts "
        "ficaram fora.",
        "- **Curtidas ocultas:** perfis que escondem as curtidas de alguns Reels foram tratados à parte; nos que "
        "escondem só uma parte, a taxa pode estar otimista.",
        "- **Seguidores de uma data só** (11/11) para todos os Reels, inclusive os mais antigos.",
        "- **Teste e meça.** O melhor uso deste playbook é gravar Reels seguindo as recomendações e comparar a taxa "
        "e os cliques deles com os anteriores da @impulsostone.",
        "",
    ]


def main():
    d = carregar()
    partes = (cabecalho(d) + resumo(d) + metodo(d) + retrato_top(d) + o_que_fazer(d) + o_que_evitar(d) + nao_faz_diferenca(d)
              + diagnostico_stone(d) + perfis(d) + ganchos(d) + criativos(d) + limites())
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text("\n".join(partes).rstrip() + "\n")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(partes)} linhas")


if __name__ == "__main__":
    main()
