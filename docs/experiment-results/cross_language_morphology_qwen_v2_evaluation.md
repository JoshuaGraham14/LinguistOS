# Cross-language morphology spike — Qwen ladder, matched design (Exp 1B + 2B)

**Experiments:** 1B + 2B — re-run of the original English-vs-Spanish isolation probes (Exp 1 and Exp 2) with the design asymmetries fixed
**Date run:** 2026-06-17
**Date documented:** 2026-06-17
**Track:** Small-model conditioning, methodology consolidation
**Script:** `research/prototyping/cross_language_morphology_qwen_spike.py`
**Raw results:** `docs/spike-results/eval_cross_language_morphology_qwen_v2_results.json`
**Status:** Diagnostic spike. Not run through `run_experiment.py` or the DB pipeline — isolation probes sit outside the sentence-evaluator stack by design (see reproducibility header in the script).

---

## Purpose

Exp 1 (English rare verbs) and Exp 2 (Spanish verb isolation) made the headline claim that *"at 4B, rare English is at 100% but rare Spanish is at 43%"* — a 57-point gap interpreted as evidence that the small-model Spanish gap is a multilingual training-data problem rather than a capacity problem.

While analysing those experiments for fairness we identified three design asymmetries:

1. **English got 2 probes per verb (past tense + past participle); Spanish got 1.** Doubling probe count favours the language with more shots.
2. **The Spanish prompt was more morphologically loaded.** "First person singular preterite" vs English "past tense" — different task complexity per probe.
3. **Tier sizes differed** (English 6+10, Spanish 5+8+7).

This experiment replaces those scripts with a single matched-design isolation probe so the cross-language claim rests on the language axis alone.

---

## Design changes vs Exp 1 / Exp 2

| Axis | Original Exp 1 / Exp 2 | Matched design (this run) |
|---|---|---|
| Probes per verb | English 2, Spanish 1 | **2 in both** — past tense 1st singular, past participle |
| Prompt template | Different wording per language | **One template**, parametrised by language + form label |
| Person/number load | Spanish prompt loaded with tense + person + number | Matched: both probes specify "first person singular" past; past participle is non-finite in both |
| Tier sizes | English 6+10, Spanish 5+8+7 | **7 common + 7 rare per language** |
| Total probes | English 32 conj. + 16 recog.; Spanish 20 + 20 | **28 per language**, 56 per model |
| Gold curation | Hand-curated, hetero source | Hand-curated, single sweep cross-checked against OED / RAE; alternates listed (`besought`/`beseeched`, `clad`/`clothed`, `shrove`/`shrived`); `henchir` 1sg preterite is `henchí` (not the `hencho` bug from the niche benchmark) |
| Decoding | Greedy (T=0) | **Greedy (T=0)** — deterministic, no seed required |
| Scoring | NFC + casefold exact match | **NFC + casefold exact match**, accent-sensitive |

Recognition (gloss → lemma) is dropped entirely. Exp 1 / 2 already showed it confounds morphology with synonym substitution; it adds no information at the cross-language level.

---

## Results — Qwen ladder, matched design

| Model | Language | Common (n=14) | Rare (n=14) | Overall (n=28) |
|---|---|---:|---:|---:|
| **0.5B** | English | 10/14 (71%) | 1/14 (7%) | 11/28 (39%) |
| **0.5B** | Spanish | 4/14 (29%) | 1/14 (7%) | 5/28 (18%) |
| **1.7B** | English | 14/14 (100%) | 9/14 (64%) | 23/28 (82%) |
| **1.7B** | Spanish | 10/14 (71%) | 9/14 (64%) | 19/28 (68%) |
| **4B** | English | 13/14 (93%) | 12/14 (86%) | 25/28 (89%) |
| **4B** | Spanish | 14/14 (100%) | 9/14 (64%) | 23/28 (82%) |

### 4B by probe type

| Language | Tier | Past tense (1sg) | Past participle |
|---|---|---:|---:|
| English | common | 6/7 (86%) | 7/7 (100%) |
| English | rare | 5/7 (71%) | 7/7 (100%) |
| Spanish | common | **7/7 (100%)** | 7/7 (100%) |
| Spanish | rare | **3/7 (43%)** | 6/7 (86%) |

The cross-language gap survives but **only on the rare past-tense cell**: 71% English vs 43% Spanish. Past participles are at ceiling on both languages.

---

## Comparison to the original Exp 1 / Exp 2 claim

The original headline:

> *"At 4B, rare English is at 100%, rare Spanish at 43%. A 57-point gap, same model, same task, different language."*

The matched-design version of the same comparison:

> At 4B, rare English is at **86%**, rare Spanish at **64%**. A **22-point** gap.

The directional claim — small models handle rare English better than rare Spanish — survives. The **magnitude is a third of what was originally reported.** Most of the original 57-point gap was probe asymmetry, not language asymmetry.

Where the gap concentrates is also clearer now: rare past participle is **86% Spanish vs 100% English** (a 14-pp gap), while rare past tense 1sg is **43% Spanish vs 71% English** (a 28-pp gap). Past tense morphology — which requires both person/number agreement and Spanish-specific stem changes — is the actual hard cell. Past participle is essentially solved.

---

## What the failures look like at 4B

Eight 4B failures total (3 English, 5 Spanish):

