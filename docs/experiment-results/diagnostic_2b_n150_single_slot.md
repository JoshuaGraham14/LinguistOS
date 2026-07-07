# Diagnostic 2B — Spanish single-slot results (n=150)

**Series:** Diagnostic 2 — Spanish paradigm isolation  
**Results file:** `docs/spike-results/eval_diagnostic_2b_n150_single_slot_qwen_results.json`

**Pass rate** = the model's first extracted token matches the gold form (strict, like Diagnostic 1A).

150 verbs — 50 per frequency tier (high / mid / low), regularity pooled.  
4,650 single-form calls per model (150 verbs × 5 tenses × 6 persons + 150 participles).

See also: [Diagnostic 2A results](diagnostic_2a_n150_paradigm.md) (full-paradigm production).

---

## 1. By model size

| Model | Pass rate | Correct / Total |
|-------|-----------|-----------------|
| Qwen3 0.6B | 1.5% | 68 / 4,650 |
| Qwen3 1.7B | 44.7% | 2,079 / 4,650 |
| Qwen3 4B | 55.5% | 2,579 / 4,650 |

---

## 2. By tense

### Qwen3 0.6B

| Tense | Pass rate | Calls |
|-------|-----------|-------|
| present | 3.2% | 900 |
| preterite | 2.4% | 900 |
| imperfect | 0.0% | 900 |
| future | 0.2% | 900 |
| conditional | 0.0% | 900 |
| participle | 10.0% | 150 |

### Qwen3 1.7B

| Tense | Pass rate | Calls |
|-------|-----------|-------|
| present | 51.3% | 900 |
| preterite | 41.8% | 900 |
| imperfect | 26.4% | 900 |
| future | 64.7% | 900 |
| conditional | 32.2% | 900 |
| participle | 87.3% | 150 |

### Qwen3 4B

| Tense | Pass rate | Calls |
|-------|-----------|-------|
| present | 60.7% | 900 |
| preterite | 30.6% | 900 |
| imperfect | 55.8% | 900 |
| future | 64.4% | 900 |
| conditional | 59.9% | 900 |
| participle | 91.3% | 150 |

---

## 3. By person (indicative only)

| Person | 0.6B | 1.7B | 4B |
|--------|------|------|-----|
| yo | 0.4% | 45.1% | 70.8% |
| tú | 0.1% | 26.3% | 56.3% |
| él | 3.3% | 60.8% | 72.4% |
| nosotros | 1.3% | 49.1% | 45.2% |
| vosotros | 0.0% | 19.5% | 9.6% |
| ellos | 1.9% | 59.1% | 71.3% |

---

## 4. By frequency tier

| Tier | 0.6B | 1.7B | 4B | Calls per model |
|------|------|------|-----|-----------------|
| high | 2.1% | 45.7% | 62.2% | 1,550 |
| mid | 1.7% | 43.2% | 54.3% | 1,550 |
| low | 0.6% | 45.2% | 49.9% | 1,550 |

---

## Note: 2A vs 2B

On the larger models, **full-paradigm production (2A) scores higher** than single-slot (2B) for most tenses. The model often produces better forms when asked for a whole table than when asked for one form in isolation.
