# E0 Hebrew spike — findings (June 2026)

> Live GPT run via `research/generation/baseline_gpt.py` — **same prompt template as Spanish**
> (`gpt-5.4-nano`, temperature 0.7, `sentence_length=short`, 3 candidates per case).
>
> Script: `research/scripts/e0_hebrew_spike.py`
> Raw JSON: [`eval_hebrew_e0_spike_results.json`](eval_hebrew_e0_spike_results.json)

---

## Hebrew tense model (used in prompt)

Modern Hebrew has **exactly three morphological tenses** (not Spanish-style preterite/imperfect/subjunctive):

| Canonical | Hebrew name | English | Benchmark YAML labels |
| --- | --- | --- | --- |
| **Past** | עבר (avar) | completed / perfective | `qatal`, `past`, `preterite` |
| **Present** | הווה (hoveh) | ongoing / Benoni participle | `present_participle`, `present` |
| **Future** | עתיד (atid) | not yet done | `yiqtol`, `future` |

Biblical names (`qatal`, `yiqtol`) are **aliases** mapped to these three in `baseline_gpt.py`.
Imperative and infinitive are **moods/forms**, not a fourth tense — the prompt explicitly forbids
imperative unless requested.

---

## Round 2 (prompt-fixed) — headline results (n=30)

| Metric | Round 1 (opaque labels) | **Round 2 (Hebrew tense block)** |
| --- | --- | --- |
| EF strict | 43% (13/30) | **100% (30/30)** |
| EF clitic-aware | 43% | **100%** |
| Length in band | 97% | **100%** |

**E0 gate:** ≥ ~70% clitic-aware EF → **PASS**. Proceed to E1.

### Prompt changes (Round 2)

1. Explain three tenses (עבר / הווה / עתיד) and map benchmark label → required tense
2. Explicit agreement line (person, number, gender when set)
3. Auto subject anchoring for 2nd/3rd person (+ 1sg when gender specified)
4. Finite-verb instruction (not infinitive-only, not imperative, not wrong tense)

---

## Test cases — what and why

| ID | Target | Expected form | Constraints | Why it's difficult |
| --- | --- | --- | --- | --- |
| 01 | לשאול | שאלתי | qatal, 1sg | Infinitive keyword — may leave `ל+stem` unconjugated (Spanish *dormir* pattern) |
| 02 | לכתוב | כותבת | present, 3sg **fem** | Present marks gender on verb; pro-drop |
| 03 | לשאול | שאלת | qatal, 2sg masc | 2sg past without anchored subject |
| 04 | ללכת | הלכת | qatal, 2sg **fem** | `הלכת` = 1sg or 2sg fem orthographically |
| 05 | לכתוב | נכתוב | yiqtol, 1pl | Future needs `נ-` prefix |
| 06 | לאכול | אכלנו | qatal, 1pl | Past plural suffix `-נו` |
| 07 | לדבר | מדבר | present, 1sg **masc** | `אני` is gender-neutral; verb must be masc |
| 08 | לדבר | מדברת | present, 1sg **fem** | Feminine present 1sg |
| 09 | ללכת | הלך | qatal, 3sg masc | Irregular suppletive past |
| 10 | לתת | נתת | qatal, 2sg masc | Past 2sg; narrative `ו-` clitic risk |

---

## Per-case results (Round 2)

| ID | EF strict | Notes |
| --- | --- | --- |
| 01 | **3/3** | Past 1sg `שאלתי` |
| 02 | **3/3** | `היא כותבת` with explicit feminine subject |
| 03 | **3/3** | `אתה שאלת` — past 2sg masc (was 0/3 in Round 1) |
| 04 | **3/3** | `את הלכת` — past 2sg fem (was 0/3) |
| 05 | **3/3** | `נכתוב` future 1pl (was 0/3) |
| 06 | **3/3** | `אכלנו` |
| 07 | **3/3** | `אני מדבר` |
| 08 | **3/3** | `אני מדברת` feminine (was 0/3) |
| 09 | **3/3** | `הוא הלך` irregular past |
| 10 | **3/3** | `אתה נתת` past 2sg (was 0/3 imperatives) |

---

## Round 1 (baseline — for comparison)

| Metric | Rate |
| --- | --- |
| EF strict | **43%** (13/30) |
| EF clitic-aware | **43%** — 0 clitic fixes |
| Length in band | **97%** |

