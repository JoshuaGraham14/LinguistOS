#!/bin/bash
#SBATCH --job-name=lora06_kick
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_06b_kickoff_matrix_%j.out
#
# Runs after both 0.6B LoRA train jobs (set --dependency=afterok:A:B at submit).
# Submits the full 18-arm OOD matrix + naturalness from inside this job.
set -euo pipefail
PROJECT=/vol/bitbucket/jjg25/LinguistOS
cd "${PROJECT}"
bash "${PROJECT}/research/scripts/cluster/lora_06b_matrix_submit.sh"
