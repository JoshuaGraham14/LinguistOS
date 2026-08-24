# Experimental framework

CLI-driven pipeline for constrained sentence-generation experiments: configure a **benchmark** (what to test) and a **method** (how to generate), run generation, score every sentence with a shared metric suite, and store the run in SQLite for analysis.

This is the research artefact used for the technical-method and transfer experiments. Diagnostics in the report largely use their own scripts under `diagnostics/` / `prototyping/`, not this runner. Large runs were executed on a GPU cluster via `scripts/cluster/`; the same CLI works locally if a GPU (or CPU) is available.

## Structure

| Path | Role |
|------|------|
| `run_experiment.py` | CLI entry point |
| `pipeline.py` | Generate → evaluate → store metrics |
| `benchmarks/` | YAML benchmarks (constraint grids) |
| `methods/` | YAML method presets (prompt / decode / LoRA arms) |
| `generation/` | Generators (HF, GPT, constrained decode, NeuroLogic, few-shot, …) |
| `evaluation/` | Sentence metrics, roll-ups, optional judges / LanguageTool / Cysill |
| `db/` | SQLAlchemy models for experiment databases |
| `diagnostics/` | Diagnostic figure scripts and assets |
| `welsh/` | Welsh resources (mutation, Eurfa morph bans, transfer helpers) |
| `scripts/` | Training, plotting, audits; `scripts/cluster/` for Slurm jobs |
| `merge_databases.py` | Merge per-job run DBs into one `research.db` |
| `prototyping/` | Early spike scripts (not the main runner) |

## Setup

From the **repository root**:

```bash
python3 -m venv research/.venv
source research/.venv/bin/activate
pip install -r research/requirements.txt
python3 -m spacy download es_core_news_sm
```

Copy `research/.env.example` to `research/.env` and set keys as needed. LanguageTool needs Java; tests mock it and do not require Java.

## Run an experiment

Always invoke from the repo root so `python -m research.…` resolves:

```bash
# Mock (no model call)
python -m research.run_experiment --benchmark spanish_basic --method baseline_default

# Live generation (HF methods use CUDA if available, else MPS/CPU)
python -m research.run_experiment --benchmark spanish_basic --method baseline_default --live
```

Useful flags: `--no-eval`, `--no-metrics`, `--skip-experiment-group-metrics`, `--resume`.

**Default scoring** covers form match, LanguageTool, length, and clause count. Report-style judge / perplexity scores are opt-in (also how cluster jobs often rescore offline):

```bash
python -m research.run_experiment \
  --benchmark spanish_lora_ood_n36 \
  --method direction_2_lora_vanilla_ood_n36 \
  --live \
  --with-naturalness-judge \
  --with-fluency-perplexity
```

(`--with-naturalness-judge` needs `OPENAI_API_KEY`; `--with-cysill` is the Welsh grammar opt-in.)

**Local GPU / LoRA knobs** (same env vars as cluster scripts):

| Env | Purpose |
|-----|---------|
| `RESEARCH_DB` | Write this run to an isolated SQLite file (default: `research/research.db`) |
| `LORA_ADAPTER_PATH` | Attach a PEFT adapter for LoRA arms |
| `HF_BATCH_SIZE` | Batch size (lower for soft / NeuroLogic if VRAM is tight) |

```bash
export RESEARCH_DB=research/runs/local_ood_vanilla.db
export LORA_ADAPTER_PATH=/path/to/adapter
export HF_BATCH_SIZE=4
python -m research.run_experiment --benchmark spanish_lora_ood_n36 --method direction_2_lora_vanilla_ood_n36 --live
```

Merge isolated run DBs when needed:

```bash
python -m research.merge_databases --target research/research.db research/runs/local_ood_vanilla.db
```

## Tests

```bash
python -m pytest research/tests/ -q
```

## Extending

- **Benchmark:** add YAML under `benchmarks/`
- **Method:** add YAML under `methods/baseline/` (or related); CLI uses the preset `name`
- **Generator:** implement under `generation/` and register in `generation/__init__.py`
- **Evaluator:** add under `evaluation/sentence/` (or distribution metrics) and register in the package `__init__`
