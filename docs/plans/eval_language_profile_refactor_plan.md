# Language-profile prompt refactor — plan (June 2026)

> **Status:** Implemented on branch `research/eval-hebrew-e0-spike` (Phases 1–7, June 2026).
> E0 Round 3: 100% EF short + long without Hebrew patch. Ready to merge to `main`.

> Replace the Hebrew patch in `baseline_gpt.py` with a **single generic prompt** driven
> by per-language schemas. One source of truth for which constraints exist in each
> language, what they're called in the prompt, and (optionally) how they're displayed.
>
> Related: [`eval_hebrew_plan.md`](eval_hebrew_plan.md), [`evaluation_metrics_implementation_plan.md`](evaluation_metrics_implementation_plan.md)

---

## Decisions locked in

| # | Decision | Choice |
|---|----------|--------|
| 1 | Where constraints live | **Flat top-level dict** (Option A) — single `constraints` JSON column; drop `extra_constraints` blob; `reset_db()` after migration |
| 2 | Subject anchoring | **Drop language-specific pronoun examples** — keep `explicit_subject_required` as the only knob, prompt text is generic |
| 3 | Glosses | **Default formatter + override** — titlecase raw value automatically; per-language `glosses:` overrides only when value benefits (e.g. `past → Past (עבר)`) |

Architectural principle (carried from `eval_verb_morphology_plan.md`):
**Code is language-agnostic. Language knowledge lives in data.**

---

## Goals

1. Delete all `if target_language == "he":` branches from `baseline_gpt.py`
2. Make adding a new language a **pure data change** (new YAML file)
3. Validate benchmark YAML against the language schema at load time
4. Keep prompt shape close to the current Spanish prompt (the one that works)
5. No regression on Spanish `pass_rate::expected_form_match`
6. Hebrew E0 short + long pass rates ≥95% without the patch

---

## Non-goals

- Touching evaluators (`expected_form_match`, `verb_morphology`, etc.) — interface stays the same
- Merging `morph_configs/` into language profiles — separate refactor, defer
- New benchmarks (Hebrew basic, Spanish niche) — separate phase
- DB migration tool — accept `reset_db()` for the prototype
- Streamlit / app integration

---

## Target architecture

```
research/
  languages/                   ← NEW directory, source of truth for constraint schema
    es.yaml
    he.yaml
    _schema.md                 ← (or comment in each file) — documents YAML shape
  generation/
    baseline_gpt.py            ← gutted; ~80 lines; no Hebrew block
    prompt_builder.py          ← NEW module: generic build_prompt()
    languages.py               ← NEW module: load + validate language profiles
  benchmarks/
    spanish_basic.yaml         ← flatten extra_constraints → top-level keys
    spanish_challenging.yaml   ← flatten
    spanish_grammar_probe.yaml ← flatten
    (hebrew_basic.yaml later)
  benchmarks/loader.py         ← validate constraint keys against language profile
  db/models.py                 ← single `constraints: JSON` column on ConstraintSet
```

---

## Language profile YAML shape

`research/languages/{code}.yaml`:

```yaml
code: he
name: Hebrew

# Required: which constraint fields this language exposes, and allowed values.
# Order in YAML = order in prompt (after fixed-order core fields).
dimensions:
  tense:    [past, present, future]
  person:   ["1st", "2nd", "3rd"]
  number:   [singular, plural]
  gender:   [masculine, feminine]
  binyan:   [paal, piel, hifil, hitpael, nifal, pual, hufal]

# Optional: prompt label override (defaults to titlecased field name).
labels:
  binyan: "Binyan"

# Optional: per-value display gloss. Only include entries that benefit.
# Missing entries fall back to the value (titlecased for snake_case).
glosses:
  tense:
    past: "Past (עבר)"
    present: "Present (הווה)"
    future: "Future (עתיד)"
  binyan:
    hifil: "Hif'il (causative)"
    piel: "Pi'el"
    hitpael: "Hitpa'el (reflexive)"

# Optional: fields that are always required (defaults to person+number for verbs).
required: [tense, person, number]
```

```yaml
# es.yaml
code: es
name: Spanish
dimensions:
  tense:    [present, preterite, imperfect, future, conditional]
  mood:     [indicative, subjunctive, imperative]
  person:   ["1st", "2nd", "3rd"]
  number:   [singular, plural]
  dialect:  [peninsular, latin_american, voseo]

glosses:
  tense:
    preterite: "Preterite (pretérito indefinido)"
  mood:
    subjunctive: "Subjunctive"
  dialect:
    peninsular: "Peninsular Spanish (vosotros for 2pl)"
    voseo: "Rioplatense voseo (vos for 2sg)"

required: [tense, person, number]
```

