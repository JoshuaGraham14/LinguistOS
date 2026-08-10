#!/bin/bash
# Train balanced Welsh Qwen3-1.7B LoRA with gold-form injection.

#SBATCH --job-name=w_lora_form
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_lora_form_balanced_%j.out

set -euo pipefail
export EXPERIMENT=lora-form
# shellcheck disable=SC1091
source /vol/bitbucket/jjg25/LinguistOS-welsh/research/scripts/cluster/welsh_lora_sft_balanced_body.sh
