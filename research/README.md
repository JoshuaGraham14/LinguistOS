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
| `app.py` | Streamlit stub (not wired to the pipeline) |

## Setup

From the repo root (or `research/`):

```bash
cd research
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For live OpenAI runs, copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

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

## Tests

```bash
python -m pytest tests/ -q
```

## Adding components

- **Benchmark:** YAML under `benchmarks/`, loaded on first use.
- **Method:** YAML under `methods/` (`baseline_gpt`, `individual_gpt`, etc.).
- **Sentence evaluator:** class under `evaluation/sentence/`, register in `evaluation/sentence/__init__.py` (`DEFAULT_EVALUATORS`).
- **Distribution metric:** class under `evaluation/distribution/`, register in `evaluation/distribution/__init__.py` (`DEFAULT_GROUP_METRICS`).
