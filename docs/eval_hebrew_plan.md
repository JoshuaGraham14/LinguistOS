# Hebrew Evaluation — Implementation Plan (Phase E)

> Cross-language generalisation of the research-mode evaluation pipeline.
> Hebrew is morphologically richer than Spanish and breaks several implicit assumptions
> in the current stack (whole-token matching, pro-drop anchoring, spaCy parsing, LT grammar).
>
> Parent plan: [`evaluation_metrics_implementation_plan.md`](evaluation_metrics_implementation_plan.md) (Phase E).
> Companion: [`eval_verb_morphology_plan.md`](eval_verb_morphology_plan.md) (parser architecture).
> Thesis framing: [`eval_thesis_claims.md`](eval_thesis_claims.md).

---

## Goal

Answer four questions for the dissertation:

1. **Framework generalisation:** Does the same evaluator *interface* work for Hebrew without forking the pipeline?
2. **Constraint checking:** Does `expected_form_match` (Hebrew-aware) remain the headline metric when morphology is dense and clitics attach to verbs?
3. **Tool reliability:** How does Stanza Hebrew compare to spaCy Spanish on the same diagnostic role (`verb_morphology`)?
4. **Prompt anchoring:** What kind of explicit-subject / gender anchoring is required for long, challenging Hebrew items?

**Framing (decide now, defend in write-up):**

> Phase E tests whether the *evaluation framework* generalises, not whether GPT generalises
> equally well across languages. Constraint-specific checking should matter *more* in Hebrew,
> where general grammar tools are weakest and morphology is densest.

---

## Why Hebrew is harder than Spanish

| Assumption (works for `es`) | Hebrew failure mode | Mitigation |
| --- | --- | --- |
| Whole-token `expected_form_match` | Proclitics fuse to verbs: `ושאלתי` = `ו+שאלתי` | Clitic-stripping + optional morph fallback matcher |
| Constraints = tense + person + number | Gender marked on 2nd/3rd past, all present, 2nd/3rd future | Add `gender` axis (nullable for Spanish) |
| spaCy is the parser | Weak/experimental Hebrew support | Stanza `he` via `morph_configs/he.yaml` |
| LanguageTool = grammar baseline | Hebrew ruleset is very thin | Drop LT for Hebrew headline; optional GPT-judge later |
| Explicit subject fixes person slips | Present verbs agree with subject gender; pronouns are gendered | Gender-aware prompt anchoring |
| Whitespace tokenization | Ktiv male vs ḥaser; optional niqqud | Normalisation layer; store raw + normalised in `details` |
| Spanish length bands | Hebrew is morpheme-dense | Re-calibrate bands from E0 spike data |

---

## Scope tiers

Pick one tier based on dissertation timeline. **Tier 1 is the minimum viable Phase E.**

| Tier | Phases | Delivers |
| --- | --- | --- |
| **Tier 1 (MVP)** | E0 + E1 + E2 + E5 | Benchmark, clitic-aware matcher, Stanza morph, gendered prompts, mock probe, one live comparison notebook |
| **Tier 2 (full)** | Tier 1 + E3 + E4 | Grammar proxy layer, length grid, diversity grid with Hebrew caveats |
| **Tier 3 (stretch)** | Tier 2 + cross-lang chapter | Spanish vs Hebrew tool-reliability notebook section, human ratings subset |

---

## Branch and merge pattern

Follow the established `research/*` workflow:

```
research/eval-hebrew
  → E0 spike notes committed under docs/
  → E1 benchmark + matcher
  → E2 Stanza morph
  → E5 prompts + live runs
  → --no-ff merge to main: "Merge research/eval-hebrew: Hebrew benchmark and evaluation"
```

Run `reset_db()` after schema changes; method YAML loader is insert-only (see handoff).

---

## Phase E0 — Scoping spike (½ day, throw-away OK)

**Goal:** Validate that GPT Hebrew generation is good enough to evaluate, and measure clitic
attachment frequency before writing matchers.

