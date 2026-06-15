# English vs Spanish verb isolation — Qwen ladder diagnostic

**Experiment:** 2 — Paired English/Spanish verb isolation (synthesis of Exp 1 + Spanish verb spike)  
**Date run:** 2026-06-12 (same session as Exp 1; results committed ~16:43 GMT+1)  
**Date documented:** 2026-06-15  
**Track:** Small-model conditioning (supervisor meeting #7, Avenue A6)  
**Scripts:** `research/prototyping/english_rare_verbs_qwen_spike.py`, `research/prototyping/spanish_verbs_qwen_spike.py`  
**Raw results:**
- `docs/spike-results/eval_english_rare_verbs_qwen_spike_results.json` (English; see also Exp 1)
- `docs/spike-results/eval_spanish_verbs_qwen_spike_results.json` (Spanish)  
**Status:** Exploratory spike; not run through `run_experiment.py` or the evaluation pipeline

---

## Purpose

Determine whether small on-device Qwen models fail morphological tasks because:

1. **Capacity / instruction-following** — the model is too small to store or retrieve inflected forms, or
2. **Multilingual training-data** — the model has morphology for one language (English) but not another (Spanish), especially for low-frequency lemmas.

**Control logic (Tom):** run the same models on equivalent English and Spanish verb probes. If English passes and Spanish fails at the same size → language-specific data problem. If both fail on small models and both recover on larger ones → capacity problem.

This is an **isolation test**: one-word conjugation/recognition prompts only. No sentence generation, no length constraints, no pipeline evaluators.

---

## Experimental design

### Paired language spikes

| Spike | Verbs (n) | Tiers | Probes per model |
|-------|-----------|-------|------------------|
| English | 16 | common irregular (6), rare irregular (10) | 48 (16 recognition + 32 conjugation) |
| Spanish | 20 | common regular (5), common irregular (8), rare (7) | 40 (20 recognition + 20 conjugation) |

Spanish verb lists and gold forms were taken from existing benchmarks (`spanish_basic`, `spanish_challenging`, `spanish_niche`). English gold forms follow standard dictionary paradigms (OED / Merriam-Webster style); accepted alternates where listed (e.g. *besought* / *beseeched*).

### Tasks

| Task | Prompt pattern | Gold |
|------|----------------|------|
| **Recognition** | Given an English/Spanish gloss → return the infinitive (one word) | Lemma |
| **Conjugation** | Given lemma + form description → return one surface form | Dictionary form(s) |

Example (conjugation):

> What is the past tense of the English verb "gainsay" (meaning: to deny or contradict)? Reply with one word only.

Example (Spanish):

> What is the first person singular preterite (yo) of the Spanish verb "blandir" (meaning: to brandish)? Reply with one word only.

### Fixed parameters

| Parameter | Value |
|-----------|-------|
| Models | `Qwen/Qwen2.5-0.5B-Instruct`, `Qwen/Qwen3-1.7B`, `Qwen/Qwen3-4B-Instruct-2507` |
| Decoding | Greedy (`temperature = 0`) |
| Max new tokens | 32 |
| System prompt | Morphology assistant; reply with one word only |
| Qwen3 thinking | Disabled (`enable_thinking = false`) |
| Scoring | Exact token match after Unicode NFC + casefold; first token extracted from response |
| Uncertainty | Wilson 95% CI on pass rates (reported in JSON output) |

### Output artefacts

- `docs/spike-results/eval_english_rare_verbs_qwen_spike_results.json`
- `docs/spike-results/eval_spanish_verbs_qwen_spike_results.json`

---

## Results — conjugation (primary metric)

Wilson 95% CI shown in parentheses after each rate.

### English

| Model | Common irregular (12) | Rare irregular (20) | **All (32)** |
|-------|----------------------:|--------------------:|-------------:|
| 0.5B | 2/12 (17%; CI 5–45%) | 1/20 (5%; CI 1–24%) | **3/32 (9%; CI 3–24%)** |
| 1.7B | 7/12 (58%; CI 32–81%) | 12/20 (60%; CI 39–78%) | **19/32 (59%; CI 42–74%)** |
| 4B | 11/12 (92%; CI 65–99%) | 20/20 (100%; CI 84–100%) | **31/32 (97%; CI 84–99%)** |

### Spanish

| Model | Common regular (5) | Common irregular (8) | Rare (7) | **All (20)** |
|-------|-------------------:|---------------------:|---------:|-------------:|
| 0.5B | 2/5 (40%; CI 12–77%) | 1/8 (12%; CI 2–47%) | 0/7 (0%; CI 0–35%) | **3/20 (15%; CI 5–36%)** |
| 1.7B | 3/5 (60%; CI 23–88%) | 2/8 (25%; CI 7–59%) | 3/7 (43%; CI 16–75%) | **8/20 (40%; CI 22–61%)** |
| 4B | 4/5 (80%; CI 38–96%) | 8/8 (100%; CI 68–100%) | 3/7 (43%; CI 16–75%) | **15/20 (75%; CI 53–89%)** |

### Cross-language at 4B (conjugation)

| Tier | English | Spanish |
|------|--------:|--------:|
| Common (irregular / all common) | 92% (CI 65–99%) | 80–100% |
| Rare | **100%** (CI 84–100%) | **43%** (CI 16–75%) |

### Infinitive fallback (conjugation probes)

Model returned the bare infinitive instead of the requested form.

| Model | English (32) | Spanish (20) |
|-------|-------------:|-------------:|
| 0.5B | 0/32 (0%) | 0/20 (0%) |
| 1.7B | 7/32 (22%) | 5/20 (25%) |
| 4B | 0/32 (0%) | 0/20 (0%) |

---

## Results — recognition (secondary; interpret with caution)

Models often answered with a **synonym** rather than the target lemma (e.g. *deny* for *gainsay*, *llenar* for *henchir*, *testificar* for *atestiguar*).

### Overall

| Model | English (16) | Spanish (20) |
|-------|-------------:|-------------:|
| 0.5B | 0/16 (0%; CI 0–19%) | 0/20 (0%; CI 0–16%) |
| 1.7B | 2/16 (13%; CI 4–36%) | 11/20 (55%; CI 34–74%) |
| 4B | 3/16 (19%; CI 7–43%) | 13/20 (65%; CI 43–82%) |

### By tier

| Model | English common irr. (6) | English rare (10) | Spanish common reg. (5) | Spanish common irr. (8) | Spanish rare (7) |
|-------|--------------------------:|------------------:|------------------------:|------------------------:|-----------------:|
| 0.5B | 0/6 | 0/10 | 0/5 | 0/8 | 0/7 |
| 1.7B | 2/6 | 0/10 | 5/5 | 6/8 | 0/7 |
| 4B | 3/6 | 0/10 | 5/5 | 8/8 | 0/7 |

**Rare-tier recognition was 0/10 (English) and 0/7 (Spanish) on every model** — synonym substitution (*strike* for *smite*, *testificar* for *atestiguar*) dominates. Conjugation with the lemma supplied is the valid morphology probe.

---

## Per-verb detail (conjugation)

### 4B failures only

| Language | Lemma | Expected | Got |
|----------|-------|----------|-----|
| English | forgo | forwent | forgoed |
| Spanish | correr | corro | yo *(replied “yo corro”)* |
| Spanish | henchir | henchí | hinchí |
| Spanish | atestiguar | atestigüé | atestigué |
| Spanish | blandir | blandí | blandeí |
| Spanish | proferir | profiero | profero |

English 4B scored 20/20 on the rare tier; Spanish 4B scored 3/7.

### Spanish rare tier — all models

| Verb | 0.5B | 1.7B | 4B |
|------|:----:|:----:|:--:|
| henchir | ✗ | ✓ | ✗ |
| argüir | ✗ | ✓ | ✓ |
| atestiguar | ✗ | ✗ | ✗ |
| menguar | ✗ | ✗ | ✓ |
| empalagar | ✗ | ✗ | ✓ |
| blandir | ✗ | ✓ | ✗ |
| proferir | ✗ | ✗ | ✗ |

Typical 4B rare errors are orthographic near-misses (missing *ü*, wrong stem vowel) rather than unrelated tokens.

---

## Additional observations

- **Infinitive fallback** peaks at 1.7B on both languages (~22–25%); 0% at 4B.
- **0.5B** on both languages: near-chance conjugation; Spanish recognition often returns English glosses (*eat* for *comer*).
- Full per-probe outputs (expected form, raw response, latency) are in the JSON artefacts above.

---

## Findings

1. **Model size matters on both languages.** Conjugation accuracy increases monotonically from 0.5B → 1.7B → 4B on English and Spanish. This supports a capacity / instruction-following component.

2. **4B is not globally bad at Spanish morphology.** Common irregular Spanish verbs reached **100%** (8/8) at 4B — comparable to high-resource English performance on common forms.

3. **The gap is tier-specific, not language-global.** At 4B, rare English verbs: **100%**; rare Spanish verbs: **43%**. Same model size, same task format, different outcome on low-frequency lemmas. This favours a **multilingual frequency / lexical coverage** explanation for Spanish niche failure rather than pure parameter limitation.

4. **Recognition task confounds gloss→lemma mapping with morphology.** All models scored 0% on rare-verb recognition (synonym substitution). Conclusions about morphology should be drawn from conjugation only.

5. **Aligns with sentence-level benchmark.** Prior HF ladder on `spanish_basic` (sentence generation) showed 6% → 21% → 95% EF; isolation conjugation on Spanish common forms shows a similar ladder, with rare forms lagging at 4B.

---

## Limitations

- Prototyping scripts only — not integrated with `run_experiment.py` or the DB
- One probe per Spanish verb (vs two forms per English verb); Spanish probes include person/tense/mood in one answer — slightly harder than English past / past-participle only
- n is small per tier (5–12 probes); Wilson CIs are wide — exploratory, not confirmatory
- Greedy decoding only; no pass@k sampling
- Gold forms manually curated; no programmatic verification via `mlconjug3`
- Same Qwen family only; instruction-tuning quality differs across sizes (confound)
- Recognition task design over-penalises synonym answers

---

## Next steps

- Run Spanish conjugation isolation on the same verbs used in `spanish_niche` sentence benchmarks for direct paired comparison (isolation vs in-sentence EF)
- Add pass@k (n=20) at temperature > 0 to separate knowledge-in-distribution from greedy binding
- Test intervention candidates on 0.5B–1.7B where the gap is largest: knowledge injection (single gold form in prompt), validate-and-correct loop, constrained decoding
- Deprioritise gloss→lemma recognition; replace with lemma-in-prompt conjugation-only protocol for cross-language comparability
