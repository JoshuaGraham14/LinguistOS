# Handoff: Direction 1 pilot — constrained decoding vs form injection

Copy this into a new chat to implement or run the Direction 1 pilot series.

**Registry:** `research/directions/registry.yaml`  
**Assessment context:** `docs/thesis/technical_directions_assessment.md`

---

## 1. Purpose

Diagnostics (3–5) already established:

- Binding gap: model often knows forms in isolation but fails in sentences.
- Explicit prompting helps but does not close the gap.
- Form injection (Diagnostic 5B) raises expected-form match sharply; grammar/agreement can regress.

**Direction 1** is the **build phase**: enforce the gold verb form **during beam search** instead of (or compared to) putting it in the prompt.

This **pilot** does not re-prove diagnostic claims. It asks:

1. Does **hard/soft constrained decoding** match **form injection** on expected-form match?
2. Does it do **better on grammar** (LanguageTool)?
3. Does **JSON vs plain-text output** change results for injection and beam alike?

---

## 2. Research questions (one line per arm)

**Direction 1 (series):**  
On hl50, does decode-time form forcing match or beat form injection on expected-form match while improving grammar — and does output format (JSON vs plain) matter equally for both?

| ID | Question |
|----|----------|
| **inject-json** | With gold form in the prompt and JSON output (5B-style), greedy decode, what are expected-form, grammar, and length on hl50? |
| **inject-plain** | Same injection with plain-text output — format-fair baseline for plain beam arms. |
| **1A-hard-plain** | Hard beam mask, plain text, no injection — vs inject-plain: same form enforcement mechanism, different layer (decode vs prompt). |
| **1A-hard-json** | Hard beam under production JSON — does format break beam vs hard-plain? |
| **1B-soft-plain** | Soft logit bias (λ=5), plain — satisfaction vs hard-plain and inject-plain. |
| **1B-soft-json** | Soft bias, JSON — same under production scaffold. |

---

## 3. Benchmark: `spanish_direction_hl50`

| Property | Value |
|----------|-------|
| Verbs | **50** — 25 high-tier + 25 low-tier |
| Irregularity | 12 regular + 13 irregular per tier (seed 42) |
| Mid tier | **Excluded** (sharp frequency contrast) |
| Cells per verb | 31 (5 tenses × 6 persons + participle) |
| Constraint sets | **1,550** |
| Model | Qwen3-1.7B |
| Length | `short`, no CEFR |
| Manifest | `research/evaluation/lexicon/experiment_verbs/manifest_direction_hl50.csv` |

### Build and load

```bash
python3 -m research.scripts.build_direction_pilot_manifest
# → manifest_direction_hl50.csv (50 verbs)

python3 -m research.scripts.build_diagnostic_5_benchmark \
  --manifest research/evaluation/lexicon/experiment_verbs/manifest_direction_hl50.csv \
  --name spanish_direction_hl50 \
  --output research/benchmarks/spanish_direction_hl50.yaml

python3 -m research.benchmarks.loader research/benchmarks/spanish_direction_hl50.yaml
```

Smoke (2 verbs): add `--limit-verbs 2 --name spanish_direction_hl50_smoke` to the benchmark builder.

---

## 4. Fixed protocol (all core arms)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Samples per cell** | **1** | Fair pairing: beam is deterministic; no duplicate identical runs. |
| **Injection temperature** | **0** (greedy) | Comparable pass@1 to deterministic beam. Diagnostic 5B used T=0.7, n=10 — cite separately. |
| **Beam** | `num_beams=4`, `do_sample=false` | Matches `escribiréis` spike. |
| **Soft bias λ** | **5.0** | Pilot default; optional smoke sweep {2, 5, 10} before full hl50. |
| **Form in prompt** | Injection arms only | Beam arms never leak gold form in text. |
| **Runner** | `python -m research.run_experiment --live --resume` | Same DB + scorecard as Diagnostic 5. |

### Why T=0 for injection

Diagnostic 5B used T=0.7 with 10 samples for stochastic diversity. This pilot uses **n=1** and compares to **deterministic beam**. Greedy injection (T=0) gives one canonical sentence per cell — same logic as one beam path. Note in the thesis: *full Diagnostic 5B on n=150 used T=0.7, n=10.*

### Diversity metrics at n=1

Within-cell diversity (self-BLEU across candidates in one cell) is **not meaningful** at n=1. You still report experiment-level roll-ups and cross-cell variety. For the injection-diversity story, **cite Diagnostic 5B (n=150)**.

---

## 5. Pilot run table (6 core arms)

