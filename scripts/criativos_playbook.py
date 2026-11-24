"""Gera os criativos do playbook (#19) com o agente, no modo gerar_criativo.

Cada briefing é uma execução (3 criativos, ~45 s, 4 a 6 chamadas ao Gemini). Os briefings cobrem as lacunas do
diagnóstico da @impulsostone (vídeos de mais de 90 s, gancho de curiosidade) em temas e setores diferentes.
Grava as saídas completas em data/processed/playbook_criativos.json, lido por scripts/gerar_playbook.py.

Uso: .venv/bin/python scripts/criativos_playbook.py
"""

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from agente import executar  # noqa: E402

SAIDA = RAIZ / "data/processed/playbook_criativos.json"

BRIEFINGS = [
    {
        "mode": "gerar_criativo",
        "query": "Reels de educação financeira para empreendedores de pequenos negócios: separar o dinheiro da "
                 "empresa do dinheiro pessoal. Quero que ele convide a pessoa a se inscrever no Impulso Stone.",
    },
    {
        "mode": "gerar_criativo",
        "segment": "beleza",
        "query": "Reels para donas e donos de salão de beleza sobre como cobrar o preço certo pelo serviço, "
                 "terminando com o convite para participar do Impulso Stone.",
    },
    {
        "mode": "gerar_criativo",
        "segment": "alimentacao",
        "query": "Reels para quem vende comida feita em casa sobre como vender mais pelo Instagram e pelo "
                 "WhatsApp, terminando com o convite para participar do Impulso Stone.",
    },
]


def main():
    resultados = json.loads(SAIDA.read_text()) if SAIDA.exists() else []
    feitos = {r["entrada"]["query"] for r in resultados}
    for briefing in BRIEFINGS:
        if briefing["query"] in feitos:
            print("já feito:", briefing["query"][:60])
            continue
        inicio = time.time()
        saida = executar(briefing)
        print(f"{saida.run_id}: {len(saida.creatives)} criativos em {time.time() - inicio:.0f} s", flush=True)
        resultados.append({"entrada": briefing, "saida": saida.model_dump(mode="json")})
        SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
