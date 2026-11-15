#!/usr/bin/env bash
# Sobe N processos de transcrição desacoplados do terminal, cada um com T núcleos.
# Uso: scripts/transcrever_paralelo.sh 7 2
set -euo pipefail
cd "$(dirname "$0")/.."
N=${1:-7}; T=${2:-2}
mkdir -p data/interim/logs
for ((k = 0; k < N; k++)); do
  setsid nohup .venv/bin/python scripts/transcrever.py --parte "$k" --partes "$N" --threads "$T" \
    >> "data/interim/logs/transcricao_${N}x${T}_$k.log" 2>&1 < /dev/null &
done
