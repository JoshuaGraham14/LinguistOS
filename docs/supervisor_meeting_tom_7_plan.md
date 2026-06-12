# Supervisor meeting #7 — summary, questions, and plan

> **Source:** Meeting with Tom (June 2026). Transcript: `Tom #7.txt`.  
> **Scope:** Spanish + Hebrew only (no additional languages). Includes pedagogical direction alongside small-model / on-device work.

---

## 1. What you presented

You walked Tom through the **research evaluation pipeline**:

- **Constraint satisfaction:** `expected_form_match` — check that the generated sentence contains the gold surface form (e.g. `comimos`), derived from benchmark constraints + dictionary lookup. Not spaCy-based.
- **Grammar quality:** `grammar_languagetool` — LanguageTool pass rate; catches general grammar, not constraint-specific slips.
- **Length compliance:** short / medium / long token bands.
- **Diversity:** uniqueness, Self-BLEU, template rate, Distinct-1/2.
- **Diagnostic only:** `verb_morphology` (spaCy) — systematically under-reports vs EF; not a headline metric.
- **Language profiles:** per-language YAML (`research/languages/{es,he}.yaml`) for constraint schemas and prompt assembly.
- **Prompt:** language-agnostic, lists target word, constraints, length band; does not pass `expected_form` to the LLM.

### Key experimental results (at time of meeting)

| Benchmark | Model | Finding |
|-----------|-------|---------|
| `spanish_basic` | GPT-nano | ~100% EF at n=3, n=10, n=100 — morphology essentially solved |
| `spanish_basic` long | GPT-nano | ~99% EF; future-tense case often overshoots length band |
| `spanish_challenging` | GPT-nano, random length | ~96% EF; short sentences better than long |
| `spanish_niche` | GPT-nano, random length | **~31% EF** — rare verbs, infinitive trap, wrong forms |
| Local HF ladder | Qwen 0.5B → 1.7B → 4B | 6% → 21% → 95% EF on `spanish_basic` |
| Hebrew (E0) | GPT | ~100% on basic; degrades on harder sets (manual LLM check) |

**Main scare:** GPT is “too good” on basic Spanish — hard to show a problem worth solving.  
**Main relief:** Niche benchmark + length degradation + small-model ladder give real gaps.

---

## 2. What Tom said (themes)

### 2.1 The basic task may be “too easy” for large models

- Literature you read was **not this fine-grained** (no per-constraint EF pass rates).
- Risk: thesis feels **trivial** if framed only as “can GPT conjugate Spanish verbs?”
- **Counter-argument Tom endorsed:** Relying on the largest cloud models for simple drill sentences is **bad engineering** — cost, latency, offline requirement, environment.

### 2.2 Artificially limit the problem — small / on-device models

> *“I'm interested not in how well ChatGPT does this, but how can I condition an arbitrary model to do this?”*

- Repeat experiments on **micro LLMs** (you already started: Qwen 0.5B / 1.7B / 4B).
- **Research logic:** Techniques that help a 0.5B model should **transfer upward** — if you push 6% → 50% on small, you may push GPT’s 95% → 100% on niche/hard cases.
- Transfer is **an open question** worth stating explicitly in the thesis.
- Small models are **cheaper, faster, offline-capable** — aligned with a real app on edge devices.

### 2.3 Don’t assume failure = missing parameters only

Tom pushed back on “just add parameters”:

- **Knowledge distillation** — train small model on large model outputs (infinite synthetic data).
- **Constrained decoding** — load conjugation table → regex / token bias → when verb fires, force or backtrack to correct form.
- **External knowledge injection** — pass correct form or table cell into prompt (Tom called pure lookup “boring” but valid).
- **Generate → validate → correct loop** — small agentic loop: wrong form → “rewrite with X conjugation”.
- **Fine-tuned language-specific models** — e.g. Spanish-specialised checkpoints as a baseline.
- **Diagnostic:** Ask model **in isolation** for conjugation table — separates *knows form* vs *uses form in sentence*.

### 2.4 English diagnostic (same models, rare verbs)

- Run equivalent **rare/archaic English** verb benchmark on same model sizes.
- If small models **pass English, fail Spanish** → **multilingual training-data** problem.
- If they **fail both** → **capacity / constraint-binding** problem.
- Different interventions follow from each diagnosis.

*(Note: English diagnostic is a **control experiment**, not a third thesis language.)*

### 2.5 Hebrew and Spanish are the right pair — but test properly

- Spanish alone is **hyper-resourced**; Hebrew adds morphological richness (binyanim, prefixes/suffixes).
- **Hebrew challenge:** `expected_form` string matching may be insufficient when prefixes/suffixes attach — needs clitic-aware or richer matching (already flagged in E0 docs).
- Tom did **not** require a third language; deepening **es + he** is enough if generalisation is argued across resource level and morphology type.

