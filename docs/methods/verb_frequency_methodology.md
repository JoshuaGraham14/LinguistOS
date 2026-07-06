# Verb Frequency & Rarity — Methodology

**Branch:** `research/verb-frequency-rarity`
**Scope:** Objective, corpus-grounded frequency and irregularity scoring for Spanish and English verbs, used to (a) label existing benchmark verbs with continuous rarity/irregularity metrics and (b) sample new verbs for re-running experiments.

This document describes **what we built**, **why**, and **how to use it** to select verbs for the experiment pipeline. It does **not** commit to a specific verb list — that is a downstream step.

---

## 1. Motivation

The initial diagnostic experiments (Exp 1–10) used LLM-generated rarity labels ("basic", "challenging", "niche"). The supervisor's directive (meeting #7) was to:

1. **Replace LLM rarity labels with external corpus frequency** so tier assignments are objective and reproducible.
2. **Disentangle rarity from irregularity** — a verb can be common but morphologically irregular, or rare but perfectly regular. These should be independent axes.
3. **Support fair cross-lingual comparison** between Spanish and English.
4. **Enable discovery of new verbs** by tier, rather than hand-picking from a small pool.

This module is the infrastructure that lets every downstream experiment answer *"how frequent is this verb, and is the probed form irregular?"* with a single API call.

---

## 2. Design principles

| Principle | Implementation |
|---|---|
| **Continuous first, tiers second** | Report Zipf as the analysis variable; tiers exist only for stratified sampling. |
| **Lemma-summed, not surface** | A verb's frequency is the sum of its inflected forms, not just its lemma frequency. |
| **Language-appropriate morphology** | Spanish forms via `verbecc` (present indicative + infinitive + gerund + participle); English via regular `-s/-ed/-ing` plus a hand-curated irregular table. |
| **Full-dictionary census** | Cutoffs computed over all attested verbs in `wordfreq`, not a top-N slice. Avoids the "top-500 tercile" bug where common verbs were labelled rare. |
| **Frozen cutoffs** | Tier boundaries are computed once and stored as module constants. New verbs are placed against the frozen cutoffs, so labels are stable across runs. |
| **Tense-specific irregularity** | Spanish irregularity is checked per (verb, tense, person, number) by comparing `verbecc` output to the regular paradigm. |
| **Offline-safe** | WordNet lemma list committed as a text file fallback (`wordnet_verb_lemmas.txt`); no live NLTK download required on the cluster. |

---

## 3. Architecture

```
research/
├── requirements.txt                          # wordfreq>=3.1, verbecc>=1.10, nltk>=3.8
├── evaluation/lexicon/
│   ├── frequency.py                          # main API
│   ├── en_irregular.py                       # ~120 English strong/archaic verbs
│   ├── wordnet_verbs.py                      # WordNet lookup + file fallback
│   ├── wordnet_verb_lemmas.txt               # 8,429 committed lemmas
│   └── census/
│       ├── es.csv, es_meta.yaml              # 4,044 Spanish verbs + Zipf
│       └── en.csv, en_meta.yaml              # 7,007 English verbs + Zipf
├── scripts/
│   ├── build_verb_census.py                  # regenerate census from wordfreq
│   ├── compute_tier_cutoffs.py               # 33/67 percentile boundaries
│   └── score_benchmark_verbs.py              # produce verb_frequency_table.{csv,md}
└── tests/test_frequency.py                   # 15 tests
```

### Public API

```python
from research.evaluation.lexicon import (
    verb_zipf,      # (verb, lang) -> float (lemma-summed Zipf per billion)
    tier,           # (verb, lang) -> "high" | "mid" | "low"
    score_verb,     # (verb, lang, tense=?, person=?, number=?) -> dict
    is_irregular,   # (verb, tense, lang, person, number) -> bool  (Spanish only)
    sample_verbs,   # (lang, tier, n, seed) -> list[str]
    verbs_in_tier,  # (lang, tier) -> list[str]
    filter_by_tier, # (verbs, lang, tier) -> list[str]
    in_census,      # (verb, lang) -> bool
    TIER_CUTOFFS,   # frozen constants
)
```

`score_verb` is the single-call entry point for pipeline code:

```python
score_verb("henchir", "es", tense="pres_indicative", person=3, number="s")
# -> {"verb": "henchir", "zipf": 2.94, "tier": "mid",
#     "irregular": True, "in_census": True}
```

---

## 4. How the Zipf score is computed

### Definition

Zipf value \( z = \log_{10}(\text{freq per billion tokens}) \). Values roughly span 1 (rare) to 8 (extremely common).

### Lemma-summed variant

For a lemma \( \ell \) with inflected form set \( F(\ell) \):
\[
z_{\text{lemma}}(\ell) = \log_{10}\!\left(\sum_{f \in F(\ell)} \text{freq}(f) \cdot 10^9 \right)
\]

