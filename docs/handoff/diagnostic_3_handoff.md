# Handoff: Diagnostic 3 — Spanish sentence binding (3A / 3B / 3C)

Copy this into a new chat to run, re-score, or extend the Diagnostic 3 series.

---

## Where you are

| Diagnostic | Status | What it tested |
|---|---|---|
| **2A** | Complete | Full paradigm tables (n=150) — knowledge side |
| **3A** | Ready to run | Plain-text sentence, 2A hints, T=0, 1/cell |
| **3B** | Planned | Production `build_prompt` (JSON, short, no 2A hints) |
| **3C** | Planned | Same as 3B, T=0.7, 10 samples/cell (1.7B) |

**Registry:** `research/diagnostics/registry.yaml`  
**Script:** `research/prototyping/diagnostic_3_spanish_sentence_qwen_spike.py`

---

## Diagnostic 3A design

- **150 verbs** — same manifest as Diagnostic 2A  
- **4,650 cells** per model (5 tenses × 6 persons + participle)  
- **Prompt:** plain Spanish sentence; reuses `TENSE_PHRASE` and `SUBJECT_HINTS` from Diagnostic 2  
- **No** CEFR, length band, JSON, or gold-form injection  
- **Decoding:** temperature 0, 1 sentence per cell  
- **Score:** `expected_form_match` — gold token in sentence  
- **Summary:** sentence pass rate + **binding gap** vs 2A strict (joins `eval_diagnostic_2a_n150_paradigm_qwen_results.json`)

### Scale per model (3A)

| Calls | Cells scored |
|---|---|
| **4,650** | 4,650 |

× 3 models (0.6B, 1.7B, 4B).

---

## How to run

```bash
python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike --dry-run

python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \
  --variant diagnostic_3a --models qwen17b --limit 5

python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \
  --variant diagnostic_3a --resume
```

Cluster: `sbatch research/scripts/cluster/diagnostic_3a_n150_gpu.sh`

---

## Artifacts (3A)

| Artifact | Path |
|---|---|
| Script | `research/prototyping/diagnostic_3_spanish_sentence_qwen_spike.py` |
| Verb list | `research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv` |
| 2A join | `docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json` |
| **3A results** | `docs/spike-results/eval_diagnostic_3a_n150_sentence_qwen_results.json` |
| Cluster | `research/scripts/cluster/diagnostic_3a_n150_gpu.sh` |

---

## Do not

- Compare binding gap to Diagnostic **2B** — use **2A strict** slot scores only.  
- Add explicit overlay or form injection in 3A — that belongs in Diagnostic 4 / form-injection work.  
- Expect overall pass rate to match the old ~21% baseline (different verbs, T=0, no length/JSON).
