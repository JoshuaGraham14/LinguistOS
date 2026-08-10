# Method presets

Named generation settings for `run_experiment --method <name>`. Lookup uses the
YAML **`name`** field, not the file path.

## Layout

```
methods/
  baseline/               # Batched GPT presets
    default.yaml          # name: baseline_default
    short.yaml
    medium.yaml
    long.yaml
    long_explicit.yaml
    random.yaml
  individual/             # One-call-per-sample GPT presets
    default.yaml
    ...
```

Each file is self-contained (no inheritance). Open any preset to see the full config.

## sentence_length

Every preset sets `sentence_length` in `config`:

| Value | Meaning |
| --- | --- |
| `short` | 2–5 words |
| `short_expanded` | 4–8 words (Welsh periphrastic teacher regen) |
| `by_construction` | Welsh: peri → `short_expanded`, else `short` (LoRA train/eval match) |
| `medium` | 5–9 words |
| `long` | 10–16 words |
| `random` | Draw short/medium/long per sample at run time |

For `random`, each sentence stores `resolved_sentence_length` in `generation_meta`;
`length_in_band` is evaluated against that draw.