This corrects for the fact that in Spanish, `hablo`, `hablas`, `habla`, `hablamos`, `habláis`, `hablan`, `hablar`, `hablando`, `hablado` each carry frequency mass. Scoring only `hablar` massively understates the verb.

### Form sets

- **Spanish** (`verbecc`): present indicative (6 persons) + infinitive + gerund + participle. Nine forms per verb. Excludes preterite/imperfect/subjunctive on purpose — those tenses are where irregularity clusters and would double-count.
- **English**: regular `V, Vs, Ved, Ving` **or** the `en_irregular.py` table when the lemma is in it (covers `go/went/gone`, `smite`, `beseech`, `gainsay`, `shrive`, etc.).

---

## 5. Building the census

### Spanish (`census/es.csv` — 4,044 verbs)

1. Iterate every token in `wordfreq`'s Spanish dictionary (~342k entries).
2. Keep tokens ending in `-ar`, `-er`, `-ir` that `verbecc` can conjugate without error.
3. For each survivor, compute lemma-summed Zipf.
4. Sort, write CSV.

### English (`census/en.csv` — 7,007 verbs)

1. Intersect `wordfreq`'s English dictionary with WordNet verb lemmas.
2. Compute lemma-summed Zipf using irregular table where applicable, else regular pattern.
3. Sort, write CSV.

### Tier cutoffs (frozen)

|Language| `low_upper` | `high_lower` | Zipf range | N |
|---|---|---|---|---|
| Spanish | **2.858** | **3.822** | 1.01–6.93 | 4,044 |
| English | **2.995** | **3.911** | 1.01–7.55 | 7,007 |

- `low`: Zipf < 33rd percentile of the language's census.
- `high`: Zipf ≥ 67th percentile.
- `mid`: in between.
- Verbs outside the census (e.g. neologisms, misspellings, cross-lingual test items) are scored with the same live function and placed against the same frozen boundaries.

### Cross-lingual comparison

Cutoffs are **language-specific by design**. A Spanish Zipf of 3.5 and an English Zipf of 3.5 do not imply equal familiarity to a native speaker — corpora, orthographies, and inflectional inventories differ. The **structural tier** ("high" / "mid" / "low") is what transfers across languages, not the raw number.

---

## 6. Irregularity (Spanish, tense-specific)

For a given `(verb, tense, person, number)`:

1. Ask `verbecc` for the actual form.
2. Compute the *regular* form by applying the paradigm mechanically to the stem.
3. Return `True` if they differ.

This lets a verb be labelled irregular in `pres_indicative` 1sg (`tener → tengo`) but regular in `pres_indicative` 1pl (`tener → tenemos`). Downstream experiments should always pass the tense/person/number they are actually probing.

English irregularity is captured implicitly via `en_irregular.py`; a per-tense flag can be added if a future experiment needs it.

---

## 7. Scripts

- **`build_verb_census.py`** — regenerate `census/*.csv` from the current `wordfreq` version. Rerun only if the frequency library is upgraded.
- **`compute_tier_cutoffs.py`** — recomputes 33/67 percentile cutoffs from the census; prints values to paste into `TIER_CUTOFFS` if regenerating.
- **`score_benchmark_verbs.py`** — scans every `benchmarks/*.yaml`, joins with the census, and emits `docs/methods/verb_frequency_table.{csv,md}` (the audit trail for every verb currently used in a benchmark).

---

## 8. Behavioural changes vs. the old LLM-labelled tiers

- Old `spanish_niche` verbs (`henchir`, `argüir`, `gañir`, ...) are mostly **mid tier** on the frequency axis — they are below the "high" cutoff but not in the bottom third of the 4,044 attested verbs.
- The "literary/archaic" flavour previously bundled into "niche" is **not** the same construct as low frequency. For narratives that need genuinely low-Zipf items, use `tier == "low"` **and/or** an absolute cutoff (e.g. `zipf < 3.0`).
- Report **Zipf continuously** in results tables. Tiers are for sampling and headline slicing only.

---

## 9. Approach to selecting verbs for experiments

This module is the *substrate*; the experiment set is chosen on top of it. The recommended approach:

### 9.1 Sampling frame

Use a **2 × 3 grid per language** (frequency tier × irregularity):

|                | Regular | Irregular |
|----------------|---------|-----------|
| **high** Zipf  | cell 1  | cell 2    |
| **mid** Zipf   | cell 3  | cell 4    |
| **low** Zipf   | cell 5  | cell 6    |

Draw roughly equal numbers from each cell using `sample_verbs()` with a fixed seed. This isolates the two axes so downstream regressions can attribute failures to frequency vs. irregularity independently.

### 9.2 Verb roles across experiments

Not every experiment needs its own list. Three roles cover Exp 1–10:

