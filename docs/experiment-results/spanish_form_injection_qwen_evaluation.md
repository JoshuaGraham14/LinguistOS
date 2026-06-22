# Spanish form-injection — Qwen 0.5B vs 1.7B on `spanish_basic`

**Experiment:** 6 — Sentence-level form-injection ablation on `spanish_basic`
**Date run:** 2026-06-17
**Date documented:** 2026-06-17
**Track:** Small-model conditioning (supervisor meeting #7); direct follow-up to Exp 5
**Script:** `research/prototyping/spanish_form_injection_qwen_spike.py`
**Raw results:** `docs/spike-results/eval_spanish_form_injection_qwen_results.json`
**Status:** Exploratory spike; not run through `run_experiment.py` or the pipeline DB

---

## Purpose

Exp 3 (paradigm isolation) and Exp 5 (prompt ablation) jointly suggested that Qwen 1.7B fails on `spanish_basic` sentence generation not because it lacks Spanish morphology in its parameters, but because it cannot reliably **bind** the right surface form under constrained text generation (CTG). Exp 5 also showed that constraint-only self-correction (no gold form passed to the rewriter) yielded 0% repairs.

This experiment tests the natural upper bound: **what happens to expected-form-match (EF) when the exact gold surface form is injected into the prompt?** If the residual gap from Exp 5's 58% explicit ceiling is purely CTG binding, form injection should drive EF close to 100%.

It is the cleanest realisation of Tom's "external knowledge injection" suggestion from supervisor meeting #7. In production this gold form would come from a conjugation library (e.g. `mlconjug3`) or RAG; for this spike the form is taken directly from the benchmark YAML's `expected_form` field, isolating the upper-bound question first.

---

## Experimental design

### Conditions

Four conditions per model, two existing from Exp 5 (re-run as same-session controls) and two new:

| Condition | Prompt | Gold form leaked? |
|-----------|--------|-------------------|
| **baseline** | `build_prompt` | No |
| **explicit** | `build_prompt_explicit` (Spanish overlay) | No |
| **form_injected** | `build_prompt` + injected gold form | **Yes** |
| **form_injected_explicit** | `build_prompt_explicit` + injected gold form | **Yes** |

The injection is a single line appended to the prompt, immediately before the JSON-shape instruction:

> Required surface form: the verb "{keyword}" must appear in each sentence exactly as "{expected_form}" — use this conjugated surface form verbatim (one token, no infinitive, no other conjugation).

All other prompt components are unchanged from Exp 5, so `baseline` and `explicit` are byte-identical to that experiment's prompts.

### Fixed parameters (matched to Exp 5 for direct comparability)

| Parameter | Value |
|-----------|-------|
| Benchmark | `spanish_basic` (5 constraint sets, A1) |
| Models | `Qwen/Qwen2.5-0.5B-Instruct`, `Qwen/Qwen3-1.7B` |
| Device | Apple MPS (local HF inference) |
| Decoding | Same as `BaselineHFGenerator`; greedy disabled |
| Temperature | 0.7 |
| Sentence length | `short` (2–5 tokens) |
| Samples per constraint set | 10 |
| Total scored sentences per model × condition | 50 |
| Qwen3 thinking mode | Disabled |
| EF scoring | `ExpectedFormMatchEvaluator` — exact gold token in sentence |
| Length scoring | `LengthInBandEvaluator` |
| Grammar scoring | `LanguageToolGrammarEvaluator` (`grammar_languagetool`) |
| Uncertainty | Wilson 95% CI on pass rates |

### Constraint sets (`spanish_basic`)

| Keyword | Expected form | Tense | Person | Number |
|---------|--------------|-------|--------|--------|
| comer | comimos | preterite | 1st | plural |
| vivir | vivirá | future | 3rd | singular |
| hablar | hablas | present | 2nd | singular |
| escribir | escribieron | preterite | 3rd | plural |
| correr | corro | present | 1st | singular |

### Exact prompts used

**System message** (all conditions):

```text
You are a helpful Spanish language tutor. Always respond with valid JSON.
```

**Baseline** (example: *comer*, preterite 1st plural, A1, short):

```text
You generate Spanish example sentences for vocabulary practice.
Target word (lemma): "comer" (English: "to eat")
Constraints:
  Tense: Preterite (pretérito indefinido)
  Person: 1st
  Number: Plural
  length: short (2–5 tokens).
The target verb "comer" must appear in the sentence inflected to match
tense=preterite, person=1st, number=plural — not as the bare infinitive
unless the constraints require it.
Target learner level: CEFR A1 (beginner). Vocabulary and grammar must be
appropriate for this fluency level. Use only short, simple sentences
(subject–verb–object). Avoid subordinate clauses (e.g. que, porque,
cuando, si), passive voice, and any grammar above beginner level.
Produce 10 natural Spanish sentences within the length band. Each
sentence must contain the target verb inflected as specified above,
with its English translation.
Reply ONLY as JSON in this exact shape:
{"candidates":[{"sentence":"...","translation":"..."}, ...]}
```

**Explicit** = baseline + the Spanish overlay appended (subject pronoun, tense label, infinitive ban, length restatement) — unchanged from Exp 5.

**Form injected** = baseline + this single inserted line before the "Produce…" instruction:

```text
Required surface form: the verb "comer" must appear in each sentence
exactly as "comimos" — use this conjugated surface form verbatim
(one token, no infinitive, no other conjugation).
```

**Form injected + explicit** = explicit prompt with the same injection line.

---

## Results

### Headline EF pass rate

Wilson 95% CI in parentheses.

| Model | Baseline | Explicit | Form injected | Form injected + explicit |
|-------|---------:|---------:|-------------:|-------------------------:|
| **0.5B** | 4/50 (8%; CI 3–19%) | 4/50 (8%; CI 3–19%) | 9/50 (18%; CI 10–31%) | **13/50 (26%; CI 16–40%)** |
| **1.7B** | 17/50 (34%; CI 22–48%) | 30/50 (60%; CI 46–72%) | 30/50 (60%; CI 46–72%) | **49/50 (98%; CI 90–100%)** |

Reference (Exp 5, same models, same benchmark): 0.5B baseline 0%, 0.5B explicit 5%; 1.7B baseline 30%, 1.7B explicit 58%. The same-session re-run of baseline/explicit reproduces those numbers within sampling noise.

### Length-in-band and grammar (sanity that EF gains are real)

If form injection inflated EF only because the model echoed the gold token in degenerate sentences, length compliance and/or grammar would collapse. They do not.

| Model | Condition | EF | Length-in-band | Grammar (LT) |
|-------|-----------|---:|---:|---:|
| 0.5B | baseline | 8% | 56% | 100% |
| 0.5B | explicit | 8% | 26% | 96% |
| 0.5B | form_injected | 18% | 32% | 100% |
| 0.5B | form_injected_explicit | 26% | 34% | 98% |
| 1.7B | baseline | 34% | 66% | 100% |
| 1.7B | explicit | 60% | 80% | 96% |
| 1.7B | form_injected | 60% | 84% | 100% |
| 1.7B | **form_injected_explicit** | **98%** | **96%** | **100%** |

The combined condition at 1.7B is essentially saturated on every axis. Grammar stays at 100%; length compliance rises to 96%; EF reaches 98%.

### Per-verb EF (1.7B)

| Verb | Baseline | Explicit | Form injected | Form injected + explicit |
|------|---:|---:|---:|---:|
| comer (comimos) | 7/10 | **0/10** | 10/10 | 10/10 |
| vivir (vivirá) | 0/10 | 10/10 | **0/10** | 10/10 |
| hablar (hablas) | 0/10 | 10/10 | **0/10** | 9/10 |
| escribir (escribieron) | 3/10 | 0/10 | 10/10 | 10/10 |
| correr (corro) | 1/10 | 10/10 | 10/10 | 10/10 |

The two interventions are **complementary rather than redundant**:

- *Explicit alone* rescues *vivir*, *hablar*, *correr* (verbs whose failure mode is wrong subject/person) but fails on *comer* and *escribir*.
- *Form injection alone* rescues *comer*, *escribir*, *correr* (verbs whose failure mode is wrong stem/tense morphology) but fails on *vivir* and *hablar*.
- *Combined* rescues every verb.

### Why does form_injected alone fail on vivir and hablar?

The failure mode in those cells is a **subject-person default**, not a misread of the form line. Representative outputs:

```text
gold: vivirá (3rd sing future)
model: "Viviré una vacación en España." (1st sing future)
model: "Viviré la vida con mis amigos."
model: "Viviré el próximo año en otra ciudad."

gold: hablas (2nd sing present)
model: "Hablo con María."   (1st sing present)
model: "Hablo en español."
model: "Hablo de la fiesta."
```

Even with the gold form printed in the prompt, the model defaults to first-person when the prompt does not explicitly name the subject pronoun. The explicit overlay adds that subject anchoring (`Subject: use él/ella…`, `Subject: use tú…`), which is why the combined condition rises to 98%.

### Representative 1.7B form_injected_explicit outputs

```text
comer  (comimos)     OK [3t] "comimos la pizza"
                     OK [3t] "comimos la ensalada"
vivir  (vivirá)      OK [4t] "Él vivirá en Madrid."
                     OK [5t] "Él vivirá con su familia."
hablar (hablas)      OK [2t] "Hablas tú"
                     NO [2t] "Hablo tú"      <-- the single failure
escribir (escribieron) OK [5t] "Ellos escribieron un correo electrónico."
                       OK [4t] "Ellos escribieron una carta."
correr (corro)       OK [4t] "corro a la escuela"
                     OK [2t] "corro rápido"
```

The single 1.7B failure is the same person-default failure mode appearing once after the overlay; the model produced *Hablo tú* (1st-singular verb with 2nd-singular pronoun) instead of *Hablas tú*.

---

## Findings

1. **The 1.7B sentence-level binding gap closes almost entirely when the gold form is injected on top of the explicit overlay.** EF rises from a 30% baseline (Exp 5) to **98%**, with grammar at 100% and length compliance at 96%. This is the cleanest empirical confirmation to date that the residual `spanish_basic` failure on 1.7B is CTG binding, not absent knowledge.

2. **Form injection and explicit prompting fix orthogonal failure modes and stack additively.** Each intervention alone caps at 60% EF; together they reach 98%. The mechanism is interpretable: form injection supplies the correct morphological surface; the explicit overlay anchors the correct subject pronoun. Models that get one but not the other revert to first-person defaults (*Viviré* for *Vivirá*, *Hablo* for *Hablas*).

3. **Form injection alone (without the explicit overlay) is roughly equivalent to explicit prompting alone (60% vs 60%) — but on different verbs.** This is a non-obvious result: passing the exact answer in the prompt is not strictly stronger than telling the model the constraints; both interventions cap at the same EF rate but solve different sub-tasks.

4. **0.5B remains capacity-limited.** Even with the gold form *and* the explicit overlay, 0.5B reaches only 26% EF, and length compliance stays at 34%. The bottleneck at this scale is upstream of binding — instruction following and JSON formatting cap output quality before morphology becomes the limiting factor. Form injection does not rescue this model class.

5. **EF gains at 1.7B are not gamed.** A degenerate "echo the form" failure mode would collapse length compliance and grammar. Instead the 1.7B form_injected_explicit condition is at **100% grammar, 96% length, 98% EF** — the sentences are genuinely well-formed Spanish around the target form. Manual inspection of all five verbs confirms naturalistic outputs (*"Él vivirá en Madrid"*, *"Ellos escribieron una carta"*).

6. **Diversity is not measured here, but is the next likely failure axis.** With the surface form pinned and very short sentences, content templates compress (*"comimos la {food}"* appears repeatedly). Headline EF saturates; lexical and structural diversity almost certainly degrade. Diversity scoring is an explicit limitation of this spike and the priority for the next experiment.

---

## Limitations

- **Sample size:** n=10 per constraint set × 5 sets = 50 sentences per condition × model. Wilson CIs are wide on per-verb cells.
- **Single benchmark:** `spanish_basic` only. The knowledge-gap story (Exp 1/2) lives on `spanish_niche`, and is not directly tested here — form injection is expected to help even more there, but that is the **next** experiment.
- **Oracle form source:** the gold form comes from the benchmark YAML, not from a real conjugation library. A production system would call `mlconjug3` (or equivalent) given lemma + tense + person + number; the present spike isolates whether injection works before introducing a lookup-table dependency.
- **Diversity unmeasured:** distinct-n, Self-BLEU, and template rate are not scored. The 98% EF result may come with template collapse; a follow-up should include them.
- **One temperature, no seed pinning:** `temperature=0.7`, single sample per configuration. Verb-level instability seen in Exp 5 is reduced (because the combined condition saturates) but a multi-seed run would tighten CIs further.
- **Person-default still visible:** the single 1.7B failure (*Hablo tú* for *Hablas*) shows the model can still revert person even with both interventions; constrained decoding at the verb position would close this last gap deterministically.
- **No CTG / constrained-decoding comparison:** that is the planned Exp 7.
- **No transfer test to GPT yet:** Q3 (small → large transfer on `spanish_niche`) is unaddressed here.

---

## Relation to other experiments

- **Exp 3 (paradigm isolation):** confirmed 1.7B has common-verb paradigms in parameters. This experiment confirms the residual sentence-level failure is binding, not absence — closing the question.
- **Exp 5 (prompt ablation):** established 30% / 58% baseline/explicit anchors and showed self-correction without the gold form yields 0% repairs. This experiment shows the gold form is exactly the missing ingredient.
- **Exp 2 (paired isolation):** suggested rare-Spanish failure is a knowledge gap, not capacity. The next logical step is to apply form injection to `spanish_niche` and check whether the same intervention closes that gap too.

---

## Next steps

1. **Apply form injection to `spanish_challenging` and `spanish_niche`** (Exp 7) — the diagnostic story predicts that rare-verb EF should also rise sharply, because the missing ingredient at 4B was the form itself. Quantify whether form injection closes the rare-verb gap on 1.7B and 4B.
2. **Add diversity evaluators inline** — distinct-1/2, Self-BLEU, template rate. The 98% EF result is hollow if template collapse is severe.
3. **Replace oracle injection with `mlconjug3` lookup** in a second pass; verify EF rate is preserved when the gold form comes from a library rather than the benchmark YAML.
4. **Constrained decoding on 1.7B** (Exp 8) — the *Hablo tú* failure mode is a logits-level commitment that constrained decoding at the verb position would fix deterministically. This is the headline novel-method experiment.
5. **Transfer test on GPT `spanish_niche`** (Exp 9) — once form injection works on small models for rare verbs, apply the same intervention to the cloud model and report `31% → X%` on `spanish_niche`.