**Notes:**
- No prompt prose. Just data.
- No `subject_examples` table — that's the patch we're deleting.
- `morph_configs/{lang}.yaml` stays where it is (evaluator side); a later refactor can merge.

---

## Generic prompt template

`research/generation/prompt_builder.py`:

```
You generate {Language} example sentences for vocabulary practice.
Target word: "{keyword}" (English: "{translation}")
Constraints (all required):
  {Label1}: {gloss or value}
  {Label2}: {gloss or value}
  ...
  length: {band}
[CEFR line if set]
[Explicit subject line if explicit_subject_required]
Produce {N} natural {Language} sentences within the length band, each containing
the target word, with its English translation.
Reply ONLY as JSON in this exact shape:
{"candidates":[{"sentence":"...","translation":"..."}, ...]}
```

**Constraint emission rules:**
1. Iterate `dimensions` order from the language profile
2. Skip fields not set on the constraint set
3. Apply gloss if present, else titlecase the raw value
4. `keyword`, `translation`, `length` are **scaffold** lines, not part of the loop

**Subject anchoring (generic, no examples):**

```
Include an explicit subject (pronoun or noun phrase) that matches person={person},
number={number}[, gender={gender}].
```

Triggered by `explicit_subject_required: true`. **No** auto-trigger for 2nd/3rd in any language.

---

## Data model change

`ConstraintSet` (in `research/db/models.py`):

**Remove:**
- `tense`, `person`, `number`, `gender` (if added), `extra_constraints` columns

**Add:**
- `constraints: Mapped[dict] = mapped_column(JSON, nullable=False)` — full constraint dict
- Keep: `keyword`, `expected_form`, `translation`, `target_language`, `cefr_level`, `benchmark_id`

**Why:** schema is language-defined; SQL doesn't need to know the column names.

**Migration:** drop tables via `reset_db()`, reload all benchmark YAML. No alembic.

**Notebook impact:** queries like `cs.tense` become `cs.constraints["tense"]`. Update notebooks after refactor (small).

---

## Benchmark YAML migration

Before:
```yaml
- keyword: vivir
  expected_form: vivirá
  translation: to live
  tense: future
  person: 3rd
  number: singular
  extra_constraints:
    gender: feminine
```

After:
```yaml
- keyword: vivir
  expected_form: vivirá
  translation: to live
  constraints:
    tense: future
    person: 3rd
    number: singular
    gender: feminine    # only if Spanish profile gains gender; otherwise omit
```

Or flatter (preferred — fewer levels):

```yaml
- keyword: vivir
  expected_form: vivirá
  translation: to live
  tense: future
  person: 3rd
  number: singular
```

**Decision:** **Flat YAML** (no `constraints:` key in YAML). Loader collects every YAML field except reserved scaffold keys (`keyword`, `expected_form`, `translation`, `cefr_level`) into the `constraints` dict.

Hebrew example:
```yaml
- keyword: לדבר
  expected_form: מדברת
  translation: to speak
  tense: present
  person: 1st
  number: singular
  gender: feminine
```

Hebrew with binyan later:
```yaml
- keyword: לכתוב
  expected_form: יכתיב
  translation: to dictate
  tense: future
  person: 3rd
  number: singular
  gender: masculine
  binyan: hifil
```

---

## Loader validation

`research/benchmarks/loader.py`:

```python
def _build_constraints(cs_data: dict, language: str, profile) -> dict:
    """Extract constraint fields from YAML row, validated against language profile."""
    scaffold = {"keyword", "expected_form", "translation", "cefr_level", "target_language"}
    constraints = {k: v for k, v in cs_data.items() if k not in scaffold}
    profile.validate(constraints)   # raises on unknown field or invalid value
    return constraints
```

**Validation rules:**
1. Every field in `constraints` must appear in `profile.dimensions`
2. Every value must be in the allowed list for that field
3. Every field in `profile.required` must be present

Helpful error:
```
Benchmark hebrew_basic.yaml: constraint_sets[3]: invalid value 'qatal' for field 'tense'
in language 'he'. Allowed: past, present, future.
```

---

## Subject anchoring redesign

**Delete:**
- `_SUBJECT_EXAMPLES` (Spanish pronoun table)
- `_HEBREW_SUBJECT_EXAMPLES` (Hebrew pronoun table)
- Auto-anchoring for Hebrew 2nd/3rd

