#!/bin/bash
# Welsh LoRA teacher: GPT-5.5 form-inject Fix-B on welsh_transfer_n150 (6300 cells).
#
# Usage (from LinguistOS-welsh):
#   sbatch research/scripts/cluster/welsh_frontier_gpt55_inject_n150.sh

#SBATCH --job-name=w_gpt55_in150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=48:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_frontier_gpt55_inject_n150_%j.out

set -euo pipefail
export ARM=inject
export RESUME="${RESUME:-1}"
# shellcheck disable=SC1091
source /vol/bitbucket/jjg25/LinguistOS-welsh/research/scripts/cluster/welsh_frontier_gpt55_n150_body.sh
