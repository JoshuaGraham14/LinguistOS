# Handoff: Diagnostic 5 — Form injection via evaluation pipeline (5A / 5B / 5C)

Copy this into a new chat to run or resume the Diagnostic 5 series.

---

## Where you are

| Diagnostic | Status | What it tests |
|---|---|---|
| **5A** | Ready | Pipeline baseline `build_prompt`, no gold form |
| **5B** | Ready | Same + Exp-9 form injection line |
| **5C** | Ready | `build_prompt_explicit` + form injection |

All three arms use:

- Benchmark: `spanish_diagnostic_n150` (150 verbs × 31 cells = 4,650 constraint sets)
- Model: Qwen3-1.7B
- Decoding: T=0.7, 10 batched candidates per cell, `short` length, no CEFR
- Runner: `python -m research.run_experiment --live`
- Scoring: full pipeline — expected-form, LanguageTool grammar, length-in-band, diversity group metrics
- Headline: **sentence-level** pass rates (Exp 9 style), not pass@k

**5A is the framework twin of Diagnostic 3D** (same generation idea), but results are DB-backed with the fuller scorecard. Do not reuse the old 3D spike JSON as the 5A baseline.

**Registry:** `research/diagnostics/registry.yaml`

---

## Build / load the benchmark

```bash
# Regenerate YAML from the census manifest (already committed at full n=150)
python3 -m research.scripts.build_diagnostic_5_benchmark

# Smoke subset (2 verbs = 62 cells)
python3 -m research.scripts.build_diagnostic_5_benchmark \
  --limit-verbs 2 \
  --name spanish_diagnostic_n150_smoke \
  --output research/benchmarks/spanish_diagnostic_n150_smoke.yaml

# Load into the research DB (idempotent by name)
python3 -m research.benchmarks.loader research/benchmarks/spanish_diagnostic_n150.yaml
```

---

## How to run (local / cluster)

```bash
python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5a_hf_qwen3_17b_n10 \
  --live --resume \
  --skip-experiment-group-metrics

python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5b_hf_qwen3_17b_n10 \
  --live --resume \
  --skip-experiment-group-metrics

python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5c_hf_qwen3_17b_n10 \
  --live --resume \
  --skip-experiment-group-metrics
```

Or resume a specific experiment id:

```bash
python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5a_hf_qwen3_17b_n10 \
  --live --resume-experiment-id 42 \
  --skip-experiment-group-metrics
```

Cluster:

```bash
sbatch research/scripts/cluster/diagnostic_5a_n150_gpu.sh
sbatch research/scripts/cluster/diagnostic_5b_n150_gpu.sh
sbatch research/scripts/cluster/diagnostic_5c_n150_gpu.sh
```

Each arm is ~46,500 sentences. Prefer `--resume` after any interruption.

Cluster scripts set `RESEARCH_DB` to an isolated file under `research/runs/` (merge into `research.db` after all arms finish). They also set `LTP_PATH` on the project volume so LanguageTool does not hit home-directory disk quota.

**Grammar rescore** (if the original run has grammar 0% due to LT quota failure):

```bash
source research/scripts/cluster/research_cache_env.sh
export RESEARCH_DB=research/runs/diagnostic_5a.db
python3 -m research.scripts.rescore_diagnostic_5_grammar --arm 5a
# Or all arms: sbatch research/scripts/cluster/rescore_diagnostic_5_grammar.sh
```

Re-merge per-arm DBs after rescore: `bash research/scripts/cluster/diagnostic_5_merge.sh`.

**Runtime:** generation is ~10 h on A30; post-generation scoring was ~10 h on the first n=150 run because experiment-wide Self-BLEU was O(n²) over 46,500 sentences. Use `--skip-experiment-group-metrics` on large benchmarks (per-cell metrics + roll-ups only). Experiment Self-BLEU is also subsampled when enabled (`SELF_BLEU_EXPERIMENT_CAP`, default 500).

Smoke first with the small benchmark + any of the Diag 5 methods (or regenerate method YAML pointing at smoke if needed by using `--benchmark spanish_diagnostic_n150_smoke` after loading that YAML).

---

## Method map

| Arm | Method YAML name | Generator |
|-----|------------------|-----------|
| 5A | `diagnostic_5a_hf_qwen3_17b_n10` | `baseline_hf` |
| 5B | `diagnostic_5b_hf_qwen3_17b_n10` | `baseline_hf_form_injected` |
| 5C | `diagnostic_5c_hf_qwen3_17b_n10` | `baseline_hf_form_injected_explicit` |

Experiment names in DB look like:

`spanish_diagnostic_n150__diagnostic_5a_hf_qwen3_17b_n10__live`

---

## How to read results (sentence-level)

After a completed experiment, pull roll-ups from `experiment_metrics` / `sentence_evaluations` the same way as Exp 9:

- Per-sentence: `expected_form_match`, `grammar_languagetool`, `length_in_band`
- Group/diversity: uniqueness, Self-BLEU, template rate, distinct-n, length CV

Lead with **fraction of sentences that pass**, not “fraction of cells with ≥1 of 10.”

---

## Do not

- Treat Diagnostic 3D spike JSON as the 5A control for grammar/diversity.
- Cite pass@1 / pass@10 as the Diagnostic 5 headline.
- Leak gold forms in the 5A baseline prompt (participle included).
- Skip `--resume` on long cluster jobs.
