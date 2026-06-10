# Research prototyping — ad-hoc live GPT spikes

Throw-away scripts for scoping experiments **before** promoting cases to
benchmarks, the DB pipeline, or evaluators. Not part of `run_experiment.py`.

## Scripts

| Script | Purpose | Results |
|--------|---------|---------|
| [`e0_hebrew_spike.py`](e0_hebrew_spike.py) | Hebrew E0 morphology gate (10 cases) | `docs/eval_hebrew_e0_spike_{short,long}_results.json` |
| [`niche_constraints_spike.py`](niche_constraints_spike.py) | Spanish + Hebrew niche constraint probe | `docs/eval_niche_constraints_spike_results.json` |

## Run

From repo root (requires `research/.env` with `OPENAI_API_KEY`):

```bash
python3 research/prototyping/e0_hebrew_spike.py --length short
python3 research/prototyping/niche_constraints_spike.py --samples 3
```

## Notes

- Imports `research.generation.baseline_gpt` and language profiles under `research/languages/`.
- Scoring is inline in each script (EF strict, phrase match) — not the registered evaluator pipeline.
- Findings are written to `docs/eval_*.md` by hand after each spike.