**Keep:**
- `explicit_subject_required: bool` (method preset YAML)
- Generic prompt line emitted when flag is true:
  ```
  Include an explicit subject (pronoun or noun phrase) that matches
  person={person}, number={number}[, gender={gender}].
  ```

**Validation test (Phase F of this refactor):**
Re-run E0 Hebrew short + long **with `explicit_subject_required: false`** (default).
If pass rate ≥ 95%, the examples were unnecessary. If not, document and revisit.

---

## Implementation phases

### Phase 1 — Language profiles (data only)

| File | Action |
|---|---|
| `research/languages/_schema.md` | Document YAML shape |
| `research/languages/es.yaml` | Mirror current Spanish constraint vocabulary |
| `research/languages/he.yaml` | Past/present/future, gender, binyan (optional) |
| `research/generation/languages.py` | Loader + validator + gloss/label resolution |
| `research/tests/test_languages.py` | Schema validation, gloss fallback, dimension iteration |

**Done when:** `LanguageProfile.load("he")` returns valid object; `profile.validate({"tense": "qatal"})` raises.

### Phase 2 — Generic prompt builder

| File | Action |
|---|---|
| `research/generation/prompt_builder.py` | NEW: `build_prompt(constraints, language, sentence_length, …)` |
| `research/generation/baseline_gpt.py` | Delete Hebrew block (lines 44–193); `build_prompt` becomes thin wrapper or removed |
| `research/tests/test_prompt_builder.py` | Both languages; gloss fallback; constraint ordering; missing field omitted |
| `research/tests/test_baseline_gpt.py` | Update Hebrew tense-block tests — replace with "Past (עבר)" gloss appearing once |

**Done when:** Spanish prompt unchanged in spirit; Hebrew prompt shows glossed constraints with no Python-side prose.

### Phase 3 — Data model + loader

| File | Action |
|---|---|
| `research/db/models.py` | `ConstraintSet.constraints: JSON`; remove `tense/person/number/extra_constraints` columns; update `to_constraints_dict()` |
| `research/benchmarks/loader.py` | Flat YAML → constraints dict; validate against language profile |
| `research/tests/test_models.py`, `test_benchmark_loader.py` | Update for new shape; add validation tests |
| `reset_db()` invoked | Wipe + reload |

**Done when:** `cs.constraints["tense"]` is the access path; benchmarks load with validation; tests pass.

### Phase 4 — Migrate benchmark YAML

| File | Action |
|---|---|
| `research/benchmarks/spanish_basic.yaml` | Move `extra_constraints` keys to top level |
| `research/benchmarks/spanish_challenging.yaml` | Same |
| `research/benchmarks/spanish_grammar_probe.yaml` | Same |

**Done when:** All 3 benchmarks load without warnings; experiment IDs may reset (acceptable).

### Phase 5 — Update consumers

| File | Action |
|---|---|
| `research/pipeline.py` | `_generate_live_candidates` passes `cs.constraints` (dict) instead of `keyword/tense/person/number`; `generation_meta` records resolved constraints |
| `research/generation/base.py` | Update `generate(constraints: dict, …)` signature |
| `research/generation/baseline_gpt.py`, `individual_gpt.py` | Match new signature |
| `research/methods/run_config.py` | `explicit_subject_required` flag flows through unchanged |
| Notebooks | `cs.constraints["tense"]` access pattern |

**Done when:** Mock run + one live Spanish run produce identical evaluations to pre-refactor.

### Phase 6 — Hebrew E0 validation (no patch)

| Step | Action |
|---|---|
| 1 | Update `research/prototyping/e0_hebrew_spike.py` to use new generic prompt |
| 2 | Re-run `--length short`; expect ≥95% EF |
| 3 | Re-run `--length long`; expect ≥90% EF |
| 4 | If regression: turn on `explicit_subject_required` and re-test — that's the only fallback knob |

**Done when:** Hebrew works with no Python-side language code; results documented in `eval_hebrew_e0_spike.md` as "Round 3 (refactored)".

### Phase 7 — Cleanup

| File | Action |
|---|---|
| `research/generation/baseline_gpt.py` | Should be ~80 lines, generic |
| `docs/plans/eval_hebrew_plan.md` | Update "E1" steps to reflect schema-based design |
| `docs/plans/eval_session_handoff.md` | Link to this plan |

---

## Tests (minimum)

