# Spanish niche form-injection — Qwen 1.7B on `spanish_niche`

**Experiment:** 7 — Sentence-level form-injection ablation on `spanish_niche` (1.7B only)
**Date run:** 2026-06-17
**Date documented:** 2026-06-17
**Track:** Small-model conditioning (supervisor meeting #7); direct follow-up to Exp 6
**Script:** `research/prototyping/spanish_form_injection_qwen_spike.py`
**Raw results:** `docs/spike-results/eval_spanish_niche_form_injection_qwen17b_results.json`
**Status:** Exploratory spike; not run through `run_experiment.py` or the pipeline DB

---

## Purpose

Exp 6 showed that injecting the gold surface form into the prompt closes the **CTG binding gap** on `spanish_basic` at Qwen 1.7B (30% → 98% EF). But the diagnostic story from Exp 2 was that rare Spanish verbs fail for a different reason: **missing lexical knowledge** in the model's weights (4B rare English 100% vs 4B rare Spanish 43%).

If the rare-verb failure is purely a knowledge gap and not a binding gap, then injecting the gold form should fix it almost trivially — the model is told the answer and only has to write a sentence around it. Conversely, if injection on niche fails the way it failed on basic without the explicit overlay (person-default bias), that suggests rare verbs trigger additional CTG pathologies that pure injection cannot resolve.

This experiment runs the same four conditions from Exp 6 on `spanish_niche` with Qwen 1.7B only.

---

## Experimental design

Identical to Exp 6 except for the benchmark and the model scope.

| Parameter | Value |
|-----------|-------|
| Benchmark | `spanish_niche` (7 constraint sets, all C1) |
| Models | `Qwen/Qwen3-1.7B` |
| Conditions | baseline, explicit, form_injected, form_injected_explicit |
| Samples per case | 10 |
| Total scored per condition | 70 |
| Sentence length | `short` (2–5 tokens) |
| Temperature | 0.7 |
| Metrics | EF, grammar (LanguageTool), length-in-band |

### Constraint sets

| Keyword | Expected form | Tense | Person | Number |
|---------|---------------|-------|--------|--------|
| henchir | henchí | preterite | 1st | singular |
| argüir | argüí | preterite | 1st | singular |
| atestiguar | atestigüé | preterite | 1st | singular |
| menguar | menguo | present | 1st | singular |
| empalagar | empalago | present | 1st | singular |
| blandir | blandí | preterite | 1st | singular |
| proferir | profiero | present | 1st | singular |

**Important confound to flag upfront:** all 7 niche constraints are **1st-person singular**. The "yo-default" bias that hurt 1.7B baseline on `spanish_basic` (Exp 6 — *Viviré* instead of *Vivirá*) is neutralised here because the model's first-person default already matches the target. This makes the niche baseline artificially high relative to Exp 6 basic, and means this experiment isolates the **morphology** axis cleanly — the person axis is not under test.

---

## Results

### Headline EF, length, and grammar

Wilson 95% CIs are wide on per-condition cells (n=70).

| Condition | EF | Length-in-band | Grammar (LT) |
|-----------|---:|---:|---:|
| baseline | 50/70 (**71%**) | 38/70 (54%) | 70/70 (100%) |
| explicit | 40/70 (57%) | 64/70 (91%) | 70/70 (100%) |
| **form_injected** | **70/70 (100%)** | 12/70 (17%) | 67/70 (96%) |
| form_injected_explicit | 61/70 (87%) | 41/70 (59%) | 70/70 (100%) |

Two surprising features versus the Exp 6 basic story:

- **Baseline is unusually high (71%).** Niche on 1.7B is *not* the disaster the GPT-on-`spanish_niche` 31% figure suggested. Most of this is the 1st-person-only constraint set hiding the person-default bias (see confound above) and `short` length filtering out the contexts where the model paraphrases.
- **The explicit overlay *hurts* on niche** (71% → 57%). This is the opposite direction to Exp 6 basic, where explicit doubled EF (30% → 60%).

### Per-verb EF

| Verb (gold) | Baseline | Explicit | Form injected | Form injected + explicit |
|---|---:|---:|---:|---:|
| henchir (henchí) | 10/10 | **0/10** | 10/10 | 10/10 |
| argüir (argüí) | 10/10 | 10/10 | 10/10 | **1/10** |
| atestiguar (atestigüé) | **0/10** | **0/10** | 10/10 | 10/10 |
| menguar (menguo) | 10/10 | 10/10 | 10/10 | 10/10 |
| empalagar (empalago) | 10/10 | 10/10 | 10/10 | 10/10 |
| blandir (blandí) | 10/10 | 10/10 | 10/10 | 10/10 |
| proferir (profiero) | **0/10** | **0/10** | 10/10 | 10/10 |

The model has a binary profile across conditions: it either gets a verb's morphology fully or fails it entirely. The two verbs the model could not handle without injection — **atestiguar** (gold *atestigüé*) and **proferir** (gold *profiero*) — were rescued to 10/10 by form injection alone. This confirms the Exp 2 prediction: those verbs were missing-knowledge failures, and supplying the form turns them on.

### Two notable regressions

**1. The explicit overlay regresses *henchir* from 10/10 to 0/10.** This is the same kind of cross-condition flip seen in Exp 5 for *comer* on basic. Looking at the outputs, the explicit overlay's verbose constraint repetition appears to push the model toward higher-register paraphrases that drop *henchí* in favour of *llené* or skip the verb entirely. This is consistent with Exp 5's finding that the explicit overlay is not uniformly helpful — it interacts with specific lemmas.

**2. The combined condition (form_injected + explicit) crashes *argüir* from 10/10 to 1/10.** Sampling the 10 outputs shows a systematic orthographic regression:

```text
NO: "Yo arguí que el proyecto era inadecuado."
NO: "Yo arguí con firmeza en el debate."
NO: "Yo arguí que debíamos cambiar el plan."
NO: "Yo arguí que el gobierno no debía tomar decisiones rápidas."
NO: "Yo arguí que era necesario actuar inmediatamente."
...
OK: "Yo argüí que el partido era injusto."     (1/10)
```

The model is writing *arguí* (no diaeresis) instead of the gold *argüí*. EF is accent-sensitive (see `expected_form.py`), so these fail. The same model produced *argüí* correctly in `form_injected` alone (10/10). Hypothesis: the explicit overlay's `tense: pretérito indefinido` cue activates a more "standard-orthography" generation pathway that drops the dialectal/orthographic diaeresis, even when the gold line in the prompt spells it with ü. This is the same family of failure Exp 2 saw at 4B (4B Spanish wrote *atestigué* instead of *atestigüé*).

### Length collapse under form_injected alone

Form_injected alone is 100% on EF but only 17% on length-in-band. Looking at the outputs:

```text
henchir (gold=henchí, target band 2–5):
  OK [6t] "El henchí el vaso con leche."
  OK [6t] "El henchí la caja con dinero."
argüir  (gold=argüí, target band 2–5):
  OK [8t] "argüí que el presidente no debía ser elegido"
  OK [6t] "argüí que la decisión era incorrecta"
```

The sentences are good Spanish with the correct rare form — they're just longer than the short band allows because rare verbs invoke richer constructions (*argüí que…*, *henchí … con…*). This is a **length-band/genre mismatch**, not a binding failure. Under the explicit overlay, length compliance climbs back to 59% because the overlay's own length restatement pushes the model toward shorter outputs.

The combined condition (`form_injected_explicit`) trades some length compliance and some EF (the argüir crash) for grammar safety; it is the most conservative configuration but not the strictly best by either metric.

---

## Findings

1. **Form injection closes the rare-verb knowledge gap.** The two verbs 1.7B could not handle at all (*atestiguar*, *proferir*: 0/10 under both baseline and explicit) reach **10/10** under `form_injected`. The CTG-binding diagnosis from Exp 6 generalises in form, but the *cause* it cures is different: on basic it cured binding failures around verbs the model knew; on niche it cured knowledge failures around verbs the model didn't.

2. **The Exp 2 prediction is confirmed empirically.** Exp 2's paired isolation argued the niche failure was lexical, not capacity. If that were wrong, supplying the form would still leave residual binding errors. Instead, form injection alone hits **100% EF on niche** — there is essentially no residual generation-time error once the model is given the surface form, at the cost of length compliance.

3. **The explicit overlay is *harmful* on niche by itself.** Niche EF goes from 71% baseline to 57% with the explicit overlay. The overlay was designed for the person/tense binding failures observed on basic; on niche, where the 1st-person-only constraint set neutralises those failures, the overlay's extra verbosity pushes the model toward paraphrase and standard-form orthography (the *arguí* / *argüí* regression). **The right intervention depends on the failure mode.** A single combined prompt is not universally optimal.

4. **Length compliance is a genuine secondary concern.** With rare verbs the model produces longer, naturally-constructed sentences (*"argüí que el presidente no debía ser elegido"*) that bust the short band. EF can hit 100% while length compliance drops to 17%. For a learner app, length matters as much as EF. The short band is probably wrong for C1-tagged rare verbs; this is a benchmark issue more than a model issue.

5. **Accent / diaeresis is a real model failure mode that is not fixed by injection alone.** *argüí* → *arguí* persists under `form_injected_explicit` even though the gold form is printed verbatim in the prompt. Likely fix: constrained decoding at the verb position, where the diaeresis is enforced at the token level.

6. **The combined ("best of both") condition is not strictly best on niche.** On basic, `form_injected_explicit` saturated everything (98% EF, 96% length, 100% grammar). On niche, it trades EF (87%) and re-introduces orthographic regressions while improving length compliance. **There is no single dominant intervention across both benchmarks.** A practical system would route by failure-mode (or by benchmark tier).

7. **The "yo-default" bias is real and the niche set hides it.** Because all 7 niche constraints are 1st singular, the model's egocentric default lines up with the gold. A useful counterpart experiment would extend `spanish_niche` to include 2nd/3rd person rare verbs — that should drop the baseline back into the 30–40% range, matching the GPT-on-niche figure from the supervisor meeting plan.

---

## Limitations

- **All constraints are 1st-person singular.** The niche benchmark is morphologically narrow on the person axis. Generalising to 2nd/3rd-person rare verbs is needed before claiming form injection always rescues niche.
- **n=10 per verb, 7 verbs.** Wilson CIs are wide on per-verb cells; per-condition CIs (n=70) are usable but not tight.
- **`short` length is unrealistic for rare verbs.** The 17% length compliance under `form_injected` is partly the model behaving sensibly and partly the band being wrong. A `medium` or `random` length re-run is the obvious follow-up.
- **One temperature, single seed.** Same as Exp 6.
- **No 0.5B, no 4B.** 0.5B is at floor (Exp 6 showed this). 4B is the most thesis-relevant transfer target — extending this experiment to 4B should be the next step; if 4B baseline on niche is ~43% (matching the Exp 2 isolation figure) and `form_injected` lifts it to 90%+, that is the headline thesis result.
- **Accent-sensitive EF.** *arguí* is "wrong" by EF but is a recognisable alternate spelling. A relaxed EF variant (NFKD-normalised) would mitigate the *argüí* failure but would also weaken the diagnostic value of EF on Spanish.
- **No diversity scoring.** Template collapse is even more likely on niche than basic because rare-verb sentence frames are more constrained (*argüí que…* dominated all argüir outputs in this run).

---

## Relation to other experiments

- **Exp 2 (paired isolation):** predicted that rare Spanish verb failure was lexical, not capacity. This experiment empirically confirms: supplying the form turns formerly-failing verbs (*atestiguar*, *proferir*) from 0% to 100%.
- **Exp 5 (prompt ablation):** showed the explicit overlay was helpful but verb-dependent; this experiment shows it can be actively harmful on niche, sharpening the "intervention should match failure mode" conclusion.
- **Exp 6 (form injection on basic):** showed form injection + explicit overlay saturates at 98% EF on basic. On niche the picture is reversed — explicit overlay drags EF down, and form injection alone is the best by EF (at a length cost).

---

## Next steps

1. **Run the same four conditions on Qwen 4B (and ideally GPT) on `spanish_niche`** — Q3 (small → large transfer). If 4B baseline matches the 43% Exp 2 isolation figure and form injection lifts it to 90%+, this is the headline result.
2. **Re-run niche with `medium` or `random` length.** Rare verbs are not natural in 2–5 tokens; the 17% length compliance under `form_injected` is partly a benchmark artefact.
3. **Extend `spanish_niche` to include 2nd/3rd-person rare verbs.** This would unmask the yo-default bias on niche and let us measure whether form injection still saturates when both binding axes (form + person) are simultaneously challenged.
4. **Add diversity scoring.** `argüí que…` was the dominant template; quantify Self-BLEU and distinct-n.
5. **Constrained decoding** (Exp 8) — the *argüí* / *arguí* orthographic failure is exactly the case where logit-level constraints would dominate prompt-level ones.