### Procedure

1. Hand-write 8–10 constraint sets (mix of tenses, persons, genders) — do **not** commit
   to DB yet; use a scratch YAML or notebook cell.
2. Run 3 live sentences per set with the existing `baseline_gpt` prompt (`target_language=he`).
3. Manually score each output:
   - EF strict (whole token)
   - EF clitic-stripped (strip leading `והשכלבמ` proclitics)
   - Gender correct?
   - Clitics attached to target verb?
4. Record mean token counts per length band attempt (rough prompt: short / medium / long).

### Decision gates

| Outcome | Action |
| --- | --- |
| GPT EF (clitic-stripped) ≥ ~70% on basic sets | Proceed to E1 |
| GPT systematically wrong on gender | Narrow benchmark to tenses where gender is unambiguous first; document limitation |
| Clitics attach >50% of the time | Clitic-aware matcher is mandatory (not optional) |
| GPT quality hopeless (<50% manual EF) | Reframe Phase E as "framework stress test with mock + human gold" only |

### Deliverable

`docs/eval_hebrew_e0_spike.md` — table of manual scores, clitic rate, recommended length bands.
No code required; informs E1 benchmark design.

---

## Phase E1 — Benchmark + Hebrew-aware constraint matching

### E1.1 — Schema: `gender` on constraint sets

**Option A (recommended):** store in `extra_constraints` JSON — no migration.

```yaml
# hebrew_basic.yaml example
- keyword: לשאול
  expected_form: שאלתי
  translation: to ask
  tense: qatal          # past / perfective
  person: 1st
  number: singular
  extra_constraints:
    gender: masculine   # or feminine
```

**Option B:** add nullable `gender` column on `ConstraintSet` if you want it in SQL queries.
Only do this if notebook pivots need `gender` as a first-class filter.

Update `ConstraintSet.to_constraints_dict()` to flatten `gender` from `extra_constraints`
into the top-level constraints dict passed to evaluators and prompts:

```python
if self.extra_constraints:
    out["extra_constraints"] = self.extra_constraints
    if "gender" in self.extra_constraints:
        out["gender"] = self.extra_constraints["gender"]
```

### E1.2 — Hebrew tense vocabulary

Use precise Hebrew tense names in benchmark YAML (per
[`eval_verb_morphology_plan.md`](eval_verb_morphology_plan.md) §3). Map to UD features in
`morph_configs/he.yaml`.

| Benchmark `tense` | Linguistic label | UD `Tense` (Stanza) | Notes |
| --- | --- | --- | --- |
| `qatal` | Past / perfective | `Past` | Most common "past" for drills |
| `yiqtol` | Future / imperfective | `Fut` | |
| `present_participle` | Present (Benoni) | `Pres` | Gender always marked |
| `wayyiqtol` | Narrative past | `Past` | Optional; advanced benchmark only |
| `imperative` | Imperative | *(no Tense)* | Use `Mood=Imp` in morph config |

Start `hebrew_basic` with `qatal`, `yiqtol`, `present_participle` only.

### E1.3 — Benchmark YAML: `hebrew_basic`

File: `research/benchmarks/hebrew_basic.yaml`

Design principles:
- 6–8 constraint sets covering 3 tenses × varied person/number/gender
- Gold `expected_form` in **ktiv male**, no niqqud, no clitics on the gold form itself
- Verbs chosen for learner frequency, not maximal irregularity (save irregulars for `hebrew_challenging`)
- `language: he`

**Starter constraint sets (draft — validate in E0):**

| keyword | expected_form | tense | person | number | gender | gloss |
| --- | --- | --- | --- | --- | --- | --- |
| לשאול | שאלתי | qatal | 1st | singular | masc | I asked |
| לשאול | שאלת | qatal | 2nd | singular | masc | you asked |
| לכתוב | כותבת | present_participle | 3rd | singular | fem | she writes |
| לכתוב | נכתוב | yiqtol | 1st | plural | — | we will write |
| לאכול | אכלנו | qatal | 1st | plural | — | we ate |
| ללכת | הלכת | qatal | 2nd | singular | fem | you (f) went |

