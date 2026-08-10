#!/bin/bash
# Welsh LoRA teacher: GPT-5.5 plain Fix-B, periphrastic-only, length 4–8.
#
# Usage (from LinguistOS-welsh):
#   sbatch research/scripts/cluster/welsh_frontier_gpt55_plain_n150_peri.sh

#SBATCH --job-name=w_gpt55_pl_peri
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=36:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_frontier_gpt55_plain_n150_peri_%j.out

set -euo pipefail
export ARM=plain
export RESUME="${RESUME:-1}"
# shellcheck disable=SC1091
source /vol/bitbucket/jjg25/LinguistOS-welsh/research/scripts/cluster/welsh_frontier_gpt55_n150_peri_body.sh