### 2.6 Pedagogical / CTG angle — keep it, but don’t split focus blindly

- **CEFR / pedagogical relevance** is a separate axis from morphology (papers fine-tune for level; often simplify CEFR to vocabulary not grammar constructs).
- Tom acknowledged **two directions:** (A) small-model conditioning, (B) pedagogical control.
- **Recommendation for you:** Treat pedagogy as **second headline** — length bands, CEFR, difficulty appropriateness — not abandoned.

### 2.7 Other Tom notes

- Report **mean + std + min + max**, not means alone (future-tense length issue was easy to miss).
- **Infinitive trap** — model leaves verb uninflected; may be prompt but don’t rely on prompt engineering alone.
- **LT vs EF dissociation** — grammatically fine sentences that violate constraints; supports your multi-metric stack.
- Include GPT baseline results in report to **contextualise** what you’re improving.
- **Verb-only so far** — adding noun/context constraints may surface new failures (future extension).
- **CommonGen analogy** — “ingredients must appear” vs “model may not know ingredient”; niche verbs are closer to missing knowledge.

---

## 3. Open questions (for the thesis)

| # | Question | Why it matters |
|---|----------|----------------|
| Q1 | Is failure on niche verbs **missing training signal** or **failure to bind constraints during generation**? | Chooses RAG/conjugation lookup vs decoding vs correction loop |
| Q2 | Can the model produce the **correct form in isolation** (conjugation quiz) but fail in sentences? | If yes, intervention is generation-time, not “teach the model morphology” |
| Q3 | Do **interventions on 0.5B–1.7B transfer** to 4B and GPT on `spanish_niche`? | Core claim for on-device → cloud robustness |
| Q4 | How does **performance degrade by length band** for small models (same pattern as GPT on challenging)? | Links autoregressive commitment to pedagogical “sentence complexity” |
| Q5 | **Hebrew:** when does EF string match break vs when is it sufficient? | Informs Hebrew E1 matcher design |
| Q6 | **Pedagogy:** given high EF, do sentences match **CEFR-appropriate grammar and vocabulary**? | Second gap GPT doesn’t solve — diversity + level control |
| Q7 | **Diversity vs accuracy trade-off** — do correction loops / constrained decoding reduce template collapse or worsen it? | App needs both correct *and* varied items |

---

## 4. Possible avenues (Spanish + Hebrew, incl. pedagogy)

### Avenue A — Small-model conditioning (Tom’s primary push)

**Goal:** Make on-device models usable for morphology-constrained drills.

| Technique | Description | Experiments |
|-----------|-------------|-------------|
| **A1. Baseline ladder** | Already have GPT + Qwen 0.5B / 1.7B / 4B on `spanish_basic` | Extend to `spanish_challenging`, `spanish_niche` |
| **A2. Knowledge injection** | Inject single required form (or mini table row) into prompt from `mlconjug3` / Wiktionary | Measure EF gain vs prompt bloat |
| **A3. Generate–validate–correct** | Loop: generate → EF check → “rewrite with form X” | Count passes to target EF; measure diversity cost |
| **A4. Constrained decoding** | LogitsProcessor / regex bias toward allowed surface forms at verb position | Headline novel contribution if it works on 0.5B–1.7B |
| **A5. Transfer test** | Apply best method from A2–A4 on small model → re-run GPT on `spanish_niche` | Show 31% → X% niche improvement |
| **A6. English control** | Rare English verbs, same models | Diagnose data vs capacity (not a third product language) |

**Hebrew extension:** Run same ladder on `hebrew_basic` (when benchmark + matcher ready); compare degradation rate vs Spanish on challenging sets.

---

### Avenue B — Pedagogical control (second headline)

**Goal:** Sentences are not only morphologically correct but **appropriate for the learner**.

| Technique | Description | Experiments |
|-----------|-------------|-------------|
| **B1. Length as difficulty proxy** | Already have bands; add **reporting std/min/max** per case | Tom’s feedback; tie to “sentence complexity” |
| **B2. CEFR on benchmarks** | `spanish_challenging` already tags B1; extend labels on basic/niche | Measure whether outputs respect stated CEFR in prompt |
| **B3. Grammar-construct level** | CEFR as **allowed constructions** (e.g. A1: no subordinate clauses) not just word lists | New evaluators: max clause count, forbidden tense leakage |
| **B4. Vocabulary level** | Known-word coverage vs CEFR word list / learner lexicon | Requires lexicon resource; aligns with app’s vocab graph |
| **B5. Diversity as pedagogical quality** | Template collapse = bad drills | Already measured; set targets (e.g. max template rate) |
| **B6. Explicit subject anchoring** | Already 71% → 100% EF on challenging long | Pedagogical side effect: clearer drill sentences for learners |