- **Role A — Diagnostic set** (Exp 1, 2, 1B/2B, 3): ~20 verbs per language, drawn from the full 2×3 grid. Cheap isolation probes.
- **Role B — Sentence benchmark YAMLs** (Exp 4–9): three curated YAMLs derived from Role A:
  - `spanish_basic` (+ `spanish_basic_grid`): high-tier, mostly regular. 5–10 verbs.
  - `spanish_challenging`: high-tier + irregular. 5–8 verbs.
  - `spanish_niche`: not-high (mid/low Zipf), optionally with a literary bias (`zipf < 3.0`). 7–10 verbs.
- **Role C — Method demonstrations** (Exp 10, CD spikes): reuse Role B verbs; no new selection.

Where possible, Role B verbs should be **subsets** of Role A so a single manifest drives everything.

### 9.3 Selection procedure

1. **Sample.** For each language, draw the diagnostic set with `sample_verbs(lang, tier=..., n=..., seed=...)` from each of the six cells.
2. **Score.** Run `score_verb` per verb and per probed `(tense, person, number)` needed by downstream experiments.
3. **Manual validate.** Check the sampled Spanish verbs against a reference (RAE / Wiktionary) to catch corpus artefacts (proper nouns, foreign borrowings, typos). Same for English against OED / Wiktionary. This step is not optional.
4. **Commit a manifest.** A single CSV under `research/evaluation/lexicon/experiment_verbs/manifest.csv` with columns: `verb, lang, zipf, tier, irregular_tenses, in_census, role_diagnostic, role_basic, role_challenging, role_niche, role_grid`. Every downstream YAML and spike script reads from this manifest.
5. **Build YAMLs.** Regenerate `benchmarks/spanish_basic.yaml`, `spanish_challenging.yaml`, `spanish_niche.yaml`, `spanish_basic_grid.yaml` from the manifest, preserving Zipf/tier/irregular metadata as YAML fields.
6. **Update spike scripts.** Isolation spikes should load `VERB_ENTRIES` from the manifest instead of hard-coding.
7. **Always report.** In every results table: `verb, zipf, tier, irregular_for_probed_form, in_census`.

### 9.4 Cross-lingual pairing

For Exp 1B/2B (paired EN/ES isolation), pair by **structural cell** (same tier × irregularity), not by matched Zipf value. Cutoffs differ between languages by design.

### 9.5 What re-running experiments requires

| Experiment | New words? | Source |
|---|---|---|
| 1 (EN isolation) | Yes | Role A (English) |
| 2 (ES isolation) | Yes | Role A (Spanish) |
| 1B/2B (paired) | Yes | Role A subset, paired by cell |
| 3 (paradigm) | Partial — 8–10 ES only | Role A subset |
| 3B (paradigm vs sentence) | Yes | Must equal `spanish_basic` verbs |
| 4 (CEFR) | Reuse | `spanish_basic` |
| 5 (prompt ablation) | Yes | All three YAMLs |
| 6 (form inj. basic) | Reuse | `spanish_basic` |
| 7 (form inj. niche) | Yes | `spanish_niche` |
| 8 (GPT niche) | Reuse | `spanish_niche` |
| 9 (basic grid) | Reuse | `spanish_basic_grid` |
| 10 (knowledge vs sentence) | No | Analysis join on Exp 9 |

The minimum viable refresh is: **build the manifest → re-run 1, 2, 1B/2B, 5, 9 → analyse 10**. Everything else can either reuse the new YAMLs (6, 7, 8) or be cited from the original diagnostic runs.

### 9.6 What stays the same across the refresh

- Prompts, generators, evaluators, pipeline scripts, DB schema.
- Research questions.
- Qualitative story (expected: pattern holds; headline percentages may shift).

### 9.7 What changes

- Tier labels move from LLM-assigned to Zipf-derived.
- Some old "niche" verbs reclassify as mid tier; new low-tier verbs enter the pool.
- Numbers are directly comparable to future re-runs because cutoffs are frozen.

---

## 10. Reproducibility checklist

- [ ] `wordfreq` and `verbecc` versions pinned in `research/requirements.txt`.
- [ ] Census CSVs committed.
- [ ] Tier cutoffs frozen as module constants.
- [ ] Selection seed recorded in the manifest header.
- [ ] Manifest CSV committed before any re-runs.
- [ ] Every experiment doc cites the manifest commit hash.

---

## 11. Deliverables produced by this module

- `docs/methods/verb_frequency_table.{csv,md}` — every existing benchmark verb scored.
- `docs/methods/verb_frequency_methodology.md` — this document.
- `research/evaluation/lexicon/` — the module itself.
- (Pending) `research/evaluation/lexicon/experiment_verbs/manifest.csv` — the single source of truth for verbs used in the frequency-validated experiment re-runs.
