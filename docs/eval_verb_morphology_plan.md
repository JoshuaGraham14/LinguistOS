# `verb_morphology` Evaluator — Implementation Plan

> Headline dissertation metric for constraint satisfaction: does the generated sentence
> contain a token whose lemma is the target verb and whose morphology (tense + person +
> number) matches the requested constraints?
>
> Companion to [`evaluation_metrics_implementation_plan.md`](evaluation_metrics_implementation_plan.md).

---

## 1. Goal

Binary, parser-based check (1.0 / 0.0) that complements the deterministic
`expected_form_match` evaluator. Comparing the two gives us:

- agreement rate (both pass) → strong evidence the model satisfied the constraint
- expected-form passes, parser fails → spaCy mis-tagging (tool-reliability finding)
- expected-form fails, parser passes → expected-form gold label may be incomplete
- both fail → likely generation error

Disagreements are themselves dissertation findings about NLP tool reliability.

---

## 2. Architectural principle

**Code is language-agnostic. Language knowledge lives in data.**

The evaluator never mentions Spanish or Hebrew. It reads a per-language morph config
keyed on `target_language` from the constraint set. Adding a new language is purely
additive: new config file + new parser model. Zero code changes.

This satisfies the supervisor's requirement that the evaluation system generalises
across languages without hard-coding.

---

## 3. Tense vocabulary policy

Each language uses its own precise linguistic tense names in benchmark YAML.

| Language | Tense vocabulary |
| --- | --- |
| Spanish (`es`) | `preterite`, `imperfect`, `present`, `future`, `conditional`, `present_subjunctive`, … |
| Hebrew (`he`) | `qatal`, `yiqtol`, `weqatal`, `present_participle`, … *(future)* |
| French (`fr`) | `passe_compose`, `imparfait`, `passe_simple`, `futur_simple`, … *(future)* |

Generic terms like `past` are rejected because they hide ambiguities (Spanish has
preterite *and* imperfect; both are "past"). Precise terms map cleanly to Universal
Dependencies features.

**Migration:** `spanish_basic.yaml` uses `past` today; rename to `preterite`.

---

## 4. Branch

Branch `research/eval-verb-morphology` from `research/eval-expected-form`.

---

## 5. Data layer

### Benchmark YAML (`research/benchmarks/spanish_basic.yaml`)

Rename `tense: past` → `tense: preterite`. No other changes; mock outputs (`comimos`,
`escribieron`, …) are already preterite forms, so `expected_form` labels stay correct.

### Per-language morph config (`research/evaluation/morph_configs/es.yaml`)

```yaml
parser: spacy
model: es_core_news_sm
pos_filter: [VERB, AUX]

tense_map:
  preterite: Past
  imperfect: Imp
  present: Pres
  future: Fut
  conditional: Cnd

person_map:
  "1st": "1"
  "2nd": "2"
  "3rd": "3"

number_map:
  singular: Sing
  plural: Plur
```

Hebrew/French configs added later as new files; no code changes required.

---

## 6. Code layer (language-agnostic)

### `research/evaluation/morph_configs/__init__.py`

`load_morph_config(language: str) -> dict`

- Reads `<language>.yaml` from this directory
- Validates required keys (`parser`, `model`, `pos_filter`, `tense_map`, `person_map`, `number_map`)
- Caches per process (small files; load-once is enough)
- Raises `ValueError` for unsupported languages or malformed configs

### `research/evaluation/sentence/verb_morphology.py`

`VerbMorphologyEvaluator` — single class, no language conditionals.

**Algorithm:**

1. Read `target_language`, `keyword`, `tense`, `person`, `number` from constraints.
2. Load language config; resolve expected `Tense`/`Person`/`Number` UD values.
3. Lazy-load the parser (spaCy model) keyed on config's `model` name.
4. Parse the sentence.
5. Collect all tokens where:
   - `token.lemma_.casefold() == keyword.casefold()`
   - `token.pos_ in config["pos_filter"]`
6. For each candidate, compare `token.morph.get("Tense")`, `Person`, `Number` to expected
   (strict — first value in each list must equal the expected string).
7. **Pass (1.0)** if any candidate matches all three; else **fail (0.0)**.

**`details` JSON:**

```json
{
  "passed": false,
  "language": "es",
  "keyword": "comer",
  "lemma_present": true,
  "candidates_checked": 1,
  "matched_token": "comemos",
  "expected": {"Tense": "Past", "Person": "1", "Number": "Plur"},
  "observed": {"Tense": "Pres", "Person": "1", "Number": "Plur"},
  "tense_match": false,
  "person_match": true,
  "number_match": true,
  "parse_ok": true,
  "reason": "morph_mismatch"
}
```

`reason ∈ {missing_keyword, unsupported_language, unsupported_tense, parse_failed, lemma_not_found, morph_mismatch}`; omitted on pass.

**Strict matching policy** (documented in module docstring):

