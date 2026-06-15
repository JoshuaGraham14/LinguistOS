# Spanish paradigm Qwen diagnostic (explicit prompt)

**Experiment:** 3 — Spanish paradigm isolation (explicit prompt)  
**Date run:** 2026-06-12 (explicit-prompt re-run; same commit batch as Exp 1–2 ~16:43 GMT+1)  
**Date documented:** 2026-06-15  
**Track:** Small-model conditioning (supervisor meeting #7)  
**Script:** `research/prototyping/spanish_paradigm_qwen_spike.py` (`prompt_version: explicit_v1`)  
**Raw results:**
- `docs/spike-results/eval_spanish_paradigm_qwen05b_explicit_prompt_results.json`
- `docs/spike-results/eval_spanish_paradigm_qwen17b_explicit_prompt_results.json`  
**Status:** Exploratory spike; not run through `run_experiment.py` or the evaluation pipeline  
**Scope:** Explicit-prompt runs only (after the minimal `"{lemma}, {tense} tense."` prompt was revised). Models: **0.5B** and **1.7B** only (4B not re-run with revised prompt). Minimal-prompt artefact: `docs/spike-results/eval_spanish_paradigm_qwen_spike_results.json`

---

## Purpose

Isolate whether Qwen models **store Spanish conjugation paradigms** when not embedded in sentence generation — separating **morphological knowledge / capacity** from **constrained text generation (CTG)** failures observed in the main benchmark.

One verb and one tense per call. The model must list all six indicative forms (yo → ellos). No constraint YAML, no gold form passed in, no sentence context.

Follows the small-model conditioning diagnostic track (supervisor meeting #7): if paradigms are largely correct in isolation but sentence-level `expected_form_match` fails, the bottleneck is **binding at generation time**, not missing morphology in parameters.

---

## Experimental design

### Stimulus set

Five Spanish verbs × five indicative tenses × six persons = **30 gold forms per verb**, **150 forms per model**.

| Lemma | Tier | Source benchmark |
|-------|------|------------------|
| comer, hablar | common_regular | `spanish_basic` |
| tener | common_irregular | `spanish_challenging` |
| blandir, argüir | rare | `spanish_niche` |

**Tenses (all indicative):** present, preterite, imperfect, future, conditional.

Gold paradigms hard-coded in the spike script (RAE / SpanishDict-style). Duplicate persons (e.g. yo/él both *comía*) scored independently — each of the six slots must appear in the output.

### Models

| Label | Checkpoint | Run with explicit prompt |
|-------|------------|--------------------------|
| qwen05b | `Qwen/Qwen2.5-0.5B-Instruct` | Yes |
| qwen17b | `Qwen/Qwen3-1.7B` | Yes |

### Fixed parameters

| Parameter | Value |
|-----------|-------|
| Device | Apple MPS (local inference) |
| Decoding | Greedy (`temperature=0`, `do_sample=False`) |
| Max new tokens | 256 |
| Qwen3 thinking mode | Disabled |
| Calls per model | 25 (one per verb × tense) |
| Scoring | Each gold form matched anywhere in output (order-independent; Unicode NFC + casefold) |
| Confidence intervals | Wilson 95% CI on form-level recall |

### Prompt (`explicit_v1`)

**System message:**
> You are a Spanish conjugation assistant. Follow the instruction exactly and output only the requested verb forms.

**User message (template):**
```
Conjugate the Spanish verb "{lemma}" in the {tense_label}.
List all six forms for: yo, tú, él/ella, nosotros, vosotros, ellos.
Reply with only the six conjugated verb forms, one per line.
```

`{tense_label}` examples: `present indicative`, `preterite (pretérito indefinido) indicative`, `imperfect indicative`, `simple future indicative`, `conditional indicative`.

**Concrete example — blandir, preterite:**
```
System: You are a Spanish conjugation assistant. Follow the instruction exactly and output only the requested verb forms.
User:   Conjugate the Spanish verb "blandir" in the preterite (pretérito indefinido) indicative.
        List all six forms for: yo, tú, él/ella, nosotros, vosotros, ellos.
        Reply with only the six conjugated verb forms, one per line.
Gold:   blandí, blandiste, blandió, blandimos, blandisteis, blandieron
```

### Primary metric

**Form recall** — proportion of gold surface forms found in the model response (0–6 per call, aggregated over 150 slots per model).

---

## Results

### Aggregate summary (Wilson 95% CI on form recall)

| Model | Forms correct | Form recall | Wilson 95% CI |
|-------|---------------|-------------|---------------|
| **0.5B** | 17 / 150 | 11.3% | 7–17% |
| **1.7B** | 109 / 150 | 72.7% | 65–79% |

### By tier

| Model | Common regular (n=60) | Common irregular (n=30) | Rare (n=60) |
|-------|----------------------|-------------------------|-------------|
| **0.5B** | 10/60 (16.7%; CI 9–28%) | 2/30 (6.7%; CI 2–21%) | 5/60 (8.3%; CI 4–18%) |
| **1.7B** | 52/60 (86.7%; CI 76–93%) | 30/30 (100%; CI 89–100%) | 27/60 (45.0%; CI 33–58%) |

### By tense (all verbs pooled)

| Tense | 0.5B (n=30 forms) | 1.7B (n=30 forms) |
|-------|-------------------|-------------------|
| Present | 11/30 (36.7%) | 14/30 (46.7%) |
| Preterite | 2/30 (6.7%) | 26/30 (86.7%) |
| Imperfect | 0/30 (0%) | 23/30 (76.7%) |
| Future | 4/30 (13.3%) | 22/30 (73.3%) |
| Conditional | 0/30 (0%) | 24/30 (80.0%) |

### Per verb × tense (forms correct / 6)

**0.5B**

| Verb | Tier | Present | Preterite | Imperfect | Future | Conditional | **Total** |
|------|------|---------|-----------|-----------|--------|-------------|-----------|
| comer | common_regular | 4/6 | 2/6 | 0/6 | 0/6 | 0/6 | 6/30 |
| hablar | common_regular | 3/6 | 0/6 | 0/6 | 1/6 | 0/6 | 4/30 |
| tener | common_irregular | 2/6 | 0/6 | 0/6 | 0/6 | 0/6 | 2/30 |
| blandir | rare | 1/6 | 0/6 | 0/6 | 3/6 | 0/6 | 4/30 |
| argüir | rare | 1/6 | 0/6 | 0/6 | 0/6 | 0/6 | 1/30 |

**1.7B**

| Verb | Tier | Present | Preterite | Imperfect | Future | Conditional | **Total** |
|------|------|---------|-----------|-----------|--------|-------------|-----------|
| comer | common_regular | 0/6 | 6/6 | 6/6 | 6/6 | 6/6 | 24/30 |
| hablar | common_regular | 6/6 | 5/6 | 6/6 | 5/6 | 6/6 | 28/30 |
| tener | common_irregular | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | **30/30** |
| blandir | rare | 2/6 | 4/6 | 0/6 | 5/6 | 6/6 | 17/30 |
| argüir | rare | 0/6 | 5/6 | 5/6 | 0/6 | 0/6 | 10/30 |

### Incomplete paradigms — 1.7B (missing gold forms)

| Verb / tense | Score | Missing |
|--------------|-------|---------|
| comer / present | 0/6 | all six (*como* … *comen*) |
| hablar / preterite | 5/6 | *hablasteis* |
| hablar / future | 5/6 | *hablaremos* |
| blandir / present | 2/6 | *blandes*, *blande*, *blandís*, *blanden* |
| blandir / preterite | 4/6 | *blandiste*, *blandisteis* |
| blandir / imperfect | 0/6 | all six |
| blandir / future | 5/6 | *blandiréis* |
| argüir / present | 0/6 | all six |
| argüir / preterite | 5/6 | *argüisteis* |
| argüir / imperfect | 5/6 | *arguíamos* |
| argüir / future | 0/6 | all six |
| argüir / conditional | 0/6 | all six |

0.5B missed at least one form on **every** call (25/25 incomplete). Full missing-form list in the raw JSON.

### Prompt revision effect (same models, prior minimal prompt)

For context on why `explicit_v1` was adopted — minimal prompt was `"{lemma}, {tense} tense."` with no system message:

| Model | Minimal prompt recall | Explicit prompt recall | Change |
|-------|----------------------|------------------------|--------|
| **0.5B** | 3.3% (5/150) | 11.3% (17/150) | +8.0 pp |
| **1.7B** | 24.7% (37/150) | 72.7% (109/150) | **+48.0 pp** |

---

## Findings

1. **Explicit task framing is necessary on small models.** The revised prompt raised 1.7B form recall from 25% to 73%. A large share of earlier poor scores reflected **instruction ambiguity**, not absent morphology — especially at 1.7B.

2. **1.7B has strong paradigm knowledge for high-frequency Spanish.** *Tener* scored 30/30 across all tenses. Common regular verbs (*comer*, *hablar*) reached 80–93% per verb. This is inconsistent with a pure capacity-floor explanation at 1.7B.

3. **Rare verbs remain weak even with a clear prompt.** *Argüir* (10/30) and *blandir* (17/30) at 1.7B vs *tener* (30/30). Rare-tier pool recall was 45% at 1.7B vs 100% on common irregular. Low-frequency lemmas are a **lexical knowledge** problem, not fully resolved by better instructions.

4. **Present tense is anomalously hard at 1.7B.** *Comer* present scored 0/6 while other *comer* tenses scored 6/6. *Argüir* present also 0/6. Suggests sporadic tense-specific or stem-change errors, not uniform paradigm absence.

5. **0.5B is not viable for paradigm generation.** Even with the explicit prompt, recall was 11% with 0% on imperfect and conditional across all verbs. Instruction tuning and capacity both limit this size class.

6. **CTG vs knowledge (directional).** At 1.7B, near-perfect paradigms on *tener* coexist with much lower sentence-level `expected_form_match` on the HF benchmark (~21% on `spanish_basic`). Sentence-generation failure on common verbs is therefore plausibly **CTG / binding**, while rare-verb failure in both isolation and sentences points to **missing lexical knowledge** → knowledge injection is the appropriate intervention for the niche tier.

---

## Limitations

- Only 0.5B and 1.7B re-run with `explicit_v1`; 4B not tested under this prompt
- Form recall is lenient (order-independent substring match); duplicate correct forms can inflate scores where yo/él share the same surface form
- Single greedy sample per call; no pass@k
- Gold paradigms manually curated; no programmatic conjugation library verification
- Peninsular six-form paradigm (includes vosotros); Latin-American omission not tested
- Not stored in the research DB pipeline

---

## Related work

- Single-form isolation spikes: `docs/spike-results/eval_english_rare_verbs_qwen_spike_results.json`, `docs/spike-results/eval_spanish_verbs_qwen_spike_results.json`
- Sentence-level HF baselines: `spanish_basic` Qwen ladder (supervisor meeting #7 plan)
- Minimal-prompt paradigm run (superseded for 0.5B/1.7B): `docs/spike-results/eval_spanish_paradigm_qwen_spike_results.json`
