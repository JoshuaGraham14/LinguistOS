# Handoff: Diagnostic 3 — Spanish sentence binding (3A / 3B / 3C)

Copy this into a new chat to run, re-score, or extend the Diagnostic 3 series.

---

## Where you are

| Diagnostic | Status | What it tested |
|---|---|---|
| **2A** | Complete | Full paradigm tables (n=150) — knowledge side |
| **3A** | Ready to run | Plain-text sentence, 2A hints, T=0, 1/cell |
| **3B** | Ready to run | Production `build_prompt`, JSON, short, T=0, 1/cell |
| **3C** | Planned | Same as 3B, T=0.7, 10 samples/cell (1.7B) |

**Registry:** `research/diagnostics/registry.yaml`  
**Script:** `research/prototyping/diagnostic_3_spanish_sentence_qwen_spike.py`

---

## Variant summary

| Variant | Prompt | Output | T | Samples | Models |
|---------|--------|--------|---|---------|--------|
| **3A** | Plain text, 2A `TENSE_PHRASE` / `SUBJECT_HINTS` | One Spanish sentence | 0 | 1 | 0.6B, 1.7B, 4B |
| **3B** | `build_prompt` baseline (no CEFR, no 2A hints) | JSON + translation | 0 | 1 | 0.6B, 1.7B, 4B |
| **3C** | Same as 3B | JSON (10 candidates) | 0.7 | 10 | 1.7B only |

All variants: **4,650 cells** per model (150 verbs × 31 slots), same gold forms as 2A.

---

## How to run

```bash
python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike --dry-run \
  --variant diagnostic_3b

python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \
  --variant diagnostic_3a --models qwen17b --limit 5

python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \
  --variant diagnostic_3b --resume
```

Cluster:
- `sbatch research/scripts/cluster/diagnostic_3a_n150_gpu.sh`
- `sbatch research/scripts/cluster/diagnostic_3b_n150_gpu.sh`

---

## Artifacts

| Variant | Results JSON | Cluster script |
|---------|--------------|----------------|
| 3A | `docs/spike-results/eval_diagnostic_3a_n150_sentence_qwen_results.json` | `diagnostic_3a_n150_gpu.sh` |
| 3B | `docs/spike-results/eval_diagnostic_3b_n150_sentence_qwen_results.json` | `diagnostic_3b_n150_gpu.sh` |
| 3C | `docs/spike-results/eval_diagnostic_3c_n150_sentence_qwen_results.json` | (planned) |

2A join for binding gap: `docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json`

---

## Do not

- Compare binding gap to Diagnostic **2B** — use **2A strict** only.  
- Add explicit overlay or form injection in 3A/3B/3C.  
- Add 2A-style tense hints to 3B/3C (that is 3A’s role).