- `preterite` strictly means `Tense=Past`; imperfect forms (`comíamos`) do **not** pass
- 3rd person must be tagged `Person=3`; missing values count as failure
- Case-folded lemma comparison both sides

---

## 7. Dependencies

Add to `research/requirements.txt`:

```text
spacy>=3.7
```

Document in `research/README.md`:

```bash
python3 -m spacy download es_core_news_sm
```

Required, not optional. Failing loudly on missing dependencies is preferred over
silent all-zero scores.

---

## 8. (Optional) Benchmark loader validation

Extend `research/benchmarks/loader.py` to validate each constraint set's `tense`,
`person`, and `number` against the declared language's morph config. Catches typos
at load time. Defer if scope creep — but a small safety net.

---

## 9. Tests

### `research/tests/conftest.py`

Session-scoped fixture pre-loading spaCy once:

```python
@pytest.fixture(scope="session")
def es_nlp():
    import spacy
    return spacy.load("es_core_news_sm")
```

### `research/tests/test_morph_configs.py`

- Spanish config loads correctly
- Unknown language raises `ValueError`
- Required keys present in returned dict

### `research/tests/test_evaluation.py` (additions)

| Case | Assertion |
| --- | --- |
| `Comimos pizza ayer.` + (comer, preterite, 1, pl) | `score == 1.0` |
| `Nosotros comemos pizza.` + (comer, preterite, 1, pl) | `score == 0.0`, `tense_match is False` |
| `Nosotros hablamos.` + (comer, preterite, 1, pl) | `score == 0.0`, `lemma_present is False` |
| Substring trap (`recomendar` + keyword `comer`) | `score == 0.0` |
| Unsupported language | `score == 0.0`, `reason: unsupported_language` |
| Empty sentence | `score == 0.0`, `lemma_present is False` |
| Mock outputs vs spaCy | Print results; assert only manually verified cases |

**Important:** do **not** blanket-assert all mock outputs pass. Empirical probing of
`es_core_news_sm` shows:

- lowercase `comimos` is mis-tagged `Tense=Pres` (should be `Past`)
- sentence-initial `Hablas` is mis-tagged `NOUN` (lemma `habla`)
- sentence-initial `Corro` lemmatizes to `corro` with `Person=3`

These spaCy quirks are dissertation findings, not test bugs. Tests should document
the actual behaviour, not paper over it.

---

## 10. File layout

| File | Status |
| --- | --- |
| `research/benchmarks/spanish_basic.yaml` | Modified (`past` → `preterite`) |
| `research/evaluation/morph_configs/__init__.py` | **New** |
| `research/evaluation/morph_configs/es.yaml` | **New** |
| `research/evaluation/sentence/verb_morphology.py` | **New** |
| `research/evaluation/sentence/__init__.py` | Modified (register) |
| `research/evaluation/__init__.py` | Modified (re-export) |
| `research/tests/conftest.py` | Modified (session spaCy fixture; rename `past` → `preterite`) |
| `research/tests/test_morph_configs.py` | **New** |
| `research/tests/test_evaluation.py` | Modified (verb_morphology cases + rename `past` → `preterite`) |
| `research/tests/test_benchmarks.py` | Modified (rename `past` → `preterite`) |
| `research/tests/test_models.py` | Modified (rename `past` → `preterite`) |
| `research/tests/test_run_experiment.py` | Modified (rename `past` → `preterite`) |
| `research/requirements.txt` | Modified (`spacy>=3.7`) |
| `research/README.md` | Modified (model install step) |

---

## 11. Implementation order

1. Save this plan
2. Rename benchmark tense values (`past` → `preterite`) across YAML and tests
3. Add `morph_configs/es.yaml` + `load_morph_config()` + tests
4. Add spaCy to requirements + README install step
5. Implement `VerbMorphologyEvaluator`
6. Register in `DEFAULT_EVALUATORS`
7. Write evaluator tests (strict; document spaCy quirks)
8. Run full test suite
9. Reset `research.db`, run mock experiment, compare `pass_rate::verb_morphology` vs
   `pass_rate::expected_form_match` in `explore.ipynb`
10. Commit on `research/eval-verb-morphology`

---

## 12. Dissertation framing

The evaluation pipeline is language-agnostic by design. Each evaluator reads a
per-language configuration mapping benchmark terminology (e.g. Spanish *preterite*)
to Universal Dependencies morphological features. Adding a new language requires
only a new configuration file and a parser model; the evaluator code itself never
changes. Disagreement between deterministic surface-form matching and parser-based
morphology checking surfaces NLP tool reliability issues directly — a central
research concern of this thesis.

---

## 13. Out of scope (for now)

- Hebrew or French configs
- `extra_constraints` features (mood, voice, …)
- Partial-credit scoring
- Frontend label translation (research mode stays rigorous; UI labels are separate)
- ML/LLM-judge evaluators
