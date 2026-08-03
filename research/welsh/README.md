# Welsh transfer experiments

Transfer study for morphologically constrained sentence generation on Welsh
(Qwen edge models), parallel to the Spanish pipeline.

## Slot grid (frozen)

Future is **periphrastic only** — Eurfa lists almost no full synthetic future
paradigms for lexical verbs (spoken 3sg at best). Person/number on periphrastic
cells is marked on the auxiliary; the target lemma contributes the verbnoun
(soft-mutated after *gwneud* past).

| Tense | Synthetic (Eurfa lexical) | Periphrastic (aux × 6 + verbnoun) |
|---|---|---|
| Present | `pres` × 6 persons | *bod* present × 6 + *yn* + VN |
| Past | `past` × 6 persons | *gwneud* past × 6 + soft-mutated VN |
| Imperfect | `imperf` × 6 persons | *bod* imperfect (*roedd…*) × 6 + *yn* + VN |
| Future | — | *bod* future (*bydd…*) × 6 + *yn* + VN |

Persons: `1s 2s 3s 1p 2p 3p` on every filled cell (42 cells / verb:
3×6 synthetic + 4×6 periphrastic). Prefer Eurfa `notes=spoken` (accept
`short` / unmarked as alts).

Auxiliary paradigms are fully present in Eurfa for the forms we need
(*bod* present / future / imperfect; *gwneud* past).

## Data sources

| File | Role | License / citation |
|---|---|---|
| `data/eurfa_cylist20131111.csv` | Gold synthetic forms + verbnouns + aux | Eurfa (GPL/AGPL), Kevin Donnelly |
| `data/corcencc_lemmas.xlsx` | Lemma frequency ranks | Yr Amliadur / CorCenCC (CC-BY-SA), Knight et al. 2020 |

**Frequency / Zipf:** Spanish uses `wordfreq` Zipf; Welsh is not in wordfreq, so
Zipf is derived from CorCenCC `per_million` on the same scale as the thesis:

`Zipf(w) = log10(f(w) · 10⁹)` with `f = per_million / 10⁶`
→ `Zipf = log10(per_million) + 3`.

Tiers are equal-count Zipf terciles over the Eurfa∩CorCenCC pool (parallel to
Spanish census terciles). Continuous `zipf` is kept on the manifest for analysis.

**Target-verb coverage** (sampling filter):

- verbnoun (`infin`)
- synthetic present / past / imperfect × all 6 persons

Lexical `fut` rows are **not** required (synthetic future is out of grid).

## Verb sampling

```bash
python -m research.welsh.scripts.select_welsh_verbs
python -m research.welsh.scripts.select_welsh_verbs --per-tier 50 --seed 42
```

Writes:

- `manifests/manifest_welsh_n150.csv` — stratified sample (high/mid/low)
- `manifests/welsh_coverage_pool.csv` — all lemmas passing coverage ∩ CorCenCC
- `manifests/welsh_tier_cutoffs.json` — frozen frequency tercile cutoffs
- `manifests/welsh_cases_n150.csv` — gold case table (150 × 42 = 6300 rows)

```bash
python -m research.welsh.scripts.build_welsh_cases
```

Each case row mirrors the Spanish experiment-verb pattern (`lang`, `zipf`,
`tier`, `cell_id`, `gold` / `gold_alts`) with Welsh-specific fields:
`construction`, `aux_gold`, `particle`, `requires_soft_mutation`,
`match_forms`. Soft mutation for periphrastic past is applied by
`research/welsh/mutation.py`.

Auxiliaries used in periphrastic templates (`bod`, `gwneud`) are excluded from
the target-verb pool.

**QA filters (sampling):** a blocklist drops sensitive/awkward lemmas and verbs
that are weak Welsh-morphology probes (transparent English loans/calques such
as *tanberfformio*, *samplo*; ultra-niche literary items such as *englynu*).
CorCenCC hapaxes (`raw < 2`) are also dropped so low-tier items are at least
attested twice.
