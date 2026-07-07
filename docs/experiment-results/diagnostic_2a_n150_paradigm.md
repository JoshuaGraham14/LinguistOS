# Diagnostic 2A — Spanish full-paradigm results (n=150)

**Series:** Diagnostic 2 — Spanish paradigm isolation  
**Results file:** `docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json`  
**Scoring version:** `label_aware_v3`

**Strict** = slot-level accuracy (correct form in the correct person slot, with pronoun prefixes stripped).  
**Perfect** = call-level rate (the entire six-form table is correct).

150 verbs — 50 per frequency tier (high / mid / low), regularity pooled.  
900 full-paradigm calls per model (150 verbs × 6 tenses).

See also: [Diagnostic 2B results](diagnostic_2b_n150_single_slot.md) (single-form production).

---

## 1. By model size

| Model | Strict | Perfect | Calls |
|-------|--------|---------|-------|
| Qwen3 0.6B | 20.4% | 8.1% | 900 |
| Qwen3 1.7B | 69.1% | 52.9% | 900 |
| Qwen3 4B | 80.8% | 70.6% | 900 |

---

## 2. By tense

*Strict is slot-level; perfect is call-level. Participle has only one form, so strict and perfect are identical.*

### Qwen3 0.6B

| Tense | Strict | Perfect |
|-------|--------|---------|
| present | 43.2% | 2.7% |
| preterite | 29.0% | 2.7% |
| imperfect | 11.2% | 3.3% |
| future | 15.3% | 1.3% |
| conditional | 0.0% | 0.0% |
| participle | 38.7% | 38.7% |

### Qwen3 1.7B

| Tense | Strict | Perfect |
|-------|--------|---------|
| present | 65.4% | 38.0% |
| preterite | 54.8% | 20.7% |
| imperfect | 72.2% | 62.0% |
| future | 78.6% | 64.7% |
| conditional | 72.3% | 50.0% |
| participle | 82.0% | 82.0% |

### Qwen3 4B

| Tense | Strict | Perfect |
|-------|--------|---------|
| present | 81.1% | 53.3% |
| preterite | 71.3% | 40.0% |
| imperfect | 88.2% | 84.0% |
| future | 84.7% | 80.7% |
| conditional | 76.9% | 74.7% |
| participle | 90.7% | 90.7% |

---

## 3. By person form (strict only; indicative)

Perfect paradigm is a whole-table metric and is not broken down by person slot.  
Based on 750 indicative calls per model (5 tenses × 150 verbs).

| Person | 0.6B | 1.7B | 4B |
|--------|------|------|-----|
| yo | 19.1% | 67.7% | 76.5% |
| tú | 20.1% | 65.2% | 79.2% |
| él | 26.7% | 72.3% | 81.9% |
| nosotros | 22.3% | 70.9% | 82.8% |
| vosotros | 7.1% | 61.7% | 79.9% |
| ellos | 23.3% | 74.1% | 82.4% |

---

## 4. By frequency tier

50 verbs per tier. 300 calls per model per tier (50 verbs × 6 tenses).

### Qwen3 0.6B

| Tier | Strict | Perfect |
|------|--------|---------|
| high | 24.5% | 8.0% |
| mid | 19.2% | 9.0% |
| low | 17.5% | 7.3% |

### Qwen3 1.7B

| Tier | Strict | Perfect |
|------|--------|---------|
| high | 75.5% | 59.0% |
| mid | 65.0% | 48.3% |
| low | 66.8% | 51.3% |

### Qwen3 4B

| Tier | Strict | Perfect |
|------|--------|---------|
| high | 87.9% | 77.3% |
| mid | 76.5% | 66.7% |
| low | 77.9% | 67.7% |
