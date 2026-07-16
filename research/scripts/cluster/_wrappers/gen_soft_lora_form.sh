#!/bin/bash
#SBATCH --job-name=lora_soft_form
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_ood_soft_lora_%j.out
export ARM=soft
export RESEARCH_DB=/vol/bitbucket/jjg25/LinguistOS/research/runs/lora_ood_soft_lora.db
export LORA_ADAPTER_PATH=/vol/bitbucket/jjg25/LinguistOS/research/runs/lora/qwen3_1p7b_form_given
bash /vol/bitbucket/jjg25/LinguistOS/research/scripts/cluster/lora_ood_eval_arm.sh