```
English failures:
  come   / past_tense_1sg     expected=came             got='I'        ← instruction-following
  shrive / past_tense_1sg     expected=shrove|shrived   got="shrive'd" ← tokenisation
  clothe / past_tense_1sg     expected=clad|clothed     got='I'        ← instruction-following

Spanish failures:
  henchir   / past_tense_1sg  expected=henchí           got='enchufé'   ← lemma substitution
  atestiguar/ past_tense_1sg  expected=atestigüé        got='testigué'  ← prefix dropped
  menguar   / past_tense_1sg  expected=mengüé           got='mengué'    ← accent only
  menguar   / past_participle expected=menguado         got='menor'     ← lemma substitution
  blandir   / past_tense_1sg  expected=blandí           got='blanqué'   ← lemma substitution
```

The **failure modes differ by language**:

- **English failures are mostly instruction-following:** "I" instead of "I came" → the model started writing a sentence and the "one word only" cut it off. Not a knowledge problem.
- **Spanish failures are mostly genuine morphological/lexical errors:** lemma substitutions (`enchufé` for `henchí`, `blanqué` for `blandí`), missing diacritics (`mengué` for `mengüé`), prefix drops (`testigué` for `atestigüé`).

This is finer-grained than what Exp 1 / 2 could see, and it's only visible because both languages get the same prompt now.

### Accent-only failures

Several smaller-model "failures" are missing diacritics, not wrong morphology: `corri`/`corrí`, `arguido`/`argüido`, `atestigue`/`atestigüé`, `mengué`/`mengüé`, `empalagé`/`empalagué`. The accent-sensitive scoring (consistent with the pipeline's `expected_form_match`) treats these as failures, but a relaxed NFKD-normalised scorer would push Spanish numbers up several points. This is a known thesis-limitation of EF on Spanish and is the same family of issue we saw in Exp 7 (`arguí` for `argüí` under explicit overlay).

---

## Findings

1. **The original 57-point gap was inflated by design asymmetry.** The matched-design 4B gap is **22 points overall**, **28 points on rare past tense 1sg**, and **14 points on past participle**. The cross-language claim is qualitatively correct but the magnitudes from Exp 1 / 2 should not be cited unchanged.

2. **The directional claim — rare Spanish < rare English at the same model size — survives.** The 4B "ceiling-on-rare-English" pattern still holds at 86%, while rare Spanish stays at 64%. This still supports a multilingual-data interpretation of the small-model Spanish gap; it just doesn't support the *strength* of that interpretation that Exp 2 originally claimed.

3. **The gap concentrates where the morphology is densest.** Past participle is at ceiling everywhere; the action is in 1st-singular preterite. That makes intuitive sense — participles are more regular and non-finite, preterites carry person, number, and language-specific stem changes.

4. **Failure-mode dissociation:** English failures at 4B are dominated by prompt compliance (the "I" failures); Spanish failures are dominated by genuine morphological errors (`enchufé` for `henchí`). The asymmetry was hidden in the original because the prompts were not matched.

5. **0.5B is at floor on Spanish past tense.** 4/14 common (mostly accent failures) and 1/14 rare — confirming Exp 5's "0.5B is a floor, not a target" conclusion via an independent probe.

6. **Common Spanish 1.7B is not as solid as Exp 3 implied.** 10/14 (71%) common Spanish at 1.7B in this matched design vs ~87–93% in Exp 3's full-paradigm probe. The two probes (past tense + past participle) and accent-sensitive scoring expose problems that paradigm-table averaging hides (e.g. `escribido` for `escrito`, `tengo` for `tuve`, `hacido` for `hecho`).

---

## What the thesis should now say

When citing the cross-language gap:

- **Use the matched numbers** (4B: rare English 86%, rare Spanish 64%; 4B rare 1st-singular preterite 71% vs 43%) — not the 100% / 43% from Exp 2.
- Cite Exp 1 / Exp 2 as the **initial diagnostic** that motivated the matched-design follow-up, not as the final evidence.
- Use **failure-mode dissociation** (instruction-following on English, morphology on Spanish) as supporting evidence — it's a richer finding than the headline percentages and was not available in the original.

---

## Limitations

- n=7 per tier per language. Wilson 95% CIs are wide; this is still a diagnostic spike, not a confirmatory experiment.
- Greedy single-sample. No pass@k. A multi-sample run at T=0.7 would tighten the picture and reveal whether the 4B Spanish rare failures are stable across samples.
- Hand-curated gold. The original henchir bug shows the cost of this; we cross-checked sources before this run, but a programmatic verifier (`mlconjug3` for Spanish, NLTK or `inflect` for English) is the right long-term fix.
- Accent-sensitive scoring penalises Spanish in particular. A relaxed-NFKD second pass should be reported alongside the strict numbers.
- Past participle ceiling is itself a limitation: it means our matched probe set only really discriminates on past tense, so future iterations should add a finite, person-loaded form for English too (e.g. third-person singular present).

---

## Reproducibility

```bash
python3 -m research.prototyping.cross_language_morphology_qwen_spike
```

Greedy decoding, deterministic. Three Qwen sizes, 56 probes each, ~3 minutes total on Apple MPS. Defaults match this writeup; pass `--models qwen17b qwen4b` to skip 0.5B, or `--dry-run` to inspect every probe and prompt without loading any model.

Outputs JSON: `docs/spike-results/eval_cross_language_morphology_qwen_v2_results.json`.

---

## Next steps

1. Add an accent-relaxed scoring variant and report it alongside strict EF.
2. Replace hand-curated gold with `mlconjug3` (Spanish) and a programmatic source (English).
3. Add a second finite probe (e.g. 3rd-singular present) so past participle no longer dominates and English participle ceiling stops compressing the gap.
4. Re-run with temperature > 0, multi-sample, to convert wide Wilson CIs into pass@k.
