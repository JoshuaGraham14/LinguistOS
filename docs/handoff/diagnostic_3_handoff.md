# Handoff: Diagnostic 3 — Spanish sentence binding (3A / 3B / 3C / 3D)

Copy this into a new chat to run, re-score, or extend the Diagnostic 3 series.

---

## Where you are

| Diagnostic | Status | What it tested |
|---|---|---|
| **2A** | Complete | Full paradigm tables (n=150) — knowledge side |
| **3A** | Complete | Plain-text sentence, 2A hints, T=0, 1/cell |
| **3B** | **New run** | Production JSON + **same 3A hints**, T=0, 1/cell |
| **3C** | Complete (was old 3B) | Production `build_prompt`, JSON, short, no hints, T=0 |
| **3D** | Complete (was old 3C) | Same as 3C, T=0.7, 10 samples/cell, pass@10 (1.7B) |

**Registry:** `research/diagnostics/registry.yaml`  
**Script:** `research/prototyping/diagnostic_3_spanish_sentence_qwen_spike.py`

---

## Variant summary (ablation ladder)

| Variant | Prompt | Output | T | Samples | Models |
|---------|--------|--------|---|---------|--------|
| **3A** | Plain text, 2A `TENSE_PHRASE` / `SUBJECT_HINTS` | One Spanish sentence | 0 | 1 | 0.6B, 1.7B, 4B |
| **3B** | `build_prompt` JSON + **3A hint overlay** | JSON + translation | 0 | 1 | 0.6B, 1.7B, 4B |
| **3C** | `build_prompt` baseline (no hints) | JSON + translation | 0 | 1 | 0.6B, 1.7B, 4B |
| **3D** | Same as 3C | JSON (10 candidates) | 0.7 | 10 | 1.7B only |

All variants: **4,650 cells** per model (150 verbs × 31 slots), same gold forms as 2A.

**Key comparisons:** 3A vs 3B (plain vs JSON, hints held); 3B vs 3C (hints vs no hints, JSON held).

---

## How to run

```bash
python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike --dry-run \
  --variant diagnostic_3b

python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \
  --variant diagnostic_3b --models qwen17b --limit 5 --resume
```

Cluster:
- `sbatch research/scripts/cluster/diagnostic_3a_n150_gpu.sh`
- `sbatch research/scripts/cluster/diagnostic_3b_n150_gpu.sh`  ← new bridge variant
- `sbatch research/scripts/cluster/diagnostic_3c_n150_gpu.sh`
- `sbatch research/scripts/cluster/diagnostic_3d_n150_gpu.sh`

---

## Artifacts

| Variant | Results JSON | Cluster script |
|---------|--------------|----------------|
| 3A | `docs/spike-results/eval_diagnostic_3a_n150_sentence_qwen_results.json` | `diagnostic_3a_n150_gpu.sh` |
| 3B | `docs/spike-results/eval_diagnostic_3b_n150_sentence_qwen_results.json` | `diagnostic_3b_n150_gpu.sh` |
| 3C | `docs/spike-results/eval_diagnostic_3c_n150_sentence_qwen_results.json` | `diagnostic_3c_n150_gpu.sh` |
| 3D | `docs/spike-results/eval_diagnostic_3d_n150_sentence_qwen_results.json` | `diagnostic_3d_n150_gpu.sh` |

2A join for binding gap: `docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json`

Diagnostic 4 baseline for pairing: **3C** (production, no hints).

---

## Do not

- Compare binding gap to Diagnostic **2B** — use **2A strict** only.  
- Add explicit overlay or form injection in 3A–3D (that is Diagnostic 4).  
- Confuse old naming: pre-rename **3B ≈ current 3C**, old **3C ≈ current 3D**.
