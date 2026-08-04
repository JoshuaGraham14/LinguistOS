#!/bin/bash
# Welsh LLM-judge audit — 10 verbs × 42 cells × 1 sample (420 sentences).
#
# Usage:
#   sbatch research/scripts/cluster/welsh_judge_audit_n10_gpu.sh
#   METHOD=welsh_judge_audit_inject_n1 sbatch --export=ALL,METHOD \
#     research/scripts/cluster/welsh_judge_audit_n10_gpu.sh
#
# Env overrides:
#   METHOD   method YAML name (default: welsh_judge_audit_vanilla_n1)
#   RESUME   0/1 (default: 0)
#   DB / EXPORT optional explicit paths

#SBATCH --job-name=welsh_jdg_n10
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_judge_audit_n10_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
VENV="${PROJECT}/.venv"
: "${METHOD:=welsh_judge_audit_vanilla_n1}"
: "${RESUME:=0}"
: "${BENCHMARK:=welsh_transfer_n10}"
: "${DB:=${PROJECT}/research/runs/${METHOD}.db}"
: "${EXPORT:=${PROJECT}/research/welsh/manifests/${METHOD}_summary.json}"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs" "${PROJECT}/research/welsh/manifests"

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

if [[ -f /vol/cuda/12.0.0/setup.sh ]]; then
  # shellcheck disable=SC1091
  source /vol/cuda/12.0.0/setup.sh
fi

cd "${PROJECT}"
export PROJECT
export RESEARCH_DB="${DB}"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
# Reuse main-tree HF caches
export HF_HOME="/vol/bitbucket/jjg25/LinguistOS/.cache/huggingface"
export TRANSFORMERS_CACHE="${HF_HOME}"
export LTP_PATH="/vol/bitbucket/jjg25/LinguistOS/.cache/language_tool_python"
if [[ -f "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
fi
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY not set (research/.env on cluster)" >&2
  exit 1
fi

echo "=== Welsh judge audit n10 — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  BENCHMARK=${BENCHMARK} METHOD=${METHOD}"
echo "  RESEARCH_DB=${RESEARCH_DB}"
echo "  RESUME=${RESUME}"
nvidia-smi || true
python3 -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
python3 -c "from research.evaluation.sentence.naturalness_llm_judge import WELSH_PROMPT_VERSION; print('welsh_prompt', WELSH_PROMPT_VERSION)"

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG+=(--resume)
fi

python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --with-naturalness-judge \
  --skip-experiment-group-metrics \
  "${RESUME_FLAG[@]}"

echo ""
echo "=== Exporting judge audit summary ==="
python3 -m research.scripts.audit_welsh_judge_n10 \
  --db "${RESEARCH_DB}" \
  --out "${EXPORT}"

echo ""
echo "=== Welsh judge audit n10 done $(date -Is) ==="
echo "DB: ${RESEARCH_DB}"
echo "Summary: ${EXPORT}"
