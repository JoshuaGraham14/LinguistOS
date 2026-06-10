# Language profile YAML schema

One file per language: `research/languages/{code}.yaml`.

Used by the generation prompt builder and benchmark loader validation.

## Top-level fields

| Field | Required | Purpose |
| --- | --- | --- |
| `code` | yes | ISO-style language code (`es`, `he`, …) |
| `name` | yes | Display name in prompts (`Spanish`, `Hebrew`) |
| `dimensions` | yes | Map of constraint field → allowed values (order = prompt order) |
| `labels` | no | Prompt label override per field (default: titlecased field name) |
| `glosses` | no | Per-field value → display string; missing values use default formatter |
| `required` | no | Constraint fields that every benchmark row must set (default: `tense`, `person`, `number`) |

## Rules

- No prompt prose in language files — data only.
- Adding a language = add `{code}.yaml`; no Python changes.
- Benchmark YAML uses flat constraint keys at the top level (not nested under `constraints:`).
- Reserved benchmark keys (not constraints): `keyword`, `expected_form`, `translation`, `cefr_level`, `target_language`.
