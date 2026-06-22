# Spanish niche GPT form-injection — `gpt-5.4-nano` on `spanish_niche`

**Experiment:** 8 — GPT form-injection transfer test on `spanish_niche`
**Date run:** 2026-06-17
**Date documented:** 2026-06-17
**Track:** Small-model conditioning / transfer test (supervisor meeting #7, Avenue A5)
**Method:** `form_injected_random_n50`
**Generator:** `baseline_gpt_form_injected`
**Pipeline experiment:** `spanish_niche__form_injected_random_n50__live` (DB id=14)
**Reference baseline:** `spanish_niche__baseline_random_n50__live` (DB id=7)
**Status:** Full pipeline live run; 350 generated sentences, sentence evaluators, group metrics, and roll-ups.

---

## Purpose

The original GPT baseline on `spanish_niche` showed that the benchmark strongly discriminates morphology: EF collapsed to **30.6%** while LanguageTool stayed at **99.7%**. That was the core evidence that niche verbs expose a constraint-satisfaction problem, not a grammar problem.

Experiments 6 and 7 then showed that injecting the expected surface form strongly improves Qwen models. This experiment asks the transfer question:

> If I add the same form-injection line to the original GPT `spanish_niche` setup, using the same model, temperature, sample count, and random length schedule, does GPT improve from the 30.6% baseline?

The only intended intervention is one extra prompt line:

```text
Required surface form: the verb "{keyword}" must appear in each sentence
exactly as "{expected_form}" — use this conjugated surface form verbatim
(one token, no infinitive, no other conjugation).
```

---

## Experimental design

### Matched setup

| Parameter | Original baseline | Form-injected run |
|-----------|-------------------|-------------------|
| Benchmark | `spanish_niche` | `spanish_niche` |
| Method | `baseline_random_n50` | `form_injected_random_n50` |
| Generator | `baseline_gpt` | `baseline_gpt_form_injected` |
| Model | `gpt-5.4-nano` | `gpt-5.4-nano` |
| Temperature | 0.7 | 0.7 |
| Sentence length | `random` | `random` |
| Samples per case | 50 | 50 |
| Total sentences | 350 | 350 |
| Evaluators | Same full pipeline | Same full pipeline |

The pipeline resolves `random` length per generated sentence, so this matches the original live setup more closely than a batched ad-hoc script would.

---

## Headline comparison

| Metric | Original GPT baseline | Form injected | Change |
|--------|----------------------:|--------------:|-------:|
| **Expected form match** | **30.6%** | **96.0%** | **+65.4 pp** |
| LanguageTool grammar | 99.7% | 98.9% | -0.8 pp |
| Length in band | 42.6% | **1.4%** | **-41.2 pp** |
| Verb morphology (spaCy diagnostic) | 1.7% | 13.4% | +11.7 pp |
| Uniqueness | 88.9% | 99.7% | +10.8 pp |
| Self-BLEU | 0.565 | 0.480 | lower / more diverse |
| Template rate | 64.9% | 67.7% | +2.8 pp |

The headline is extremely strong but not free: **form injection raises EF from 30.6% to 96.0%, while length compliance collapses from 42.6% to 1.4%.**

---

## Per-case EF

| Verb | Original baseline EF | Form-injected EF | Change |
|------|---------------------:|-----------------:|-------:|
| argüir | 94% | 98% | +4 pp |
| atestiguar | 78% | 88% | +10 pp |
| blandir | 36% | 98% | +62 pp |
| proferir | 4% | 100% | +96 pp |
| empalagar | 2% | 100% | +98 pp |
| henchir | 0% | 90% | +90 pp |
| menguar | 0% | 98% | +98 pp |

This is the cleanest result so far for the thesis story: the worst baseline verbs were exactly the ones most rescued by form injection.

---

## Results by length band

| Band | n | EF | Length compliance | Grammar |
|------|--:|---:|------------------:|--------:|
| short | 117 | 91.5% | 4.3% | 97.4% |
| medium | 119 | 100% | 0.0% | 100% |
| long | 114 | 96.5% | 0.0% | 99.1% |

The form-injected GPT run effectively ignores the requested length band. The average output length is **15.2 tokens**, so most generations look like long C1 register examples even when the resolved target band is short.

---

## Remaining EF failures

There were 14 EF failures out of 350. They are mostly not ordinary conjugation failures; they are orthographic/tokenisation glitches around rare forms:

```text
henchir / expected hencho:
  "Hench o la copa..."        (gold split into two tokens)
  "Henchо mi cuaderno..."     (homoglyph / orthographic corruption)
  "Mi memoria se hincho..."   (related form, missing expected token)

atestiguar / expected atestigüé:
  "Ateigüé ante el juez..."   (missing 'st')
  "Ate stigüé..."             (split token)
  "Ate​stigüé..."             (hidden character)

argüir / expected argüí:
  "argüíó"                    (over-inflected / attached suffix)

menguar / expected menguo:
  "menguoar"                  (gold embedded in a non-word)

blandir / expected blandí:
  "blandií"                   (over-accented / duplicated vowel)
```

So the residual 4% EF failure is mostly **surface-form copying instability**, not the old problem of paraphrase, infinitive use, or wrong person/tense.

---

## Findings

1. **Form injection transfers strongly to GPT.** The original GPT niche baseline was 30.6% EF; the matched form-injected run reaches **96.0% EF**. This is the clearest evidence so far that the niche benchmark failure is primarily about missing or unstable access to the exact surface form, not general grammar ability.

2. **The hardest baseline verbs are rescued the most.** `proferir` goes 4% → 100%, `empalagar` 2% → 100%, `henchir` 0% → 90%, and `menguar` 0% → 98%. That lines up exactly with the earlier diagnosis: these verbs exposed lemma substitution and avoidance, and explicit surface-form injection removes that uncertainty.

3. **Grammar remains basically solved.** LanguageTool drops only slightly (99.7% → 98.9%), so the model can usually build grammatical sentences around the injected form.

4. **Length compliance collapses.** This is the big trade-off. The model now obeys the rare form but writes long C1-style explanatory sentences regardless of requested band. EF improved by +65 pp, but length fell by -41 pp. This shows morphology control and pedagogical format control are separate axes.

5. **Diversity did not collapse globally.** Uniqueness rises from 88.9% to 99.7%, Self-BLEU decreases, and template rate only nudges up. That said, manual inspection still shows local framing repetition for certain verbs, especially legal-register forms.

6. **The remaining failures are token-level spelling/copying errors.** Hidden characters, split tokens, homoglyphs, and malformed forms (`Ate stigüé`, `Hench o`, `menguoar`) are exactly the kind of issue that constrained decoding or strict post-generation validation could catch.

---

## Interpretation

This is the result we hoped for from the intervention phase:

> GPT did not fail `spanish_niche` because it could not write Spanish. It failed because it did not reliably select and preserve the exact rare surface form. When the form is supplied, EF rises from 30.6% to 96.0%.

But it also gives a more nuanced engineering conclusion:

> Form injection solves morphology, but not pedagogy. A usable learning-app generator needs a second mechanism for length/complexity control.

The next version of the method should probably be **form injection + stricter length instruction / validation**, not just form injection.

---

## Next steps

1. Run a **generate → validate → retry** loop where EF and length must both pass. The current result proves EF can be solved; now test whether length can be recovered without losing EF.
2. Try form injection with **medium-only** or **C1-appropriate length** to separate benchmark mismatch from prompt failure.
3. Add a strict post-processor that rejects split/homoglyph copies of the expected form.
4. Compare against constrained decoding for the residual copy instability.