Use `gender: null` or omit where tense does not mark gender (1st past, 1st future plural).

### E1.4 — Mock probe: `hebrew_morph_probe`

File: `research/benchmarks/hebrew_morph_probe.yaml` (`mock_only: true`)

Mirror `spanish_grammar_probe`: 10–15 hand-curated sentences in
`research/fixtures/mock_outputs.py` covering:
- Correct gold forms (EF pass)
- Clitic-prefixed correct forms (`ושאלתי` — EF strict fail, clitic-aware pass)
- Wrong person/gender (EF fail, morph may pass/fail)
- Ktiv ḥaser variant (optional — tests normalisation)

Enables matcher iteration without OpenAI spend.

### E1.5 — Hebrew text normalisation

New module: `research/evaluation/hebrew/normalize.py`

```python
def strip_niqqud(text: str) -> str: ...
def strip_cantillation(text: str) -> str: ...
def normalize_hebrew(text: str, *, strip_niqqud: bool = True) -> str: ...
```

Apply NFKC; strip Unicode ranges U+0591–U+05C7 (niqqud + cantillation).
**Do not** fold final letters by default (ם→מ changes word identity).

### E1.6 — Clitic-aware `expected_form_match`

**Approach:** extend the existing evaluator with a per-language matching strategy — do **not**
register a second evaluator name (keeps roll-ups comparable across languages).

File: `research/evaluation/sentence/expected_form.py` (extend) or
`research/evaluation/sentence/expected_form_strategies.py` (new, imported by evaluator).

**Matching cascade (first hit wins):**

| Step | Strategy | `details.match_strategy` |
| --- | --- | --- |
| 1 | Strict whole-token match (current behaviour) | `strict` |
| 2 | Strip leading proclitics `והשכלבמ` from each token, then whole-token match | `clitic_stripped` |
| 3 | *(optional, Tier 2)* Stanza: find token whose lemma = keyword and features match | `morph_fallback` |

**Proclitic set (initial):** `ו` (and), `ה` (the), `ב` (in), `ל` (to), `כ` (as/like), `מ` (from), `ש` (that/relative).
Strip recursively (`ובשאלתי` → `שאלתי`). Document that object/possessive **suffixes** are out of scope for Tier 1.

**`details` additions (all strategies):**

```python
{
    "passed": bool,
    "expected_form": str,
    "matched_token": str | None,
    "match_strategy": "strict" | "clitic_stripped" | "morph_fallback" | None,
    "raw_token": str | None,          # before clitic strip
    "normalized_expected": str,
    "normalized_matched": str | None,
}
```

**Diagnostic metric (notebook only, not a new evaluator):** compute
`strict_pass_rate` vs `clitic_aware_pass_rate` from `details.match_strategy` in analysis.
The gap is a dissertation finding about Hebrew surface matching.

### E1.7 — Tokenization for Hebrew

Extend `research/evaluation/distribution/tokens.py`:
- For `language=he`, strip niqqud before edge-punctuation strip
- RTL marks (U+200F, U+200E) stripped
- Do not lowercase (Hebrew has no case; `casefold()` is harmless but document)

---

## Phase E2 — Stanza `verb_morphology` for Hebrew

### E2.1 — Morph config

File: `research/evaluation/morph_configs/he.yaml`

```yaml
parser: stanza
model: he
pos_filter: [VERB, AUX]

tense_map:
  qatal: Past
  yiqtol: Fut
  present_participle: Pres
  wayyiqtol: Past
  imperative: null   # checked via Mood instead

person_map:
  "1st": "1"
  "2nd": "2"
  "3rd": "3"

number_map:
  singular: Sing
  plural: Plur

gender_map:
  masculine: Masc
  feminine: Fem
```

Extend `_REQUIRED_KEYS` in `morph_configs/__init__.py` to include `gender_map` as
**optional** (present only when language needs it).

