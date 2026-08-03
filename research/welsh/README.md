# Welsh transfer experiments

Transfer study for morphologically constrained sentence generation on Welsh
(Qwen edge models), parallel to the Spanish pipeline but with a **4×2** slot
grid: four tenses × (synthetic | periphrastic).

## Slot grid (frozen)

| Tense | Synthetic (Eurfa) | Periphrastic |
|---|---|---|
| Present | `pres` × 6 persons | *bod* + *yn* + verbnoun |
| Future | `fut` (often 3sg only in Eurfa) | *bydda* + *yn* + verbnoun |
| Past | `past` × 6 persons | *gwneud* past + soft-mutated verbnoun |
| Imperfect | `imperf` × 6 persons | *roedd* + *yn* + verbnoun |

Persons: `1s 2s 3s 1p 2p 3p`. Prefer Eurfa `notes=spoken` (accept `short` / unmarked as alts).

## Data sources

| File | Role | License / citation |
|---|---|---|
| `data/eurfa_cylist20131111.csv` | Gold synthetic forms + verbnouns | Eurfa (GPL/AGPL), Kevin Donnelly |
| `data/corcencc_lemmas.xlsx` | Lemma frequency ranks | Yr Amliadur / CorCenCC (CC-BY-SA), Knight et al. 2020 |

**Frequency / Zipf:** Spanish uses `wordfreq` Zipf; Welsh is not in wordfreq, so
Zipf is derived from CorCenCC `per_million` on the same scale as the thesis:

`Zipf(w) = log10(f(w) · 10⁹)` with `f = per_million / 10⁶`
→ `Zipf = log10(per_million) + 3`.

Tiers are equal-count Zipf terciles over the Eurfa∩CorCenCC pool (parallel to
Spanish census terciles). Continuous `zipf` is kept on the manifest for analysis.

**Important Eurfa limitation:** lexical verbs almost never have a full 6-person
synthetic future in the CSV (typically only spoken 3sg). Coverage for sampling
therefore requires:

- verbnoun (`infin`)
- synthetic present / past / imperfect × all 6 persons
- synthetic future with **at least** 3sg (recorded separately in the manifest)

Periphrastic future does not depend on lexical `fut` rows; it uses *bod* future
forms + verbnoun.

## Verb sampling

```bash
python -m research.welsh.scripts.select_welsh_verbs
python -m research.welsh.scripts.select_welsh_verbs --per-tier 50 --seed 42
```

Writes:

- `manifests/manifest_welsh_n150.csv` — stratified sample (high/mid/low)
- `manifests/welsh_coverage_pool.csv` — all lemmas passing coverage ∩ CorCenCC
- `manifests/welsh_tier_cutoffs.json` — frozen frequency tercile cutoffs

Auxiliaries used in periphrastic templates (`bod`, `gwneud`) are excluded from
the target-verb pool.
