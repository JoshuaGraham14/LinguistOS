# Research prototyping — ad-hoc live GPT spikes

Throw-away scripts for scoping experiments **before** promoting cases to
benchmarks, the DB pipeline, or evaluators. Not part of `run_experiment.py`.

## Scripts

| Script | Purpose | Results |
|--------|---------|---------|
| [`e0_hebrew_spike.py`](e0_hebrew_spike.py) | Hebrew E0 morphology gate (10 cases) | `docs/eval_hebrew_e0_spike_{short,long}_results.json` |
| [`niche_constraints_spike.py`](niche_constraints_spike.py) | Spanish + Hebrew niche constraint probe | `docs/eval_niche_constraints_spike_results.json` |
| [`english_rare_verbs_qwen_spike.py`](english_rare_verbs_qwen_spike.py) | English rare-verb recognition + conjugation on Qwen 0.5B / 1.7B / 4B | `docs/eval_english_rare_verbs_qwen_spike_results.json` |
| [`spanish_verbs_qwen_spike.py`](spanish_verbs_qwen_spike.py) | Spanish common + rare verb recognition + conjugation (same Qwen ladder) | `docs/eval_spanish_verbs_qwen_spike_results.json` |
| [`spanish_paradigm_qwen_spike.py`](spanish_paradigm_qwen_spike.py) | Full indicative paradigms (5 verbs × 5 tenses, minimal prompt) | `docs/eval_spanish_paradigm_qwen_spike_results.json` |

## Run

From repo root (requires `research/.env` with `OPENAI_API_KEY`):

```bash
python3 research/prototyping/e0_hebrew_spike.py --length short
python3 research/prototyping/niche_constraints_spike.py --samples 3
python3 research/prototyping/english_rare_verbs_qwen_spike.py
python3 research/prototyping/english_rare_verbs_qwen_spike.py --models qwen05b --dry-run
python3 research/prototyping/spanish_verbs_qwen_spike.py
python3 research/prototyping/spanish_verbs_qwen_spike.py --tasks conjugation
python3 research/prototyping/spanish_paradigm_qwen_spike.py
```

## Notes

- Imports `research.generation.baseline_gpt` and language profiles under `research/languages/`.
- Scoring is inline in each script (EF strict, phrase match) — not the registered evaluator pipeline.
- Findings are written to `docs/eval_*.md` by hand after each spike.
