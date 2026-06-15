# English rare-verb Qwen diagnostic

**Experiment:** 1 — English rare-verb Qwen diagnostic (control)  
**Date run:** 2026-06-12 (results committed ~16:43 GMT+1; exact start time not recorded)  
**Date documented:** 2026-06-15  
**Track:** Small-model conditioning (supervisor meeting #7, Avenue A6)  
**Script:** `research/prototyping/english_rare_verbs_qwen_spike.py`  
**Raw results:** `docs/spike-results/eval_english_rare_verbs_qwen_spike_results.json`  
**Status:** Exploratory spike; not run through `run_experiment.py` or the evaluation pipeline

---

## Purpose

Control experiment for the small-model conditioning track (supervisor meeting #7, Avenue A6). Before testing Spanish niche verbs, establish whether Qwen models can **store and retrieve English irregular morphology** when the lemma is known.

If small models pass English conjugation but fail Spanish at the same parameter count, failure is likely **multilingual training-data scarcity**. If they fail both, **model capacity / instruction-following** is the more plausible explanation.

Two sub-tasks were tested:

1. **Recognition** — given an English gloss, return the base-form lemma
2. **Conjugation** — given lemma + form label, return one inflected surface form (primary diagnostic)

---

## Experimental design

### Stimulus set

16 English verbs in two tiers, hard-coded in the spike script:

| Tier | n | Examples | Forms tested |
|------|---|----------|--------------|
| **Common irregular** | 6 | rise, lay, swim, steal, bind, forgo | past tense, past participle |
| **Rare / literary irregular** | 10 | gainsay, beseech, smite, shrive, cleave, gird, forswear, betide, clothe, wreak | past tense, past participle |

Gold answers were taken from standard dictionary entries (OED / Merriam-Webster style). Listed alternates (e.g. *besought* / *beseeched*, *clad* / *clothed*) were accepted as correct.

**Total probes per model:** 48 (16 recognition + 32 conjugation).

### Models (independent variable: parameter count)

| Label | Checkpoint |
|-------|------------|
| qwen05b | `Qwen/Qwen2.5-0.5B-Instruct` |
| qwen17b | `Qwen/Qwen3-1.7B` |
| qwen4b | `Qwen/Qwen3-4B-Instruct-2507` |

Same three-model ladder as the existing HF Spanish baselines.

### Fixed parameters

| Parameter | Value |
|-----------|-------|
| Device | Apple MPS (local inference) |
| Decoding | Greedy (`temperature=0`, `do_sample=False`) |
| Max new tokens | 32 |
| Qwen3 thinking mode | Disabled |
| Samples per probe | 1 |
| Scoring | First alphabetic token extracted; case-insensitive exact match against gold set |
| Confidence intervals | Wilson 95% CI on pass rates |

### Prompts

Each probe is a two-turn chat (via the model’s Hugging Face chat template):

**System message (fixed):**
> You are a precise English morphology assistant. Follow the instruction exactly. Give only the requested word.

**User message templates:**

| Task | Template |
|------|----------|
| Recognition | What is the base form (infinitive) of the English verb that means "{gloss}"? Reply with one word only. |
| Conjugation | What is the {form_label} of the English verb "{lemma}" (meaning: {gloss})? Reply with one word only. |

`{form_label}` is either `past tense` or `past participle`.

**Concrete examples:**

*Recognition — gainsay:*
```
System: You are a precise English morphology assistant. Follow the instruction exactly. Give only the requested word.
User:   What is the base form (infinitive) of the English verb that means "to deny or contradict"? Reply with one word only.
Gold:   gainsay
```

*Conjugation — smite, past tense:*
```
System: You are a precise English morphology assistant. Follow the instruction exactly. Give only the requested word.
User:   What is the past tense of the English verb "smite" (meaning: to strike heavily)? Reply with one word only.
Gold:   smote
```

No sentence generation, no constraint YAML, no external conjugation lookup passed to the model.

### Secondary metric

**Infinitive fallback rate** — on conjugation probes, the model returned the bare lemma instead of an inflected form (analogous to the Spanish “infinitive trap”).

---

## Results

### Conjugation (primary outcome)

| Model | Common irregular (n=12) | Rare irregular (n=20) | All conjugation (n=32) |
|-------|-------------------------|-------------------------|------------------------|
| **0.5B** | 2/12 (17%; CI 5–45%) | 1/20 (5%; CI 1–24%) | 3/32 (9%; CI 3–24%) |
| **1.7B** | 7/12 (58%; CI 32–81%) | 12/20 (60%; CI 39–78%) | 19/32 (59%; CI 42–74%) |
| **4B** | 11/12 (92%; CI 65–99%) | 20/20 (100%; CI 84–100%) | 31/32 (97%; CI 84–99%) |

### Recognition (secondary outcome)

| Model | Pass rate (n=16) | Wilson 95% CI |
|-------|------------------|---------------|
| 0.5B | 0/16 (0%) | 0–19% |
| 1.7B | 2/16 (13%) | 4–36% |
| 4B | 3/16 (19%) | 7–43% |

Models overwhelmingly returned **synonyms** (*deny* for *gainsay*, *strike* for *smite*, *place* for *lay*) rather than the target lemma. This reflects gloss→lemma retrieval difficulty and prompt compliance, not morphology per se.

### Infinitive fallback (conjugation probes only)

| Model | Fallback count | Rate |
|-------|----------------|------|
| 0.5B | 0/32 | 0% |
| 1.7B | 7/32 | 22% |
| 4B | 0/32 | 0% |

At 1.7B, wrong answers often echoed the lemma (*shrive*, *wreak*, *forgo*) or regularised forms (*stealed*, *gained* for *gainsaid*).

### Representative errors (4B conjugation — sole failure)

| Probe | Expected | Got |
|-------|----------|-----|
| forgo / past tense | forwent | forgoed |

All other rare-tier forms at 4B were correct, including *gainsaid*, *smote*, *shriven*, *forswore*, *clad*.

---

## Findings

1. **English morphology is present in Qwen at sufficient scale.** The 4B model scored 97% on isolated conjugation, including 100% on the rare/archaic tier. Rare English irregulars are not uniformly absent from model parameters.

2. **Performance scales sharply with parameter count.** Conjugation rose from 9% (0.5B) → 59% (1.7B) → 97% (4B). The ladder mirrors the Spanish `spanish_basic` pattern (6% → 21% → 95% EF), suggesting a shared capacity floor rather than a language-specific one at small sizes.

3. **Rare and common tiers are not clearly separated at 1.7B+.** At 1.7B, rare-tier conjugation (60%) matched common-tier (58%). At 4B, rare verbs were handled as well as common ones. Lexical rarity alone does not explain failure once the model is large enough.

4. **Recognition is a poor morphology proxy.** Gloss→lemma mapping failed even at 4B (19%), because models paraphrase with high-frequency synonyms. **Conjugation with the lemma supplied** is the valid diagnostic for this experiment.

5. **Failure modes differ by size.** 0.5B produces unrelated tokens or present-tense defaults (*rises* for *rose*). 1.7B regularises (*stealed*) or confuses near neighbours (*gained* for *gainsaid*, *befell* for *betide*). 4B fails only on low-frequency irregulars (*forwent*).

6. **Implication for the Spanish follow-up.** If Spanish niche conjugation remains poor at 4B while English rare conjugation is near-ceiling, the bottleneck is likely **Spanish-specific training signal**, not parameter storage alone. A paired Spanish isolation test (Test 2) is required to confirm.

---

## Limitations

- Single greedy sample per probe — no pass@k or temperature ablation
- n=1 per cell — Wilson CIs are wide; exploratory only
- Gold forms manually curated; no programmatic dictionary source
- Recognition task confounded by synonym substitution
- English has fewer inflected forms per verb than Spanish — cross-language comparison is directional, not symmetric
- Local MPS inference only; no batching or latency analysis reported here
- Not stored in the research DB pipeline

---

## Next steps

- Run **Test 2**: identical isolation protocol on Spanish verbs from `spanish_basic`, `spanish_challenging`, and `spanish_niche` benchmarks
- Compare conjugation pass rates English vs Spanish at each model size in a single table
- Drop or redesign the recognition sub-task; retain conjugation-only for the paired comparison
- Optionally add pass@20 at `temperature=0.7` to separate *knowledge* from *sampling reliability*
