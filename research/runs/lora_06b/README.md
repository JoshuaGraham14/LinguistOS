# LoRA scale transfer — Qwen3-0.6B

Isolated tree for the **0.6B** scale-transfer experiment.  
Does **not** overwrite anything under `research/runs/lora/` (Qwen3-1.7B).

## Layout

```text
lora_06b/
  adapters/
    lora_form/           # Experiment A (form given at train)
    lora_no_inject/      # Experiment B (no form at train)
  ood/                   # 18 per-arm sqlite DBs (cluster only; gitignored)
```

## Shared (read-only)

- SFT JSONL from the 1.7B tree: `research/runs/lora/sft_lora_{form,no_inject}_n150.jsonl`
- OOD benchmark: `spanish_lora_ood_n36` (same 36 held-out verbs)

## Cluster workflow

1. Sync **code only** (never rsync `*.db` / `research/runs/` while jobs run).
2. Train adapters:
   ```bash
   sbatch research/scripts/cluster/lora_06b_sft_form.sh
   sbatch research/scripts/cluster/lora_06b_sft_no_inject.sh
   ```
3. After both adapters exist, submit the full 18-arm OOD matrix:
   ```bash
   bash research/scripts/cluster/lora_06b_matrix_submit.sh
   ```

See `docs/gpu/cluster_research_playbook.md` for DB / rsync rules.