| Area | Tests |
|---|---|
| Language profile loading | Missing field; unknown dimension; unknown value; gloss fallback; titlecase default |
| Validation | Reject `tense: qatal` for `he`; reject `binyan: piel` for `es`; accept valid |
| Prompt builder (es) | All current Spanish fields appear; CEFR line; explicit subject line generic |
| Prompt builder (he) | `tense: Past (עבר)` from gloss; no Hebrew prose paragraphs; no pronoun examples |
| Loader | Flat YAML parses; existing benchmarks load post-migration |
| Pipeline | Spanish mock run produces identical sentences + evaluations to pre-refactor (recorded fixture) |
| Hebrew E0 | Short + long with new prompt — recorded pass rates in `docs/` |

---

## Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Hebrew EF drops after removing patch | Medium | High | E0 gate before committing; fallback to `explicit_subject_required: true` flag, not Python code |
| Spanish prompt subtly differs and EF moves | Low | Medium | Snapshot one Spanish prompt before/after; diff manually |
| Notebook regressions on `cs.tense` access | High | Low | Mechanical find-replace; do it as part of Phase 5 |
| DB wipe loses historical experiment IDs | Certain | Low | Already accepted via `reset_db()` workflow |
| Gloss titlecase looks ugly (`imperfect_subjunctive` → `Imperfect_Subjunctive`) | Medium | Low | Default formatter replaces `_` with space then titlecases: `Imperfect Subjunctive` |
| Method preset YAML changes needed | Low | Low | `explicit_subject_required` already there; nothing else |

---

## Open questions to confirm before coding

1. **Required scaffold keys** in benchmark YAML: `keyword`, `expected_form`, `translation`, `cefr_level`, `target_language` — anything else? Currently no.
2. **Where to require `target_language`** — benchmark top-level only (current), or also per constraint set? Keep current (top-level).
3. **Hebrew `gender` for 1st singular present** — leave to benchmark author or auto-default? Author. (Schema lists `gender: [masculine, feminine]` as optional.)
4. **`mood` for Spanish** — adopt as part of this refactor or defer to Spanish niche phase? Defer to niche phase; not required to delete Hebrew patch.
5. **Test fixtures** for `verb_morphology` / `morph_configs` — touched? No, `morph_configs/{lang}.yaml` lives in its own world.

---

## Files to create or modify

| Path | Action |
|---|---|
| `docs/plans/eval_language_profile_refactor_plan.md` | This plan |
| `research/languages/_schema.md` | NEW — YAML shape docs |
| `research/languages/es.yaml` | NEW |
| `research/languages/he.yaml` | NEW |
| `research/generation/languages.py` | NEW — load + validate |
| `research/generation/prompt_builder.py` | NEW — generic builder |
| `research/generation/baseline_gpt.py` | Trim to ~80 lines; remove Hebrew block |
| `research/generation/individual_gpt.py` | Adapt signature |
| `research/generation/base.py` | Adapt signature |
| `research/db/models.py` | `constraints: JSON` column |
| `research/benchmarks/loader.py` | Flat YAML + schema validation |
| `research/benchmarks/spanish_basic.yaml` | Flatten |
| `research/benchmarks/spanish_challenging.yaml` | Flatten |
| `research/benchmarks/spanish_grammar_probe.yaml` | Flatten |
| `research/pipeline.py` | Pass constraints dict |
| `research/prototyping/e0_hebrew_spike.py` | Use new prompt builder |
| `research/tests/test_languages.py` | NEW |
| `research/tests/test_prompt_builder.py` | NEW |
| `research/tests/test_baseline_gpt.py` | Update Hebrew tests |
| `research/tests/test_models.py` | Update for new schema |
| `research/tests/test_benchmark_loader.py` | Add validation tests |
| `research/explore_live_spanish_basic.ipynb` | Update `cs.tense` access pattern |
| `research/explore_live_spanish_challenging.ipynb` | Same |
| `docs/plans/eval_hebrew_plan.md` | Note schema-based approach replaces tense block |
| `docs/plans/eval_session_handoff.md` | Link to plan; note `reset_db()` migration |

---

## Done when

1. `baseline_gpt.py` has no `if target_language == "he":` branches
2. Adding a new language = adding `languages/{code}.yaml` only
3. Spanish E0 / existing experiments produce same prompts (snapshot diff)
4. Hebrew E0 short + long ≥ 95% / 90% EF with no Python language code
5. Benchmark loader rejects invalid constraint values with clear error
6. All 199 existing tests pass + new tests for languages and prompt builder
7. `docs/spike-reports/eval_hebrew_e0_spike.md` updated with Round 3 (refactored) results