### E2.2 — Stanza adapter in `verb_morphology.py`

Add `_get_stanza_nlp(lang: str)` with module-level cache (mirror spaCy pattern).

Stanza pipeline setup:
```python
import stanza
stanza.download("he")  # one-time; document in README
nlp = stanza.Pipeline("he", processors="tokenize,mwt,pos,lemma", download_method=None)
```

**Token alignment:** Stanza Hebrew uses MWT (multi-word tokens). Flatten via
`word.id` / `word.words` so candidate selection matches surface tokens.

**Gender check:** when `constraints.get("gender")` is set, compare `Gender` UD feature.
When absent, skip gender check (same as skipping an unspecified feature).

**Observed dict extension:**
```python
"Gender": _first_morph(token, "Gender"),
```

### E2.3 — Expectations (do not relitigate Claim 5)

Pre-commit: Stanza Hebrew `verb_morphology` is **diagnostic only**, same as spaCy Spanish.
Headline column remains `pass_rate::expected_form_match` (clitic-aware).
Report `parser_disagreement` rate in the Hebrew notebook as a tool-reliability finding.

### E2.4 — `clause_count` for Hebrew

`clause_count` currently uses spaCy deps. For Hebrew:

| Option | Effort | Recommendation |
| --- | --- | --- |
| Skip `clause_count` for `he` runs | Low | Tier 1 default — register evaluator but return `parse_ok: false, reason: unsupported_language` |
| Stanza deps if available | Medium | Tier 2 — Stanza Hebrew UD may lack reliable `ccomp`/`advcl` |
| Token-heuristic (count `ש`/`אשר` relativisers) | Low | Acceptable for dissertation appendix with documented limitations |

---

## Phase E3 — Grammar layer (Tier 2)

LanguageTool Hebrew is too weak for Claim 1-style LT vs EF comparison. Pick one:

### Option A — Omit LT for Hebrew (recommended Tier 1–2)

- `grammar_languagetool` returns `reason: unsupported_language` for `target_language=he`
- Write-up: *"Constraint-specific checking is the only reliable automatic signal for Hebrew;
  this strengthens the cross-linguistic argument."*

### Option B — GPT grammaticality judge (Tier 2 stretch)

New evaluator `grammar_llm_judge` (optional, not in `DEFAULT_EVALUATORS` until calibrated):
- Fixed rubric prompt: binary grammaticality + optional error category
- Calibrate on 20-sentence human-rated subset before reporting headline numbers
- Store `details.rationale` for error analysis

### Option C — Hebrew-specific tool

DictaBERT / dicta-checker — heavier dependency; only if Option B is insufficient.

**Recommendation:** ship Tier 1 with Option A; add Option B only if the thesis chapter
needs a "grammar quality" column for Hebrew.

---

## Phase E4 — Length grid + diversity (Tier 2)

### E4.1 — Re-calibrated length bands

File: `research/evaluation/length_bands.py` — add per-language overrides:

```python
LENGTH_BANDS_BY_LANGUAGE = {
    "es": {"short": (2, 5), "medium": (5, 9), "long": (10, 16)},
    "he": {"short": (3, 6), "medium": (6, 10), "long": (10, 14)},  # tune from E0
}
```

Values above are placeholders — **must** come from E0 token-count distribution.

### E4.2 — Method presets

Copy Spanish preset pattern under `methods/baseline/` and `methods/individual/`:
- `baseline_default`, `individual_default` (first live comparison)
- `baseline_long`, `individual_long` (length stress)
- `baseline_long_explicit`, `individual_long_explicit` (gendered anchoring)

Set `target_language: he` in generator config or rely on benchmark language propagation
(verify `pipeline.py` passes `target_language` from constraint set).

### E4.3 — Diversity metric caveats

| Metric | Hebrew caveat | Mitigation |
| --- | --- | --- |
| `template_rate` | Leading `ו`/`ה` inflates shared prefixes | Strip proclitics before prefix extraction, or report with footnote |
| `self_bleu` / `distinct_n` | Generally OK with `sacrebleu tokenize='intl'` | Verify in notebook |
| `uniqueness_ratio` | Works as-is | — |