| ID | Registry id | Decode | Output | Inject | T | Samples | Method (to implement) |
|----|-------------|--------|--------|--------|---|---------|------------------------|
| **inject-json** | `direction_1_inject_json` | Greedy | JSON | Yes | 0 | 1 | `baseline_hf_form_injected` |
| **inject-plain** | `direction_1_inject_plain` | Greedy | Plain | Yes | 0 | 1 | `baseline_hf_form_injected_plain` |
| **1A-hard-plain** | `direction_1a_hard_plain` | Beam hard | Plain | No | — | 1 | `constrained_hf_hard_plain` |
| **1A-hard-json** | `direction_1a_hard_json` | Beam hard | JSON | No | — | 1 | `constrained_hf_hard_json` |
| **1B-soft-plain** | `direction_1b_soft_plain` | Beam soft | Plain | No | — | 1 | `constrained_hf_soft_plain` |
| **1B-soft-json** | `direction_1b_soft_json` | Beam soft | JSON | No | — | 1 | `constrained_hf_soft_json` |

### Prompt mapping

| Output | Prompt builder | Notes |
|--------|----------------|-------|
| JSON, no inject | `build_prompt` | Same constraint labels as Diagnostic 5A |
| JSON, inject | `build_prompt` + injection line | Same as Diagnostic 5B |
| Plain, no inject | `build_prompt_plain` *(new)* | One Spanish sentence per line; same constraints |
| Plain, inject | `build_prompt_plain` + injection line *(new)* | Fair vs inject-json |

Plain prompts must carry the **same morphological constraints** as JSON arms (verb, tense, person, number, length band); only the output scaffold differs.

---

## 6. Metrics (evaluation pipeline)

All arms scored identically via `run_experiment`:

| Metric | Evaluator | Pilot priority |
|--------|-----------|------------------|
| Expected-form match | `ExpectedFormMatchEvaluator` | **Primary** |
| Grammar | `LanguageToolGrammarEvaluator` | **Primary** (vs injection) |
| Length in band | `LengthInBandEvaluator` | Secondary |
| Uniqueness, self-BLEU, template rate, distinct-n | Group metrics | Cross-cell / experiment level at n=1 |

**Headline:** sentence-level pass rates (% of sentences passing each metric).

**Agreement errors:** Manual spot-check or parser pass on a subset initially; full agreement metric is Direction 2. Flag subject–verb mismatches (e.g. *nosotros escribiréis*) in write-up.

---

## 7. Headline comparisons

| Priority | Contrast | Success looks like |
|----------|----------|-------------------|
| **1** | **1A-hard-plain vs inject-plain** | EF ≈ inject; **grammar ≥ inject** |
| **2** | **1A-hard-json vs inject-json** | Same under JSON scaffold |
| **3** | **1A-hard-json vs 1A-hard-plain** | Quantify JSON cost on beam |
| **4** | **inject-json vs inject-plain** | Quantify JSON cost on injection |
| **5** | **1B-soft-plain vs 1A-hard-plain** | Soft vs hard trade-off |
| **6** | **1A-hard-plain vs Diagnostic 5B** (n=150, cite) | Pilot confirms direction of full-scale 5B |

---

## 8. Implementation checklist

### Generators (`research/generation/`)

- [ ] `build_prompt_plain` in `prompt_builder.py` (constraints + one sentence line, no JSON)
- [ ] `baseline_hf_form_injected_plain` — inject + plain + greedy
- [ ] `constrained_hf.py` — shared token encoding / `force_words_ids`
- [ ] `constrained_hf_hard_plain`, `constrained_hf_hard_json`
- [ ] `constrained_hf_soft_plain`, `constrained_hf_soft_json` — `LogitsProcessor` with λ=5
- [ ] Register all in `GENERATOR_REGISTRY`

### Method YAMLs (`research/methods/baseline/`)

One YAML per arm, e.g.:

- `direction_1_inject_json_hl50.yaml`
- `direction_1_inject_plain_hl50.yaml`
- `direction_1a_hard_plain_hl50.yaml`
- … etc.

Each: `benchmark: spanish_direction_hl50`, `samples_per_case: 1`, model Qwen3-1.7B, temperature 0 where applicable.

### Cluster scripts (`research/scripts/cluster/`)

Optional Slurm wrappers mirroring Diagnostic 5 pattern.

### Constraint failure log

Log cells where hard beam fails (empty output, form not found post-hoc) for tokenisation debugging.

---

## 9. Run order

### Phase A — Infrastructure

1. Build + load `spanish_direction_hl50`.
2. Smoke benchmark (2 verbs) + **1A-hard-plain** only — validate generator + DB pipeline.

### Phase B — Injection baselines (fast, greedy)

