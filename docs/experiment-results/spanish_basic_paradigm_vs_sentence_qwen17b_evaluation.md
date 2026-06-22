# Spanish basic — paired paradigm vs. sentence-EF comparison (Qwen 1.7B)

**Experiment:** 3B — paired paradigm-recall vs. sentence-level EF on the full `spanish_basic` verb set, Qwen 1.7B only.
**Date run:** 2026-06-18
**Date documented:** 2026-06-18
**Track:** Small-model conditioning, methodology consolidation
**Script:** `research/prototyping/spanish_paradigm_qwen_spike.py`
**Raw results (this run):** `docs/spike-results/eval_spanish_basic_paradigm_qwen17b_results.json`
**Reference sentence-EF baseline:** DB experiment id=9, `spanish_basic__baseline_hf_qwen3_17b_n20__live`
**Status:** Diagnostic spike (paradigm probe) paired against an existing pipeline experiment. The paradigm probe itself sits outside the sentence-evaluator stack by design.

---

## Purpose

The original Exp 3 paradigm probe ran on `comer, hablar, tener, blandir, argüir`, but the 1.7B sentence-level baseline (21% EF) was on `spanish_basic`, which uses `comer, vivir, hablar, escribir, correr`. Only **2 of the 5 sentence-EF verbs were paradigm-probed** in the original, so the "the model has the knowledge but fails to bind it" claim was supported for 2 of 5 verbs and assumed for the other 3.

This experiment closes that gap: probe **all 5 `spanish_basic` verbs** in paradigm isolation at Qwen 1.7B, then compare verb-by-verb against the existing 21% sentence-EF baseline.

---

## Design

| Parameter | Paradigm probe (this run) | Sentence-EF baseline (DB id=9) |
|---|---|---|
| Model | `Qwen/Qwen3-1.7B` | `Qwen/Qwen3-1.7B` |
| Benchmark verbs | comer, **vivir**, hablar, **escribir**, **correr** | comer, vivir, hablar, escribir, correr |
| Task | List all 6 indicative forms for one verb × one tense | Generate a Spanish sentence using the verb in the specified form |
| Tenses probed | All 5 indicative (present, preterite, imperfect, future, conditional) | One tense per verb (matches `spanish_basic` YAML) |
| Total slots | 5 verbs × 5 tenses × 6 persons = **150 slots** | 5 verbs × 20 samples = **100 sentences** |
| Decoding | Greedy, T=0 | T=0.7 (`baseline_hf`) |
| Scoring | NFC + casefold; gold form matched anywhere in output | `expected_form_match` — exact gold token in sentence |
| Prompt | Explicit paradigm prompt (`explicit_v1`, see script) | Standard `build_prompt` from `baseline_hf` |
| Samples per cell | 1 (greedy, deterministic) | 20 |

The decoding mismatch is a known caveat: paradigm probe is the model's best-effort knowledge recall (greedy); sentence baseline is stochastic at T=0.7. The headline dissociation is too large to be sampling noise, but the magnitudes should be cited with this caveat.

---

## Results — paired by verb

| Verb | Required sentence form | Paradigm total recall | Target cell present in paradigm? | Sentence-level EF |
|---|---|---:|:---:|---:|
| **comer** | comimos (preterite 1pl) | 24/30 (80%) | **YES** | **0/20 (0%)** |
| **vivir** | vivirá (future 3sg) | 30/30 (100%) | **YES** | **0/20 (0%)** |
| **hablar** | hablas (present 2sg) | 28/30 (93%) | **YES** | **1/20 (5%)** |
| **escribir** | escribieron (preterite 3pl) | 28/30 (93%) | **YES** | **0/20 (0%)** |
| **correr** | corro (present 1sg) | 22/30 (73%) | YES | 20/20 (100%) |
| **Overall** | — | 132/150 (88%) | **5/5 (100%)** | 21/100 (21%) |

**The target cell — the exact surface form the sentence-level benchmark requires — was produced correctly in paradigm isolation in every single case.** Yet on 4 of 5 verbs, the same model produced fewer than 2/20 sentences containing the same form.

### Example: vivir future 3sg

When asked for the conditional/future paradigm in isolation, Qwen 1.7B produces the perfect six-form table:

```
yo viviré
tú vivirás
él/ella vivirá   ← the required gold form for spanish_basic
nosotros viviremos
vosotros viviréis
ellos vivirán
```

But in 20 sentence-generation attempts with the constraint *vivir + future + 3rd + singular*, the model produced `vivirá` zero times. The paradigm is in the weights; the binding under generation is not happening.

### Example: comer preterite 1pl

Paradigm output:
```
yo comí
tú comiste
él/ella comió
nosotros comimos   ← the required gold form for spanish_basic
vosotros comisteis
ellos comieron
```

Sentence-level EF: 0/20. Same model, same verb, same form, totally different success rate.

---

## What this shows

1. **The 21% sentence EF on `spanish_basic` is not a knowledge gap.** Every single sentence-EF target cell is produced correctly in paradigm isolation. This is the cleanest possible support for the **CTG binding** interpretation: the surface form exists in the model's parameters, and the model can produce it on demand when not constrained by sentence-generation requirements.

2. **The dissociation is per-verb, not just on average.** Original Exp 3 supported the claim only for `comer` and `hablar`. This paired re-run supports it for **all 5 `spanish_basic` verbs**, including the three that were never paradigm-probed before (`vivir`, `escribir`, `correr`).

