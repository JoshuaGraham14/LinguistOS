#!/bin/bash
#SBATCH --job-name=lora_nat_soft_ni
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_ood_nat_soft_no_inject_%j.out
export DB_PATH=/vol/bitbucket/jjg25/LinguistOS/research/runs/lora_ood_soft_lora_no_inject.db
export METHOD_NAME=direction_2_lora_soft_ood_n36
export LABEL=soft_lora_no_inject
export EVALUATOR=both
export RESUME=1
bash /vol/bitbucket/jjg25/LinguistOS/research/scripts/cluster/lora_ood_naturalness_arm.sh