### E4.4 — Experiment grid (Tier 2)

| Run | Benchmark | Preset | Purpose |
| --- | --- | --- | --- |
| H1 | `hebrew_basic` | `baseline_default` | EF + diversity baseline |
| H2 | `hebrew_basic` | `individual_default` | Method comparison |
| H3–H4 | `hebrew_basic` | `*_long` | Length stress without anchoring |
| H5–H6 | `hebrew_basic` | `*_long_explicit` | Gendered anchoring (extends Claim 4) |

Experiment names: `hebrew_basic__baseline_default__live` (existing naming convention).

---

## Phase E5 — Gender-aware prompt anchoring

### E5.1 — Extend `build_prompt` in `baseline_gpt.py` / `individual_gpt.py`

Add parameters:
- `explicit_subject_required: bool` (already exists — extend for Hebrew)
- `gender_required: bool` (new — read from method YAML)

Hebrew subject hints (`_SUBJECT_EXAMPLES_HE`):

| person | number | gender | hint examples |
| --- | --- | --- | --- |
| 1st | singular | — | `אני` (gender-neutral pronoun; verb still gendered in present) |
| 2nd | singular | masc | `אתה` |
| 2nd | singular | fem | `את` |
| 3rd | singular | masc | `הוא` or named masculine noun |
| 3rd | singular | fem | `היא` or named feminine noun |
| 1st | plural | — | `אנחנו` |
| 3rd | plural | masc | `הם` |
| 3rd | plural | fem | `הן` |

**Present tense special case:** 1st singular still needs gender on the verb
(`אני כותב` vs `אני כותבת`). When `gender` is set and tense is `present_participle`,
prompt must say: *"The subject is masculine/feminine; the verb must agree in gender."*

For 1st singular present without gender in constraints, pick one gender in the benchmark
and enforce via `extra_constraints.gender` — do not leave it ambiguous.

### E5.2 — Method YAML flag

```yaml
# methods/baseline/long_explicit.yaml (Hebrew variant or shared with language-agnostic flag)
explicit_subject_required: true
gender_required: true
```

### E5.3 — Claim 4 extension

Document in [`eval_thesis_claims.md`](eval_thesis_claims.md) as **Claim 4b**:

> Gender-aware prompt anchoring fixes Hebrew present-tense and 2nd/3rd-person failures,
> paralleling explicit-subject anchoring for Spanish challenging morphology.

---

## Analysis notebook

New file: `research/explore_live_hebrew_basic.ipynb`

**Sections:**

1. Experiment inventory (filter `hebrew_basic__*__live`)
2. Headline pivot: method × `pass_rate::expected_form_match`
3. Strict vs clitic-aware EF (from `details.match_strategy`)
4. `pass_rate::verb_morphology` + `parser_disagreement` rate (tool reliability)
5. LT column: absent or N/A with explanation
6. §4 Long / explicit-subject comparison (mirror `explore_live_spanish_challenging.ipynb`)
7. Optional §5 Spanish vs Hebrew tool reliability (if Tier 3)

**RTL display helper** — extract now into `research/analysis/live_experiments.py`:

```python
def display_rtl(text: str) -> str:
    """Wrap Hebrew for correct RTL rendering in Jupyter HTML."""
    return f'<div dir="rtl" style="text-align:right">{text}</div>'
```

This is the right moment to create the deferred shared analysis module; Hebrew is the forcing function.

---

## Implementation order

