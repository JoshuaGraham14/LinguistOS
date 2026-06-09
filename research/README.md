# Research Mode

CLI-driven pipeline for running generation experiments against benchmarks, scoring outputs, and storing results in a local SQLite database (`research.db`). Use [`explore.ipynb`](explore.ipynb) to inspect and compare runs.

Generation logic is adapted from [`backend/app/api/generate.py`](../backend/app/api/generate.py) but runs standalone (no FastAPI). See [`docs/research_mode_implementation_plan.md`](../docs/research_mode_implementation_plan.md) for the full design.

## Layout

| Path | Purpose |
|------|---------|
| `run_experiment.py` | CLI entry point |
| `pipeline.py` | Orchestration: generate → evaluate → metrics |
| `benchmarks/*.yaml` | Reusable constraint-set groups |
| `methods/*.yaml` | Generation method configs |
| `fixtures/mock_outputs.py` | Canned sentences for mock runs |
| `explore.ipynb` | Analysis over `research.db` |
| `explore_live_spanish_basic.ipynb` | Live method comparison (`spanish_basic`) |
| `explore_live_spanish_challenging.ipynb` | Live method comparison (`spanish_challenging`) |
| `app.py` | Streamlit stub (not wired to the pipeline) |

## Setup

From the repo root (or `research/`):

```bash
cd research
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 -m spacy download es_core_news_sm   # required for verb_morphology evaluator
```

`sacrebleu` is required for the `self_bleu` distribution metric (installed via `requirements.txt`).

`grammar_languagetool` uses a local LanguageTool server (downloaded on first use, ~259MB).
**Java** must be installed (`java -version`). Tests mock LanguageTool and do not need Java.

For live OpenAI runs, copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

To wipe experiment data and recreate an empty schema:

```bash
python3 -c "from research.db.database import reset_db; reset_db()"
```

Then reload benchmarks and method configs (see **Adding components** below) before running experiments.

## Run an experiment

Mock run (no API; uses `fixtures/mock_outputs.py`):

```bash
python -m research.run_experiment --benchmark spanish_basic --method baseline_default
```

Live generation:

```bash
python -m research.run_experiment --benchmark spanish_basic --method baseline_default --live
```

Other flags: `--no-eval` (skip per-sentence scoring), `--no-metrics` (skip group metrics and roll-ups).

### Method comparison (live)

Run both methods on the same benchmark, then inspect diversity metrics in the live notebooks:

```bash
python -m research.run_experiment --benchmark spanish_basic --method baseline_default --live
python -m research.run_experiment --benchmark spanish_basic --method individual_default --live
```

Headline experiment-wide diversity columns: `uniqueness_ratio_experiment`, `self_bleu_experiment`,
`template_rate_experiment`, `distinct_1_experiment`, `distinct_2_experiment`. Baseline (batched GPT)
should score higher on uniqueness/distinct-n and lower on self-BLEU/template-rate than individual.

## Tests

```bash
python -m pytest tests/ -q
```

## Adding components

- **Benchmark:** YAML under `benchmarks/`, loaded on first use.
  Optional `mock_only: true` marks fixture benchmarks (evaluator regression tests);
  `run_experiment --live` rejects these. After schema changes, run `reset_db()` and reload.
  Benchmarks: `spanish_basic` (easy), `spanish_challenging` (live stress-test), `spanish_grammar_probe` (mock fixture).
- **Method:** YAML under `methods/` (`baseline_gpt`, `individual_gpt`, etc.).
- **Sentence evaluator:** class under `evaluation/sentence/`, register in `evaluation/sentence/__init__.py` (`DEFAULT_EVALUATORS`).
- **Distribution metric:** class under `evaluation/distribution/`, register in `evaluation/distribution/__init__.py` (`DEFAULT_GROUP_METRICS`). Diversity metrics: `self_bleu`, `template_rate`, `distinct_1`, `distinct_2` (each with constraint_set + experiment scopes).
- **Language morph config:** YAML under `evaluation/morph_configs/<lang>.yaml` (maps benchmark tense/person/number → UD features for `verb_morphology`). Adding a new language requires no code changes — drop a file and download the parser model.
