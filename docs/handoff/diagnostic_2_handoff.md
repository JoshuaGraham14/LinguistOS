# Handoff: Diagnostic 2 — Spanish paradigm isolation (2A + 2B)

Copy this into a new chat to implement, re-score, or extend the Diagnostic 2 series.

---

## Where you are

| Diagnostic | Status | What it tested |
|---|---|---|
| **1A** | Complete | Produce one form (past tense yo + participle), EN + ES, n=25 manifest |
| **1B** | Complete | Yes/no judge on same forms |
| **2A** | Complete | Full Spanish paradigm tables + participle (n=150) |
| **2B** | Complete | Single-form production (every person × tense, n=150) |
| **3** | Planned | Sentence binding on same verbs (compare to 2A) |

**Registry:** `research/diagnostics/registry.yaml`  
**Related exploratory work:** Experiment 3 (5 verbs), Exp 3B (paired vs sentence EF), Exp 10 (`spanish_grid_knowledge_vs_sentence.py`)

---

## What Diagnostic 2 asks

**Can the model produce Spanish verb forms when asked directly — as a full table (2A) or one form at a time (2B)?**

This is the rigorous version of Experiment 3. If the model can list forms in a paradigm table (2A) but fails in sentence generation (Diagnostic 3), the problem is **binding at generation time**, not missing knowledge in the weights.

Diagnostic 1A/1B only tested **two slots** (pretérito yo + participio). Diagnostic 2 tests **five indicative tenses × six persons**, plus **past participle**.

---

## Variants

| Variant | CLI | One call asks for | Gold slots per call |
|---|---|---|---|
| **2A** | `--probe-mode diagnostic_2a` | List yo, tú, él, nos, vos, ellos (indicative); or participle (D1A ask) | 6 or 1 |
| **2B** | `--probe-mode diagnostic_2b` | One person + number for that tense; or participle | 1 |

Legacy aliases still accepted: `full_paradigm` → 2A, `single_slot` → 2B.

### Scoring

| Variant | Metrics |
|---|---|
| **2A** | **Strict** (slot-level, label-aware) + **Perfect** (call-level 6/6) |
| **2B** | **Pass rate** (first token matches gold, like D1A) |

Assignment and form-presence metrics remain in code for re-scoring but are not headline results.

### Scale per model

| Variant | Calls | Form slots scored |
|---|---|---|
| **2A** | 150 × 6 tenses = **900** | 4,650 slot scores |
| **2B** | 150 × (5×6 + 1) = **4,650** | 4,650 |
| **Total** | **5,550** calls/model | |

× 3 models (0.6B, 1.7B, 4B).

---

## Design

### Verbs

- **Language:** Spanish only.
- **Sample:** **150 verbs** — 50 per frequency tier (high / mid / low), regularity pooled in analysis.
- **Selection:** `python -m research.scripts.select_experiment_verbs --experiment diagnostic_2`  
  writes `manifest_diagnostic_2_paradigm_n150.csv` (seed 42).

### Tenses

Five **indicative** (six-person paradigms): present, preterite, imperfect, future, conditional.  
Plus **past participle** (one form per verb).

### Models

| Key | Checkpoint |
|---|---|
| `qwen06b` | `Qwen/Qwen3-0.6B` |
| `qwen17b` | `Qwen/Qwen3-1.7B` |
| `qwen4b` | `Qwen/Qwen3-4B` |

Greedy (`temperature=0`), thinking off.

### Gold forms

Use **verbecc** via `research/evaluation/lexicon/frequency.py` — not hand-coded paradigms.

---

## Artifacts

| Artifact | Path |
|---|---|
| Script | `research/prototyping/diagnostic_2_spanish_paradigm_qwen_spike.py` |
| Verb list | `research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv` |
| **2A results** | `docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json` |
| **2B results** | `docs/spike-results/eval_diagnostic_2b_n150_single_slot_qwen_results.json` |
| **2A write-up** | `docs/experiment-results/diagnostic_2a_n150_paradigm.md` |
| **2B write-up** | `docs/experiment-results/diagnostic_2b_n150_single_slot.md` |
| Re-score 2A | `python3 -m research.scripts.rescore_diagnostic_2a_paradigm` |
| Cluster script | `research/scripts/cluster/diagnostic_2_n150_gpu.sh` |

---

## How to run

```bash
python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike --dry-run

python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
  --probe-mode diagnostic_2a --models qwen17b --limit 2

python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
  --probe-mode both --resume
```

Cluster: `sbatch research/scripts/cluster/diagnostic_2_n150_gpu.sh`

---

## Next: Diagnostic 3 (sentence binding)

Compare sentence generation (one required form per verb) against **2A strict** on the same cell. See conversation notes for design (150 verbs, T=0, paired cells).

---

## Do not

- Use the minimal Exp 3 prompt — it failed badly.
- Use hand-coded gold for manifest verbs — use verbecc.
- Ask for a six-person participle paradigm — participle is always one form.