| Step | Task | Phase | Tier |
| --- | --- | --- | --- |
| 0 | E0 manual spike + `eval_hebrew_e0_spike.md` | E0 | 1 |
| 1 | `hebrew_basic.yaml` + loader smoke test | E1 | 1 |
| 2 | `hebrew_morph_probe.yaml` + mock fixtures | E1 | 1 |
| 3 | `hebrew/normalize.py` + tests | E1 | 1 |
| 4 | Clitic-aware matching in `expected_form.py` | E1 | 1 |
| 5 | Hebrew tokenization in `tokens.py` | E1 | 1 |
| 6 | Flatten `gender` in `to_constraints_dict()` | E1 | 1 |
| 7 | `morph_configs/he.yaml` | E2 | 1 |
| 8 | Stanza adapter in `verb_morphology.py` | E2 | 1 |
| 9 | `gender_map` optional key in morph config loader | E2 | 1 |
| 10 | Gender-aware prompt hints | E5 | 1 |
| 11 | `baseline_default` / `individual_default` Hebrew live runs | E5 | 1 |
| 12 | `explore_live_hebrew_basic.ipynb` | E1–E5 | 1 |
| 13 | `long` / `long_explicit` presets + live runs | E5 | 1 |
| 14 | `length_bands.py` per-language overrides | E4 | 2 |
| 15 | Length grid (6 runs) | E4 | 2 |
| 16 | `grammar_languagetool` Hebrew skip / LLM judge | E3 | 2 |
| 17 | `template_rate` proclitic strip | E4 | 2 |
| 18 | `hebrew_challenging.yaml` (irregular verbs) | E1 | 3 |
| 19 | Cross-language tool reliability notebook section | E2 | 3 |

---

## Tests (minimum)

### Unit tests (`research/tests/`)

| Test file | Cases |
| --- | --- |
| `test_hebrew_normalize.py` | niqqud strip; NFKC; final letters unchanged |
| `test_expected_form_hebrew.py` | strict pass; `ושאלתי` clitic pass; wrong form fail |
| `test_verb_morphology_hebrew.py` | mock Stanza pipeline; gender match; `parser_disagreement` |
| `test_evaluation.py` (extend) | `hebrew_morph_probe` mock run end-to-end |
| `test_tokens.py` (extend) | Hebrew RTL marks stripped; token count stable |

### Integration

```bash
# Mock probe (no API, no Stanza download in CI if mocked)
python3 -m research.run_experiment --benchmark hebrew_morph_probe --method baseline_default

# Live smoke (1 experiment, requires OPENAI_API_KEY + stanza he model)
python3 -m research.run_experiment --benchmark hebrew_basic --method baseline_default --live
```

CI: mock Stanza and LanguageTool (existing pattern); Hebrew normalisation and clitic matcher
must run without network.

---

## Dependencies

Add to `research/requirements.txt` (Tier 1):

```
stanza>=1.8
```

Setup (document in `research/README.md`):

```bash
python3 -m pip install stanza
python3 -c "import stanza; stanza.download('he')"
```

Keep Stanza import lazy inside `verb_morphology.py` (mock-only runs should not require it).

---

## Done when

### Tier 1 (MVP)

1. `hebrew_basic` and `hebrew_morph_probe` benchmarks load; mock probe passes ≥90% clitic-aware EF.
2. Stanza `verb_morphology` runs on Hebrew mock fixtures; registered in roll-ups.
3. At least 2 live experiments complete (`baseline_default`, `individual_default`).
4. `explore_live_hebrew_basic.ipynb` documents:
   - EF pass rate (strict vs clitic-aware)
   - VM pass rate + `parser_disagreement`
   - Explicit-subject/gender anchoring effect (if H5–H6 complete)
5. [`eval_thesis_claims.md`](eval_thesis_claims.md) updated with Hebrew claim(s).
6. All existing Spanish tests still pass (195+); new Hebrew tests added.

### Tier 2 (full)

7. Length grid complete; `pass_rate::length_in_band` reported with Hebrew bands.
8. Grammar layer decision documented (LT skipped or LLM judge calibrated).
9. Diversity metrics reported with proclitic caveat.

### Tier 3 (stretch)

10. Side-by-side Spanish vs Hebrew tool-reliability table in notebook.
11. Human-rated subset (≥30 sentences) for Hebrew acceptability (feeds Phase D).

