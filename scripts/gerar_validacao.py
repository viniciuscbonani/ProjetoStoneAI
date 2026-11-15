"""Gera a página de validação manual (documento do projeto: mínimo de 50 publicações).

Sorteia 50 Reels anotados (25 top, 25 controle, semente fixa), embaralha a ordem e esconde o grupo
e a resposta do Gemini, para a anotação manual ser às cegas. A página mostra quadros, legenda,
transcrição e link; salva as respostas no navegador e exporta um JSON, que vai para
data/interim/validacao_manual.json e é comparado por scripts/concordancia.py.

Uso:
    .venv/bin/python scripts/gerar_validacao.py
    xdg-open data/interim/validacao.html
"""

import base64
import csv
import html
import json
import random
from pathlib import Path

from rubrica import Anotacao

RAIZ = Path(__file__).resolve().parent.parent
N_POR_GRUPO = 25
SEMENTE = 7
# Os campos que sustentam os achados; os demais ficam fora da validação.
CAMPOS = ["formato_video", "tipo_hook", "tema_principal", "fala_de_negocio", "tem_rosto",
          "criador_e_empreendedor_real", "texto_na_tela", "tem_cta", "tipo_cta", "abordagem"]
QUADROS = ["gancho_0s", "gancho_1s", "gancho_3s", "meio_40", "final_2s"]


def opcoes(campo: str) -> list[str]:
    tipo = Anotacao.model_fields[campo].annotation
    return ["sim", "nao"] if tipo is bool else list(tipo.__args__)


def main() -> None:
    anot = {a["shortCode"]: a for a in map(json.loads, open(RAIZ / "data" / "processed" / "anotacoes.jsonl"))
            if a["versao_rubrica"] == "v2"}
    amostra = [r for r in csv.DictReader(open(RAIZ / "data" / "processed" / "amostra.csv")) if r["shortCode"] in anot]
    rng = random.Random(SEMENTE)
    escolhidos = []
    for grupo in ("top", "controle"):
        escolhidos += rng.sample([r for r in amostra if r["grupo"] == grupo], N_POR_GRUPO)
    rng.shuffle(escolhidos)

    cartoes = []
    for i, r in enumerate(escolhidos, 1):
        sc = r["shortCode"]
        trans_path = RAIZ / "data" / "midia" / sc / "transcricao.json"
        trans = json.loads(trans_path.read_text())["texto"] if trans_path.exists() else ""
        # Imagens embutidas: a página funciona sozinha, aberta de qualquer lugar.
        imgs = "".join(
            f'<img src="data:image/jpeg;base64,{base64.b64encode((RAIZ / "data" / "midia" / sc / f"q_{q}.jpg").read_bytes()).decode()}" title="{q}">'
            for q in QUADROS)
        campos = "".join(
            f'<div class="campo"><span class="nome">{c.replace("_", " ")}</span><div class="opcoes">'
            + "".join(f'<label><input type="radio" name="{sc}|{c}" value="{o}">{o.replace("_", " ")}</label>'
                      for o in opcoes(c))
            + "</div></div>" for c in CAMPOS)
        cartoes.append(f"""
<section data-sc="{sc}"><h2>{i}/{len(escolhidos)} · <a href="{r['url']}" target="_blank">abrir no Instagram</a>
 · {float(r['duracao_s']):.0f}s</h2>
<div class="quadros">{imgs}</div>
<p><b>Legenda:</b> {html.escape(r['legenda'][:600]) or '(sem legenda)'}</p>
<p><b>Transcrição:</b> {html.escape(trans[:1200]) or '(sem fala)'}</p>
<div class="campos">{campos}</div></section>""")

    pagina = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Validação manual</title>
<style>
:root {{ --bg:#fafafa; --fg:#1d1d1f; --card:#fff; --borda:#ddd; --destaque:#0b6bcb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161616; --fg:#eee; --card:#222; --borda:#3a3a3a; --destaque:#5aa9ff; }} }}
body {{ font-family: system-ui, sans-serif; background:var(--bg); color:var(--fg); max-width:1100px; margin:0 auto; padding:16px; }}
section {{ background:var(--card); border:1px solid var(--borda); border-radius:10px; padding:16px; margin:16px 0; }}
.quadros {{ display:flex; gap:6px; overflow-x:auto; }} .quadros img {{ height:220px; border-radius:6px; }}
.campos {{ display:flex; flex-direction:column; gap:10px; margin-top:14px; }}
.campo {{ display:grid; grid-template-columns:200px 1fr; gap:10px; align-items:start;
  padding-top:10px; border-top:1px solid var(--borda); }}
.nome {{ font-weight:600; padding-top:4px; }}
.opcoes {{ display:flex; flex-wrap:wrap; gap:6px; }}
.opcoes label {{ display:inline-flex; align-items:center; gap:4px; padding:4px 10px; border:1px solid var(--borda);
  border-radius:999px; cursor:pointer; white-space:nowrap; }}
.opcoes label:has(input:checked) {{ border-color:var(--destaque); background:color-mix(in srgb, var(--destaque) 18%, transparent); }}
.opcoes input {{ margin:0; }}
@media (max-width: 640px) {{ .campo {{ grid-template-columns:1fr; }} }}
a {{ color:var(--destaque); }}
#barra {{ position:sticky; top:0; background:var(--bg); padding:8px 0; border-bottom:1px solid var(--borda); }}
button {{ font-size:15px; padding:6px 14px; }}
</style></head><body>
<div id="barra"><b>Validação manual</b> · <span id="prog"></span> ·
<button onclick="exportar()">Exportar respostas (JSON)</button></div>
<p>Marque cada campo olhando os quadros, a legenda e a transcrição (ou o Reel no Instagram).
As respostas ficam salvas neste navegador. No fim, exporte e salve como
<code>data/interim/validacao_manual.json</code>.</p>
{''.join(cartoes)}
<script>
const CHAVE = "validacao_stone_v1", TOTAL = {len(escolhidos) * len(CAMPOS)};
let r = {{}}; try {{ r = JSON.parse(localStorage.getItem(CHAVE) || "{{}}"); }} catch (e) {{}}
function prog() {{ document.getElementById("prog").textContent = Object.keys(r).length + "/" + TOTAL + " respostas"; }}
document.querySelectorAll("input[type=radio]").forEach(el => {{
  if (r[el.name] === el.value) el.checked = true;
  el.addEventListener("change", () => {{ r[el.name] = el.value; try {{ localStorage.setItem(CHAVE, JSON.stringify(r)); }} catch (e) {{}} prog(); }});
}});
prog();
function exportar() {{
  const out = {{}};
  for (const [k, v] of Object.entries(r)) {{ const [sc, c] = k.split("|"); (out[sc] ||= {{}})[c] = v; }}
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {{type: "application/json"}}));
  a.download = "validacao_manual.json"; a.click();
}}
</script></body></html>"""
    destino = RAIZ / "data" / "interim" / "validacao.html"
    destino.write_text(pagina)
    (RAIZ / "data" / "interim" / "validacao_reels.json").write_text(json.dumps([r["shortCode"] for r in escolhidos]))
    print(f"{len(escolhidos)} Reels, {len(CAMPOS)} campos -> {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
