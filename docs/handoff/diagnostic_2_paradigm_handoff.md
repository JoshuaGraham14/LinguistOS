# Handoff: Diagnostic 2 — Spanish paradigm isolation (Exp 3 rigor)

Copy this into a new chat to implement and run Diagnostic 2.

---

## Where you are

| Diagnostic | Status | What it tested |
|---|---|---|
| **1A** | Complete | Produce one form (past tense yo + participle), EN + ES, n=25 manifest |
| **1B** | Complete | Yes/no judge on same forms |
| **2** | **Next** | Full Spanish paradigm tables + single-form asks (Exp 3 spirit, census-grounded) |

**Registry:** `research/diagnostics/registry.yaml`  
**Related exploratory work:** Experiment 3 (5 verbs), Exp 3B (paired vs sentence EF), Exp 10 (`spanish_grid_knowledge_vs_sentence.py`)

---

## What Diagnostic 2 asks

**Can the model produce Spanish verb forms when asked directly — as a full table of six persons, or as one form at a time — and does that depend on frequency and irregularity?**

This is the rigorous version of Experiment 3. If the model can list *saqué* in a preterite paradigm but fails in sentence generation, the problem is **binding at generation time**, not missing knowledge in the weights.

Diagnostic 1A/1B only tested **two slots** (pretérito yo + participio). Diagnostic 2 tests **five indicative tenses × six persons**, plus **past participle** (one form, matching D1A), with single-slot asks for every cell.

---

## Design (agreed)

### Verbs

- **Language:** Spanish only.
- **Sample:** **150 verbs** — all Spanish rows from `manifest_diagnostic_1_n25.csv` (25 per cell):
  - `high_regular`, `high_irregular`, `mid_regular`, `mid_irregular`, `low_regular`, `low_irregular`
- **Selection:** `python -m research.scripts.select_experiment_verbs --experiment diagnostic_2`  
  writes `manifest_diagnostic_2_paradigm_n150.csv` (seed 42, full Spanish subsample).

### Tenses

Five **indicative** (six-person paradigms):

1. present  
2. preterite (pretérito indefinido)  
3. imperfect  
4. future  
5. conditional  

Plus **past participle** (participio pasado) — **one form per verb only** (D1A-compatible prompt; not a six-person paradigm).

### Two probe modes (both required)

Inspired by `spanish_grid_knowledge_vs_sentence.py` and Exp 3:

| Mode | CLI flag | One call asks for | Gold slots per call |
|---|---|---|---|
| **Full paradigm** | `--probe-mode full_paradigm` | List yo, tú, él, nos, vos, ellos (indicative); or participle (D1A ask) | 6 or 1 |
| **Single slot** | `--probe-mode single_slot` | One person + number for that tense; or participle | 1 |

Run **both** on the same 150 verbs. Full paradigm is lenient for indicative (Exp 3 style); participle and single-slot are strict (Diagnostic 1A style).

### Scale per model

| Mode | Calls | Form slots scored |
|---|---|---|
| Full paradigm | 150 × (5 + 1 participle) = **900** | 150×5×6 + 150 = **4,650** |
| Single slot | 150 × (5×6 + 1) = **4,650** | **4,650** |
| **Total** | **5,550** calls/model | **9,300** slot scores/model |

× 3 models (0.6B, 1.7B, 4B) → overnight on one A30 GPU with `--resume` (~2–4 h per model).

### Models (same ladder as D1)

| Key | Checkpoint |
|---|---|
| `qwen06b` | `Qwen/Qwen3-0.6B` |
| `qwen17b` | `Qwen/Qwen3-1.7B` |
| `qwen4b` | `Qwen/Qwen3-4B` |

Greedy (`temperature=0`), thinking off, `unload_model()` between models.

### Gold forms

