# Spanish basic CEFR prompt evaluation

**Date:** June 2026  
**Benchmark:** `spanish_basic` (5 constraint sets, 15 sentences per condition)  
**Status:** Exploratory; C2 condition run outside the pipeline DB

---

## Purpose

Test whether updated generation prompts produce sentences that are:

1. **Morphologically correct** (target verb in the required surface form)
2. **Grammatically acceptable** (rule-based check)
3. **Pedagogically appropriate** for the stated CEFR level (vocabulary and syntactic complexity)

This follows the pedagogical-control axis in the research plan: morphology (`expected_form_match`) is necessary but not sufficient for usable practice items.

---

## Prompt intervention

`research/generation/prompt_builder.py` was extended with:

- **CEFR fluency labels** (A1 → beginner … C2 → mastery) and per-level grammar guidance
- **Explicit inflection instruction** — target lemma must appear inflected to match tense/person/number constraints, not as a bare infinitive
- **`spanish_basic` benchmark tags** — all five constraint sets labelled `cefr_level: A1`

CEFR text is injected only when `cefr_level` is set on the constraint set (or passed to the generator).

---

## Experimental design

### Conditions

| Condition | CEFR in prompt | How run |
|-----------|----------------|---------|
| **A1** | Yes (`A1`, from benchmark YAML) | Pipeline: `run_experiment --live` |
| **C2** | Yes (`C2`, passed at generation time) | Ad-hoc script; benchmark YAML unchanged |

Both conditions used the same five verbs, morphological constraints, and sample count. CEFR was the manipulated variable.

### Fixed parameters

| Parameter | Value |
|-----------|-------|
| Generator | `baseline_gpt` (`baseline_default`) |
| Model | `gpt-5.4-nano` |
| Temperature | 0.7 |
| Sentence length | `short` (2–5 tokens) |
| Samples per constraint set | 3 |
| Total sentences per condition | 15 |

### Constraint sets (`spanish_basic`)

| Keyword | Required form | Tense | Person | Number |
|---------|---------------|-------|--------|--------|
| comer | comimos | preterite | 1st | plural |
| vivir | vivirá | future | 3rd | singular |
| hablar | hablas | present | 2nd | singular |
| escribir | escribieron | preterite | 3rd | plural |
| correr | corro | present | 1st | singular |

### Evaluation metrics

**Automated (pipeline evaluators):**

- `expected_form_match` — gold surface form present as a token
- `grammar_languagetool` — no grammar-category LanguageTool matches
- `length_in_band` — token count within the declared band
- `clause_count` — spaCy clausal complexity (diagnostic)

**Post-hoc pedagogical checks (manual script):**

- Subordination markers (`que`, `porque`, `cuando`, `si`, etc.)
- Passive constructions (heuristic)
- Clause count ≤ 1 (A1 structural simplicity)
- Borderline vocabulary flags (A1 only; heuristic word list)

---

## Results

### Summary

| Metric | A1 (n=15) | C2 (n=15) |
|--------|-----------|-----------|
| Expected form match | 15/15 (100%) | 14/15 (93%) |
| Grammar (LanguageTool) | 15/15 (100%) | 15/15 (100%) |
| Length in band (short) | 15/15 (100%) | 2/15 (13%) |
| Subordination present | 0/15 (0%) | 3/15 (20%) |
| More than one clause | 0/15 (0%) | 3/15 (20%) |
| A1 structure heuristic pass* | 15/15 (100%) | — |

\*A1 only: ≤1 clause, no subordination, no passive, LT pass.

### A1 — representative outputs

| Sentence | Notes |
|----------|-------|
| *Comimos pan y queso.* | Simple SVO; appropriate |
| *Tú hablas español.* | Canonical beginner drill |
| *Las estudiantes escribieron tareas.* | Structurally simple; school vocab borderline for A1 |
| *¿Hablas conmigo?* | Simple question; pronominal *conmigo* acceptable |

### C2 — representative outputs

| Sentence | Notes |
|----------|-------|
| *Hablas de política con una precisión quirúrgica.* | Advanced lexicon; exceeds short band |
| *Vivirá ajeno a cualquier dramatismo innecesario.* | C2 register; exceeds short band |
| *Viviré en la frontera de la evidencia.* | **EF fail** — 1st person `viviré` vs required 3rd `vivirá` |
| *Cuando hablas, sueles argumentar con rigor impecable.* | Subordination + multi-clause |

### A1 pipeline experiment

- **Experiment ID:** `spanish_basic__baseline_default__live` (DB id=12)
- **Commit:** `5038808` (CEFR prompt changes)

---

## Findings

1. **CEFR instructions are followed at the register/structure level.** A1 outputs were uniformly simple (no subordination, single clause). C2 outputs used advanced vocabulary and richer syntax (*quirúrgica*, *dramatismo*, *roza la obsesión*).

2. **Morphology remains strong at A1; C2 introduces binding risk.** EF was perfect at A1. At C2, one person mismatch occurred (`viviré` / `vivirá`) — level complexity did not break grammar but did break a morphological constraint once.

3. **Length and CEFR are partially independent.** With `short` held constant, C2 sentences overwhelmingly violated the length band (87% out of band). The model prioritised “mastery-level” phrasing over the token constraint. A1 complied with both level and length.

4. **Grammar checking does not detect pedagogical level.** LanguageTool passed 100% in both conditions. Level appropriateness requires separate metrics (vocabulary level, clause complexity, construction inventory).

5. **A1 vocabulary is mostly appropriate but not guaranteed.** Three of fifteen A1 sentences flagged borderline lexicon (*estudiantes*, *tareas*, *mensajes*, *temprano*, *conmigo*) despite correct structure and morphology.

---

## Limitations

- Single model (`gpt-5.4-nano`); no small-model or temperature ablation
- C2 condition not stored as a formal pipeline experiment
- Pedagogical checks are heuristic, not CEFR-validated (no word-list or construction inventory evaluator yet)
- `short` length held fixed across levels — confounds level with format; C2 + medium/long not tested here
- n=3 per case — adequate for exploration, underpowered for significance claims

---

## Next steps

- Re-run C2 (and B1/B2) with **level-appropriate default length** (e.g. C2 → medium/long)
- Add automated CEFR appropriateness evaluators (vocabulary coverage, max clause count by level)
- Repeat on small HF models to test whether CEFR instructions survive when morphology is weaker
- Store C2+ conditions as named pipeline experiments for reproducibility