Round 1 failures were dominated by GPT ignoring opaque tense labels (`qatal`, `yiqtol`) and
missing gender in the prompt — not by model inability to conjugate Hebrew.

### Round 1 per-case (abbreviated)

| ID | EF | Failure mode |
| --- | --- | --- |
| 03–05, 08, 10 | 0/3 | Wrong tense (present/imperative instead of past/future) or wrong gender |
| 02, 09 | 2/3 | Occasional gender/person slip |
| 01, 06, 07 | 3/3 | Already worked |

---

## Round 1 failure taxonomy (fixed in Round 2)

| Mode | Cases affected | Share of failures |
| --- | --- | --- |
| **Opaque tense labels** (`qatal`/`yiqtol`/`present_participle` ignored → present default) | 03, 04, 05 | ~50% of all failures |
| **Gender not in prompt** | 02, 08, 09 | ~25% |
| **Wrong mood** (imperative instead of past 2sg) | 10 | ~10% |
| **Clitic attachment** | — | **0 observed** in this set |
| **Infinitive trap** | 01 | **Not observed** (GPT conjugates; drops infinitive keyword) |

---

## Key findings

### 1. Three-tense prompt block fixes the dominant Round 1 failure

Mapping `qatal` → Past (עבר), `present_participle` → Present (הווה), `yiqtol` → Future (עתיד)
raised EF from **43% → 100%** on the same 10 cases. GPT understands Modern Hebrew tense names;
it did not understand bare biblical labels alone.

### 2. Gender and subject anchoring are required for Hebrew

Cases 02, 08 (gender) and 03, 04, 10 (2nd person past) needed explicit agreement lines and
Hebrew subject hints (`אתה`, `את`, `היא`). These are now built into `baseline_gpt.py` for
`target_language=he` without needing `explicit_subject_required=True` on the method preset.

### 3. Clitic stripping still not observed on short drills

0/30 needed clitic-aware matching in either round. Implement for framework completeness; low
expected impact on short `hebrew_basic` items.

### 4. Proceed to E1

Gate passed. Next: `hebrew_basic.yaml`, wire `gender` from `extra_constraints` through pipeline,
clitic-aware `expected_form_match`, Stanza morph config.

---

## Round 2 — long sentences (10–16 tokens)

Same 10 cases, `sentence_length=long`, Hebrew tense block enabled.
Raw JSON: [`eval_hebrew_e0_spike_long_results.json`](eval_hebrew_e0_spike_long_results.json)

| Metric | Short (Round 2) | **Long** |
| --- | --- | --- |
| EF strict | 100% (30/30) | **97% (29/30)** |
| EF clitic-aware | 100% | **97%** |
| Length in band | 100% | **57% (17/30)** |
| Mean tokens | ~3 | **10.3** |

### Constraint satisfaction at long length

Only **one EF failure** across 30 candidates:

- **Case 06** (past 1pl `אכלנו`, 2/3): one sentence used **3rd-person plural** `הם אכלו` in a subordinate clause instead of 1pl `אכלנו`:
  *"הערב הם אכלו יחד במסעדה חדשה, ואני שמחתי..."*
  — grammatically fine narrative, wrong person for the constraint. Same failure class as Spanish long person slips (Claim 4).

All other cases: **3/3 EF pass**, including 2sg past, future 1pl, and irregular `הלך`.

### Length compliance at long length

GPT produces **longer** sentences (mean 10.3 tokens vs ~3 short) but often **undershoots** the 10–16 band:

| Case | Mean tokens | In-band rate | Notes |
| --- | --- | --- | --- |
| 01, 02, 05, 06, 09 | 11–13 | 67–100% | Reliable long output |
| 03 | 10.0 | 67% | Borderline |
| 04, 07, 08, 10 | 8.7–9.0 | **0%** | Consistently 8–9 tokens — below min 10 |

**Interpretation:** Hebrew long constraint satisfaction is strong; length band compliance is weaker than Spanish (Spanish short grid was 100% in-band). Likely needs Hebrew-specific long bands (e.g. 8–14) or stronger numeric emphasis in the prompt. Clitic attachment still **0/30**.

```bash
python3 research/scripts/e0_hebrew_spike.py --length long
```

---

## Re-run commands

```bash
python3 research/scripts/e0_hebrew_spike.py --length short
python3 research/scripts/e0_hebrew_spike.py --length long
```

Results: `docs/eval_hebrew_e0_spike_{short,long}_results.json`
