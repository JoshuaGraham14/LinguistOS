# Spanish prompt ablation — Qwen 0.5B vs 1.7B (baseline / explicit / self-correct)

**Experiment:** 5 — Sentence-level prompt ablation on `spanish_basic`  
**Date run:** 2026-06-15 (local HF runs; exact start time not recorded)  
**Date documented:** 2026-06-15  
**Track:** Small-model conditioning (supervisor meeting #7); builds on Exp 3 explicit overlay  
**Script:** `research/prototyping/spanish_prompt_ablation_qwen_spike.py`  
**Raw results:**
- `docs/spike-results/eval_spanish_prompt_ablation_qwen05b_basic_results.json`
- `docs/spike-results/eval_spanish_prompt_ablation_qwen17b_basic_results.json`  
**Status:** Exploratory spike; not run through `run_experiment.py` or the evaluation pipeline

---

## Purpose

Test whether **prompt design** and a **one-shot self-correction loop** improve sentence-level morphological binding on small on-device Qwen models — without leaking the gold surface form.

This follows the small-model conditioning track (supervisor meeting #7): prior isolation spikes showed Spanish conjugation knowledge in parameters at 1.7B+, while sentence-level `expected_form_match` (EF) on `spanish_basic` remained low (~6% at 0.5B, ~21% at 1.7B under the standard HF baseline prompt). The ablation asks whether stronger instructions or a rewrite pass close that **CTG binding gap**.

**Primary metric:** `expected_form_match` only (gold token present in the Spanish sentence). Grammar, length, and CEFR appropriateness were not evaluated here.

---

## Experimental design

### Conditions

| Condition | Generation prompt | Notes |
|-----------|-------------------|-------|
| **baseline** | `build_prompt()` — same structure as `baseline_hf` | Tense/person/number in constraint block; **no** `expected_form` in prompt text |
| **explicit** | `build_prompt_explicit()` | Baseline + Spanish overlay: subject pronoun hint, tense label, infinitive ban, length restatement; **no** gold form |
| **self_correct** | Baseline pass@1, then one rewrite per EF failure | Fix prompt states lemma, constraint summary (tense/person/number), and infinitive ban only — **no** `expected_form`; gold form used **for scoring only** |

### Manipulated variables

- **Model size:** 0.5B vs 1.7B (two separate runs, identical setup otherwise)
- **Prompt condition:** baseline vs explicit vs self_correct

### Fixed parameters

| Parameter | Value |
|-----------|-------|
| Benchmark | `spanish_basic` only |
| Models | `Qwen/Qwen2.5-0.5B-Instruct`, `Qwen/Qwen3-1.7B` |
| Device | Apple MPS (local HF inference) |
| Temperature | 0.7 |
| Sentence length | `short` |
| Samples per constraint set | 10 |
| Constraint sets | 5 |
| Total scored sentences per model × condition | 50 (when all parses succeed) |
| Qwen3 thinking mode | Disabled |
| Scoring | `ExpectedFormMatchEvaluator` — exact gold token in sentence |
| Uncertainty | Wilson 95% CI on sentence-level pass rates |

### Constraint sets (`spanish_basic`)

| Keyword | Required form | Tense | Person | Number |
|---------|---------------|-------|--------|--------|
| comer | comimos | preterite | 1st | plural |
| vivir | vivirá | future | 3rd | singular |
| hablar | hablas | present | 2nd | singular |
| escribir | escribieron | preterite | 3rd | plural |
| correr | corro | present | 1st | singular |

All sets tagged `cefr_level: A1` in the benchmark YAML (CEFR text included in prompts via `build_prompt`).

### What **n** denotes

**n** = number of successfully generated, parsed, and scored sentences (not API calls or benchmark cases). Failures still count toward **n**; parse failures reduce **n** below 50.

---

## Results

### Overall EF pass rate

Wilson 95% CI in parentheses.

| Model | baseline | explicit | self_correct (pass@1 / pass@2) | correction yield |
|-------|----------|----------|--------------------------------|------------------|
| **0.5B** | 0/50 (0%; CI 0–7%) | 2/41 (4.9%; CI 1–16%) | 2/50 / 2/50 (4%; CI 1–13%) | 0/48 (0%) |
| **1.7B** | 15/50 (30%; CI 19–44%) | 29/50 (58%; CI 44–71%) | 17/50 / 17/50 (34%; CI 22–48%) | 0/33 (0%) |

**Prior reference** (earlier HF ladder on `spanish_basic`, same metric): 0.5B ~6%, 1.7B ~21%.

The 0.5B **explicit** run scored **41** sentences: on *hablar* the model returned largely unparseable output (9/10 samples dropped by the JSON extractor).

### Per-verb breakdown (pass@1)

| Verb | 0.5B baseline | 0.5B explicit | 0.5B self-correct | 1.7B baseline | 1.7B explicit | 1.7B self-correct |
|------|:-------------:|:-------------:|:-----------------:|:-------------:|:-------------:|:-----------------:|
| comer | 0/10 | 0/10 | 0/10 | 5/10 | 0/10 | 6/10 |
| vivir | 0/10 | 0/10 | 1/10 | 0/10 | 9/10 | 0/10 |
| hablar | 0/10 | 0/1 | 0/10 | 0/10 | 10/10 | 1/10 |
| escribir | 0/10 | 1/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| correr | 0/10 | 1/10 | 0/10 | 10/10 | 10/10 | 10/10 |

**Self-correct pass@2** equalled pass@1 on both models: no failure was repaired on the second attempt.

---

## Findings

1. **Model scale dominates at baseline.** 1.7B baseline (30%) is an order of magnitude above 0.5B (0%). This aligns with the prior HF ladder and with paradigm-isolation results showing usable Spanish morphology in parameters from ~1.7B upward.

2. **Explicit prompting helps substantially at 1.7B, not at 0.5B.** The explicit overlay roughly doubled EF vs baseline at 1.7B (58% vs 30%). At 0.5B, all conditions remained near floor (~0–5%). Instruction-following for morphology binding appears to require sufficient capacity.

3. **Gains are constraint-specific, not uniform.** At 1.7B, explicit prompting rescued *vivir* (future 3rd) and *hablar* (present 2nd) almost completely, but *comer* (1st pl. preterite) scored **worse** under explicit (0/10) than baseline (5/10). *Escribir* (3rd pl. preterite) failed under **every** condition on both models — the hardest binding target in this set.

4. **Self-correction without the gold form adds no lift.** Correction yield was **0%** at both sizes (48 and 33 rewrite attempts respectively). All pass@2 successes were already correct at pass@1. Constraint-only feedback is insufficient for the model to recover the target surface form in context.

5. **Easy cases saturate; hard cases persist.** *Correr* (yo + present) reached 10/10 at 1.7B under baseline, explicit, and self_correct. Failures concentrate on person–tense combinations that require explicit subject alignment (*hablas*, *comimos*, *escribieron*) or future morphology (*vivirá*) when the baseline prompt is used.

6. **Parsing fragility confounds explicit at 0.5B.** The explicit condition triggered format failures on *hablar*, reducing **n** to 41. Reported explicit rates on 0.5B should be interpreted alongside this extraction loss.

---

## Limitations

- **Exploratory sample size** — n=10 per constraint set; wide Wilson CIs; not powered for significance testing
- **Stochastic decoding** (`temperature=0.7`) — single sample per configuration; results are run-specific
- **Single benchmark** — five common regular verbs only; no `spanish_challenging` / `spanish_niche`
- **One metric** — EF pass does not imply grammatical or pedagogical quality
- **Prototyping path only** — ad-hoc HF batched generation, not the pipeline DB or `run_experiment.py`
- **Self-correct is one attempt** — no multi-turn or validator-guided loop
- **Cross-condition comparison on 1.7B explicit vs baseline** — verb-level trade-offs (e.g. comer) may reflect sampling variance as much as prompt effect

---

## Relation to other diagnostics

- **Verb isolation spikes** (`english_rare_verbs_qwen_spike`, `spanish_verbs_qwen_spike`): morphology in isolation improves with scale; Spanish rare lemmas lag English at 4B.
- **Paradigm spike** (`spanish_paradigm_qwen_spike`): explicit paradigm prompts lift form recall at 1.7B; sentence EF here tests whether that knowledge **binds** under CTG constraints.
- **CEFR prompt evaluation** (`spanish_basic_cefr_prompt_evaluation.md`): on a large model (GPT), morphology was near-perfect; this ablation shows small Qwen models fail primarily on **binding**, not on having *some* conjugation knowledge.

---

## Next steps

- Re-run 1.7B explicit vs baseline with fixed seed or pass@k aggregation to stabilise verb-level comparisons
- Extend to `spanish_challenging` / `spanish_niche` at 1.7B where explicit prompting showed the largest paradigm gains
- Test constrained decoding or gold-form injection as an upper-bound intervention (separate from fair self-correct)
- Investigate *escribir* / 3rd-plural preterite failures — likely person–number alignment in sentence context
