#!/bin/bash
# Offline re-score Welsh Diag 2A n10 results with welsh_paradigm_v3
# (spoken 1pl aux rydyn/roedden + rhoi/rhoddi stem doublet).
# No model calls — CPU-only JSON rewrite. Does not touch other jobs.
#
# Usage (from LinguistOS-welsh tree):
#   sbatch research/scripts/cluster/welsh_diag2a_n10_rescore_v3.sh

#SBATCH --job-name=welsh_d2a_rsc
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --gres=gpu:1
#SBATCH --time=00:20:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_diag2a_n10_rescore_v3_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
VENV="${PROJECT}/.venv"
MANIFESTS="${PROJECT}/research/welsh/manifests"
GPT_JSON="${MANIFESTS}/eval_diagnostic_2a_welsh_n10_gpt55_results.json"
QWEN_JSON="${MANIFESTS}/eval_diagnostic_2a_welsh_n10_qwen17b_results.json"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Missing venv at ${VENV}" >&2
  exit 1
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

echo "=== Welsh Diag 2A v3 rescore — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  scoring_version=welsh_paradigm_v3"

for SRC in "${GPT_JSON}" "${QWEN_JSON}"; do
  if [[ ! -f "${SRC}" ]]; then
    echo "ERROR: missing ${SRC}" >&2
    exit 1
  fi
  BAK="${SRC%.json}.v2_backup.json"
  if [[ ! -f "${BAK}" ]]; then
    cp -a "${SRC}" "${BAK}"
    echo "  backed up → ${BAK}"
  else
    echo "  backup exists: ${BAK}"
  fi
  echo ""
  echo "=== rescore $(basename "${SRC}") ==="
  python3 -m research.prototyping.diagnostic_2_welsh_paradigm_qwen_spike \
    --rescore "${SRC}"
done

echo ""
echo "=== Welsh Diag 2A v3 rescore done $(date -Is) ==="
python3 - <<'PY'
import json
from pathlib import Path

manifests = Path("research/welsh/manifests")
for name in (
    "eval_diagnostic_2a_welsh_n10_gpt55_results.json",
    "eval_diagnostic_2a_welsh_n10_qwen17b_results.json",
):
    p = manifests / name
    obj = json.loads(p.read_text())
    print(f"\n{name}  scoring_version={obj.get('scoring_version')}")
    for key, s in obj.get("summary", {}).get("per_model", {}).items():
        print(
            f"  {key}: overall={s['overall_strict']['slot_recall']} "
            f"perfect={s['overall_perfect_paradigm']['perfect_paradigm_rate']} "
            f"syn={s['synthetic_strict']['slot_recall']} "
            f"peri={s['periphrastic_strict']['slot_recall']} "
            f"aux={s.get('periphrastic_aux_recall')} "
            f"vn={s.get('periphrastic_vn_recall')}"
        )
PY