---

## Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| GPT Hebrew quality too poor for live eval | Medium | High | E0 gate; lean on mock probe + human ratings |
| Stanza mis-tags gender / tense | High | Medium | EF is headline; VM diagnostic only (Claim 5 pattern) |
| Clitic stripping over-matches | Low | Medium | Recursive strip with max depth 3; unit tests per clitic chain |
| Suffix clitics (`שאלתיו`) | Medium | Medium | Out of scope Tier 1; document; add suffix strip in Tier 2 if E0 shows high rate |
| Ktiv ḥaser false negatives | Medium | Medium | Optional morph fallback step; report normalisation misses in `details` |
| RTL breaks notebook tables | Low | Low | `display_rtl()` helper; export CSV with Unicode bidi marks |
| Scope creep (DictaBERT, full MWT) | High | High | Stick to Tier 1 until MVP done; Tier 2 is explicit opt-in |

---

## Open decisions (resolve before E1 coding)

| Decision | Options | Recommendation |
| --- | --- | --- |
| `gender` storage | `extra_constraints` vs DB column | `extra_constraints` for Tier 1 |
| EF matcher scope | Extend existing vs new evaluator name | Extend existing; record `match_strategy` in `details` |
| Suffix clitics | Strip in Tier 1 vs defer | Defer unless E0 shows >30% suffix attachment |
| LT for Hebrew | Skip vs LLM judge | Skip Tier 1; LLM judge Tier 2 if needed |
| Length bands | Reuse Spanish vs Hebrew-specific | Hebrew-specific from E0 data |
| `hebrew_challenging` | Tier 1 vs Tier 3 | Tier 3 — get basic working first |

---

## Dissertation chapter mapping

| Section | Source experiments | Key metrics |
| --- | --- | --- |
| Framework generalises | `hebrew_morph_probe` + `hebrew_basic` mock/live | Same evaluator names, same roll-up columns |
| Constraint checking in morph-rich language | H1–H6 | `pass_rate::expected_form_match`, strict vs clitic-aware |
| Tool reliability cross-lingual | Spanish exps + Hebrew H1–H2 | `parser_disagreement` rate ES vs HE |
| Prompt anchoring cross-lingual | H3–H6 vs Spanish exps 22–24 | EF before/after `long_explicit` |
| Grammar layer limitations | Hebrew LT skip | Narrative + optional LLM judge |

---

## Files to create or modify

| Path | Action |
| --- | --- |
| `docs/eval_hebrew_plan.md` | This plan |
| `docs/eval_hebrew_e0_spike.md` | E0 findings (after spike) |
| `research/benchmarks/hebrew_basic.yaml` | New benchmark |
| `research/benchmarks/hebrew_morph_probe.yaml` | Mock probe |
| `research/fixtures/mock_outputs.py` | Hebrew mock sentences |
| `research/evaluation/hebrew/normalize.py` | Normalisation |
| `research/evaluation/sentence/expected_form.py` | Clitic-aware cascade |
| `research/evaluation/morph_configs/he.yaml` | Stanza config |
| `research/evaluation/sentence/verb_morphology.py` | Stanza adapter + gender |
| `research/evaluation/morph_configs/__init__.py` | Optional `gender_map` |
| `research/evaluation/length_bands.py` | Per-language bands (Tier 2) |
| `research/evaluation/distribution/tokens.py` | Hebrew tokenization |
| `research/generation/baseline_gpt.py` | Hebrew subject/gender hints |
| `research/generation/individual_gpt.py` | Same |
| `research/analysis/live_experiments.py` | Shared helpers + RTL |
| `research/explore_live_hebrew_basic.ipynb` | Analysis |
| `research/tests/test_hebrew_*.py` | Unit tests |
| `research/requirements.txt` | `stanza` |
| `research/README.md` | Setup instructions |
| `docs/eval_thesis_claims.md` | Hebrew claims (after live runs) |
| `docs/eval_session_handoff.md` | Link to this plan |
