#!/bin/bash
#SBATCH --job-name=lora_inj_ni
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_ood_inj_no_inject_%j.out
export ARM=inject
export RESEARCH_DB=/vol/bitbucket/jjg25/LinguistOS/research/runs/lora_ood_inject_lora_no_inject.db
export LORA_ADAPTER_PATH=/vol/bitbucket/jjg25/LinguistOS/research/runs/lora/qwen3_1p7b_lora_no_inject
bash /vol/bitbucket/jjg25/LinguistOS/research/scripts/cluster/lora_ood_eval_arm.sh