3. **The single "easy" case fingerprints the failure mode.** `correr` is the only verb where sentence EF matches paradigm recall (both ~100%). Its required form is `corro` — 1st-person singular present, which is the model's *default* output mode when no subject is specified in the prompt. So when the constraint happens to align with the model's default, sentence EF saturates. When it doesn't (preterite 1pl, future 3sg, present 2sg, preterite 3pl), sentence EF collapses despite the model knowing the form. This matches the "yo-default" bias observed in Exp 6 (form-injection on basic).

4. **Paradigm total recall is not what predicts sentence EF.** `correr` had the *lowest* paradigm total (73%) but the highest sentence EF (100%). `vivir` had a perfect paradigm (100%) and zero sentence EF. So averaging paradigm slots is the wrong predictor — the relevant signal is *whether the specific required cell is in the output*, which it always was here.

---

## Comparison to the original Exp 3 claim

The original Exp 3 writeup said:

> "Sentence-generation failure on common verbs is therefore plausibly CTG / binding, while rare-verb failure in both isolation and sentences points to missing lexical knowledge."

This paired re-run **upgrades the first half of that claim from "plausibly" to "directly demonstrated."** For every `spanish_basic` constraint, the model produced the required form in isolation and failed to bind it in a sentence. There is no longer an unverified gap in the argument.

The second half of the claim (rare-verb knowledge gap) is **not** supported by this experiment — by design, it only covers common verbs. The knowledge-gap argument continues to rest on:

- **Exp 1B/2B (cross-language)** — at 4B, rare English 86% vs rare Spanish 64%; Spanish failures are lemma substitution (*enchufé* for *henchí*).
- **Exp 7 / 8 (form injection on niche)** — verbs like *proferir* and *empalagar* jump from near-zero EF to 100% when the form is supplied. That rescue pattern is the experimental fingerprint of a knowledge gap.

The thesis story is now:

> **Common verbs at 1.7B:** knowledge present (every `spanish_basic` target cell produced in isolation), binding broken (21% sentence EF on the same forms). → CTG/binding intervention is the right fix.
>
> **Rare verbs at 1.7B / 4B / GPT:** knowledge gap (cross-language gap, rare-verb EF rescued by injection). → knowledge-injection / lookup intervention is the right fix.

Two pillars, two distinct interventions, each supported by its own direct evidence.

---

## Limitations

- **n=1 per paradigm cell.** Greedy decoding makes this deterministic, but a single greedy sample doesn't tell us how stable the paradigm output is under stochastic decoding. Multi-sample at T>0 would tighten the picture and might surface flakier cells.
- **Decoding mismatch with the sentence baseline.** Paradigm probe is greedy (T=0); sentence baseline is T=0.7. The dissociation (88% vs 21%) is far too large to be a sampling artefact, but the magnitudes shouldn't be cited to the decimal.
- **Substring scoring (paradigm side).** Inherited from the Exp 3 script — order-independent substring match means surface-form collisions across persons can be credited twice from a single mention (e.g. `comía` is both yo and él/ella imperfect). For *this* writeup the relevant signal is the **target-cell-present** column, which uses positional matching from `per_person` and is not affected by collision inflation.
- **No 0.5B or 4B re-run.** This is targeted at the 1.7B claim; extending the comparison to 0.5B and 4B is the natural follow-up.
- **The 1.7B sentence baseline is from June 2026.** The paradigm probe is from June 2026 with the same model checkpoint, so timing is matched.

---

## Reproducibility

```bash
# 1. Paradigm probe (this run): ~85 seconds on Apple MPS
python3 -m research.prototyping.spanish_paradigm_qwen_spike \
  --models qwen17b \
  --verbs comer vivir hablar escribir correr \
  --output docs/spike-results/eval_spanish_basic_paradigm_qwen17b_results.json

# 2. Sentence baseline (already in DB as experiment id=9; re-run if needed):
python3 -m research.run_experiment \
  --benchmark spanish_basic --method baseline_hf_qwen3_17b_n20 --live
```

`vivir`, `escribir`, `correr` were added to the `PARADIGMS` dict in the spike script in this branch. The script's default verb set (`DEFAULT_VERBS`) is unchanged from the original Exp 3 — the new verbs are opt-in via `--verbs`.

---

## Findings (summary)

1. **All 5 `spanish_basic` target forms are produced correctly in paradigm isolation at Qwen 1.7B** — `comimos`, `vivirá`, `hablas`, `escribieron`, `corro`. The original Exp 3 claim is now directly supported for every verb in the sentence benchmark, not just `comer` and `hablar`.

2. **Sentence-level EF for the same forms is 0/20, 0/20, 1/20, 0/20, 20/20.** The single high-EF case (*correr corro*) is the constraint that happens to align with the model's 1st-singular default, indicating a subject-default bias rather than additional knowledge.

3. **The CTG/binding interpretation no longer rests on inference from 2 verbs.** It rests on direct paired evidence for all 5.

4. **The knowledge-gap claim remains the job of the rare-verb experiments** (Exp 1B/2B cross-language, Exp 7/8 form-injection on niche). This experiment does not bear on it.

---

## Next steps

- Re-run the paired comparison on 4B (single Qwen call set) to lift the claim from "1.7B" to "across the small-model ladder".
- Pair the paradigm probe with the form-injection sentence runs (Exp 6) on the same verbs, to show that the binding-only intervention closes the EF gap without changing paradigm knowledge.
- Re-run paradigm probe with multi-sample T>0 to confirm cell stability — single greedy sample is the main weak spot of this comparison.