**Thesis framing:** GPT hits **EF** on basic Spanish but fails **pedagogical usefulness** (repetitive, wrong complexity, niche gaps). LinguistOS improves **usable practice item rate**, not raw conjugation alone.

---

### Avenue C — Hebrew morphological richness

**Goal:** Show framework generalises beyond Romance string-match morphology.

| Step | Description |
|------|-------------|
| C1 | Merge / finish E1: clitic-aware or normalised `expected_form_match` for Hebrew |
| C2 | `hebrew_basic` + `hebrew_challenging` benchmarks (parallel to Spanish) |
| C3 | Same model ladder (GPT + small HF) on Hebrew — expect **faster degradation** than Spanish (Tom’s prediction) |
| C4 | Compare: prefix/suffix attachment errors vs Spanish person/tense slips |

---

### Avenue D — What to deprioritise (for now)

- Third natural language (Welsh, Romanian, etc.) — **out of scope per your direction**
- Full model fine-tuning from scratch — resource-heavy; use LoRA only as optional baseline
- spaCy as headline metric — keep diagnostic only
- Prompt-engineering-only fixes — Tom: “prompt engineering is boring”; use as ablation, not contribution
- Human ratings — deferred unless time allows (Phase D)

---

## 5. Recommended integrated thesis story

> **Problem:** Large models satisfy fine-grained morphological constraints on high-resource Spanish almost perfectly, but (1) **fail on low-frequency forms**, (2) produce **template-heavy, pedagogically weak** drills at scale, and (3) **small on-device models** cannot yet be relied on without scaffolding. Hebrew adds **morphological complexity** that stress-tests matching and generation.

> **Contribution:** LinguistOS — a pipeline that (a) evaluates constraint satisfaction, grammar, length, and diversity; (b) applies **inference-time conditioning** (knowledge injection, validation loops, constrained decoding) to raise small-model EF; (c) extends toward **pedagogical appropriateness** (CEFR, complexity, diversity).

> **Evidence axes:**
> - GPT ceiling + niche failure (`spanish_niche` ~31% EF)
> - Size ladder (6% → 21% → 95% → 100%)
> - Intervention transfer (small → large)
> - Hebrew vs Spanish degradation
> - Pedagogy metrics (length, clauses, templates, CEFR)

---

## 6. Action plan (prioritised)

### Immediate (this week)

- [ ] **Document GPT baselines** in interim/final report (basic 100%, niche 31%, challenging 96%) — Tom: contextualises work
- [ ] **Fix summary tables:** mean, std, min, max for length and EF per constraint set
- [ ] **Run HF ladder on `spanish_challenging` and `spanish_niche`** (Qwen 0.5B, 1.7B, 4B) — same presets as basic
- [ ] **Conjugation isolation test:** prompt small models for table cell only (no sentence) — Q1/Q2

### Short term (1–2 weeks)

- [ ] **Implement generate–validate–correct** wrapper around `baseline_hf`
- [ ] **Implement soft knowledge injection** (single expected form in prompt from conjugation library)
- [ ] **Re-run** with interventions; compare EF + diversity on basic + niche
- [ ] **Transfer test:** best intervention on GPT `spanish_niche`

### Medium term (2–4 weeks)

- [ ] **Constrained decoding prototype** (LogitsProcessor + allowed forms)
- [ ] **Pedagogical evaluators (minimal):** e.g. clause ceiling by CEFR, template rate thresholds in report
- [ ] **Hebrew E1:** clitic-aware matching + small benchmark run (GPT + one small model)

### Writing

- [ ] Add section: “Why cloud LLMs are insufficient for a learning app” (cost, offline, latency, environment)
- [ ] Add section: “Literature gap — prior work not this fine-grained”
- [ ] Explicit **limitations:** verb-only, automatic metrics only, single temperature unless ablated

---

## 7. Commands reference (current presets on `main`)

```bash
# GPT baselines
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_default_n100 --live
python3 -m research.run_experiment --benchmark spanish_challenging --method baseline_random_n50 --live
python3 -m research.run_experiment --benchmark spanish_niche --method baseline_random_n50 --live

# Local HF ladder (Spanish basic — extend to challenging/niche)
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_hf_qwen05b_n20 --live
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_hf_qwen3_17b_n20 --live
python3 -m research.run_experiment --benchmark spanish_basic --method baseline_hf_qwen3_4b_n20 --live
```

---

## 8. Decisions captured (your preferences)

| Decision | Choice |
|----------|--------|
| Languages | **Spanish + Hebrew only** |
| Primary technical track | **Small / on-device models + conditioning** |
| Secondary track | **Pedagogical control** (length, CEFR, diversity, complexity) |
| Headline metric | **`expected_form_match`** |
| Cloud model role | **Ceiling + transfer target**, not the product story |
| Third language | **Not planned** |

---

*Last updated: June 2026 — after supervisor meeting #7 and HF baseline merge to `main`.*
