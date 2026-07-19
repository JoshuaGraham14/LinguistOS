#!/bin/bash
# One-cell GPU pre-flight for hard force + per-row morphology bans.

#SBATCH --job-name=d3_morph_pre
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=00:30:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_3_morph_preflight_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
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

if [[ -f /vol/cuda/12.0.0/setup.sh ]]; then
  # shellcheck disable=SC1091
  source /vol/cuda/12.0.0/setup.sh
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

python3 - <<'PY'
from research.generation.constrained_hf import ConstrainedHFHardMorphPlainBGenerator
from research.generation.morph_bans import banned_surfaces_in_text

constraints = {
    "tense": "present",
    "person": "2nd",
    "number": "singular",
    "expected_form": "buscas",
}
generator = ConstrainedHFHardMorphPlainBGenerator(
    model="Qwen/Qwen3-1.7B",
    temperature=0.0,
    num_beams=8,
)
outputs = generator.generate(
    "buscar",
    "to search",
    constraints,
    1,
    target_language="es",
    sentence_length="short",
)
assert outputs, "hard+morph pre-flight returned no parsed sentence"
sentence = outputs[0]["sentence"]
ban_set = generator._job_morph_ban_set("buscar", constraints)
assert ban_set is not None
hits = banned_surfaces_in_text(sentence, ban_set)
assert not hits, f"hard+morph pre-flight emitted banned surfaces: {sorted(hits)}"
assert "buscas" in {token.strip(".,;:!?¡¿").casefold() for token in sentence.split()}
print(f"Direction 3 pre-flight PASS: {sentence}")
PY