- **Do not** use the hand-coded `PARADIGMS` dict in `spanish_paradigm_qwen_spike.py`.
- **Do** use **`verbecc`** via `research/evaluation/lexicon/frequency.py` (`_actual_es_form`, `_conjugate_es`) for every (verb, tense, person, number) cell — same source as the census manifest.
- Participle: manifest `gold_participle` or verbecc participio.
- Filter preterite cells with the same `-ía` bug check as `select_experiment_verbs.py`.

### Prompts (use Exp 3 explicit — not minimal)

**System (all modes):**
```
You are a Spanish conjugation assistant. Follow the instruction exactly
and output only the requested verb forms.
```

**Full paradigm — indicative (user)** — `explicit_v1`:
```
Conjugate the Spanish verb "{lemma}" in the {tense_label}.
List all six forms for: yo, tú, él/ella, nosotros, vosotros, ellos.
Reply with only the six conjugated verb forms, one per line.
```

**Full paradigm — participle (user)** — D1A wording:
```
What is the past participle (participio pasado) of the Spanish verb "{lemma}"?
Reply with one word only.
```

**Single slot — indicative (user):**
```
Conjugate the Spanish verb "{lemma}" in the {tense_label}.
Give the form for ({person} person, {number}) — this is the {subject_hint} form.
Reply with only that one conjugated verb — one word, no sentence.
```

**Single slot — participle (user):**
```
Give the participio pasado of the Spanish verb "{lemma}".
Reply with only that one conjugated verb — one word, no sentence.
```

`max_new_tokens`: 256 (indicative paradigm), 64 (single slot and participle).

### Scoring

| Mode | Rule |
|---|---|
| **Full paradigm (indicative)** | Lenient: each gold form counts if it appears **anywhere** in output (NFC + casefold). Same as Exp 3. |
| **Full paradigm (participle)** | Strict: first token must match gold (like D1A). |
| **Single slot** | Strict: first Spanish token must match gold (like D1A). |
| **Secondary (optional)** | Line-order paradigm scoring (yo = line 1, …) for thesis appendix. |

### Output files

| Artifact | Path |
|---|---|
| Script | `research/prototyping/diagnostic_2_spanish_paradigm_qwen_spike.py` |
| Verb list | `research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv` |
| Results (paradigm) | `docs/spike-results/eval_diagnostic_2_n150_paradigm_qwen_results.json` |
| Results (single slot) | `docs/spike-results/eval_diagnostic_2_n150_single_slot_qwen_results.json` |
| Cluster script | `research/scripts/cluster/diagnostic_2_n150_gpu.sh` |

---

## How to run locally (smoke test)

```bash
cd /path/to/LinguistOS
source .venv/bin/activate

python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike --dry-run

python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
  --probe-mode full_paradigm --models qwen17b --limit 2
```

---

## How to run on Imperial DoC cluster

```bash
rsync -avz --exclude '.venv' --exclude '.git' --exclude '__pycache__' \
  /Users/joshuagraham/Desktop/Diss/LinguistOS/ \
  gpucluster2:/vol/bitbucket/jjg25/LinguistOS/

cd /vol/bitbucket/jjg25/LinguistOS
sbatch research/scripts/cluster/diagnostic_2_n150_gpu.sh
```

**Partition:** `a30` (24GB for Qwen3-4B).  
**Expect:** ~2–4 h per model (5,550 greedy calls × decode length).

---

## Analysis plan (after run)

1. **Overall form recall** per model (paradigm + single slot).
2. **By tier** (high/mid/low × regular/irregular) at 1.7B.
3. **By tense** — preterite vs participle vs others; link to D1A on same verbs.
4. **Paradigm vs single-slot gap** — substring inflation check.
5. **Phase 2 (later):** Sentence EF on same verbs (Exp 3B design), especially participle sentences.

---

## Do not

- Use the minimal Exp 3 prompt (`"{lemma}, {tense} tense."`) — it failed badly (+48pp when fixed).
- Use hand-coded gold for manifest verbs — use verbecc.
- Ask for a six-person participle paradigm — participle is always one form.