3. **inject-json**
4. **inject-plain**

### Phase C — Beam core

5. **1A-hard-plain**
6. **1A-hard-json**

### Phase D — Soft beam

7. **1B-soft-plain**
8. **1B-soft-json**

### Example commands

```bash
python3 -m research.run_experiment \
  --benchmark spanish_direction_hl50 \
  --method direction_1_inject_plain_hl50 \
  --live --resume
```

Repeat for each method YAML.

---

## 10. Compute estimate

| Arm | Generations |
|-----|-------------|
| Each core arm | 1,550 |
| 6 core arms | **~9,300** |

Manageable on GPU vs one Diagnostic 5 arm on n=150 (~46,500 with n=10). Expect **~6–12 hours** for all six arms on one A30 (beam arms slower than greedy inject).

---

## 11. Promotion criteria (pilot → main n=150)

| Outcome | Action |
|---------|--------|
| 1A-hard-plain ≈ inject-plain on EF, better grammar | **Main 1A** on n=150, plain |
| 1A-hard-json ≈ 1A-hard-plain | Main 1A on n=150, JSON (pipeline parity) |
| 1A-hard-json ≪ 1A-hard-plain | Main 1A plain; document JSON limitation |
| 1A-hard-plain barely beats inject-plain | Debug tokenisation / constraint before scaling |
| 1B useful middle ground | Main 1B at pilot λ |
| Pilot inconclusive | Fix pipeline; do not scale |

Main arms: `spanish_diagnostic_n150`, same chosen format + decode settings, still **n=1** for beam vs greedy inject unless you add a diversity arm.

---

## 12. Relation to diagnostics

| Diagnostic | Role in Direction 1 pilot |
|------------|---------------------------|
| 2A/3C | Motivation only (binding gap) — already shown |
| 4A | Not re-run; explicit ceiling cited if needed |
| **5B** | Reference for injection at scale (T=0.7, n=10, n=150); pilot inject-* is **greedy n=1** on hl50 |
| 5A | Not in pilot table |

Do **not** duplicate diagnostic factorial work. This pilot is **beam + format ablation + injection baselines on the same hl50 grid**.

---

## 13. Thesis paragraph (draft)

> On a stratified subset of 50 census-validated Spanish verbs (25 high- and 25 low-frequency), we compared form injection in the prompt to decode-time constrained beam search under matched plain-text and JSON generation scaffolds. All conditions used one greedy or deterministic sample per morphological cell and were evaluated with the production pipeline (expected-form match, LanguageTool grammar, length, diversity). Hard constrained decoding matched prompt injection on expected-form match while [improving / not improving — fill after runs] grammar, demonstrating that [decode-time enforcement / plain-text scaffold — fill after runs] is the preferred intervention path for the full n=150 evaluation.

---

## 14. Open items before first run

1. ~~Implement plain prompt builder + inject-plain generator.~~ Done.
2. ~~Implement constrained_hf (start from `spanish_cd_escribireis_spike.py`).~~ Done.
3. ~~Create method YAMLs for all six core arms.~~ Done.
4. ~~Confirm greedy inject: `do_sample=False` or `temperature=0` in `BaselineHFGenerator`.~~ Done.
5. Build benchmark: `research/benchmarks/spanish_direction_hl50.yaml` (committed after `build_diagnostic_5_benchmark`).
6. Load benchmark + method presets, then run (see §9).

### Run commands (local GPU)

```bash
python3 -m research.benchmarks.loader research/benchmarks/spanish_direction_hl50.yaml

python3 -m research.run_experiment \
  --benchmark spanish_direction_hl50 \
  --method direction_1a_hard_plain_hl50 \
  --live --resume
```

Cluster — **parallel (recommended, 3 GPUs):**

```bash
sbatch research/scripts/cluster/direction_1_inject_hl50_gpu.sh   # inject-json, inject-plain
sbatch research/scripts/cluster/direction_1_hard_hl50_gpu.sh     # 1A-hard-plain, 1A-hard-json
sbatch research/scripts/cluster/direction_1_soft_hl50_gpu.sh     # 1B-soft-plain, 1B-soft-json
```

Wall time ≈ **slowest job** (~3–5 h hard, ~1–2 h inject, ~2–4 h soft), not the sum. Each uses `--resume`.

Cluster — sequential fallback (1 GPU): `sbatch research/scripts/cluster/direction_1_all_hl50_gpu.sh`

---

## 15. Quick reference — registry IDs

```
direction_1_inject_json
direction_1_inject_plain
direction_1a_hard_plain
direction_1a_hard_json
direction_1b_soft_plain
direction_1b_soft_json
```
