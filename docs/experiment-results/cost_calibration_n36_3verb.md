# Controlled computational-cost calibration (July 2026)

> **Status:** final controlled timing run complete — 45/45 measurements, no errors  
> **Benchmark:** `spanish_cost_cal_n36_3verb`  
> **Grid:** `caminar` (high frequency), `elogiar` (mid), `amonestar` (low); 31 paradigm cells each = **93 cells**  
> **Hardware:** one A30 GPU (`dipper`, GPU 0), one Slurm allocation  
> **Protocol:** all 15 arms run sequentially; three repeats; fixed `HF_BATCH_SIZE=4`; one untimed four-cell warm-up per arm; generation only (`--no-eval --no-metrics`)  
> **Reported uncertainty:** mean ± sample standard deviation over three repeats  
> **Raw data:** local `research/runs/cost_cal_sequential/repeat_{1,2,3}/*.json`; cluster `/vol/bitbucket/jjg25/LinguistOS/research/runs/cost_cal_sequential/`

## 1. Measurement definitions

| Metric | Definition |
|---|---|
| Latency | Total timed `generate_many` wall time ÷ 93 stored sentences. Model loading and the warm-up batch are excluded. |
| Relative cost | Mean latency ÷ Base 1.7B vanilla mean latency (122.66 ms/sentence). |
| Throughput | Sentences per second = 93 ÷ timed generation wall time. |
| GPU-seconds / arm | Timed generation wall time for the full 93-cell arm (mean over 3 repeats). Same as measured GPU compute time under exclusive allocation. |
| Energy estimate | `GPU-seconds × 165 W` (NVIDIA A30 datasheet TDP), reported in Wh per 93-cell arm. **Upper-bound / board-TDP estimate**, not measured board power. |
| Prompt tokens | Non-padding chat-template tokens presented to the model, averaged over 93 cells. |
| Generated tokens | Model-tokenizer count of stored sentence text, averaged over 93 cells. |
| Decode-work proxy | `num_beams × mean generated tokens`; explanatory proxy, not GPU time. |
| Calls | One logical inference request per cell; 24 underlying batched `model.generate` calls per run (`ceil(93/4)`). |

This is a **controlled cost comparison**, not optimized production throughput. Fixing batch size at four isolates method/model effects from different batching choices.

## 2. Full controlled cost table

| Arm | Inference | Beams | Latency, ms/sent ↓ | Rel. | Throughput, sent/s ↑ | GPU-s / arm ↓ | Energy, Wh / arm ↓ | Prompt tok | Gen tok | Decode work |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `base17_vanilla` | Vanilla | 1 | **122.66 ± 0.30** | **1.00×** | **8.153** | **11.41 ± 0.03** | **0.523 ± 0.001** | 244.0 | 8.42 | 8.4 |
| `base17_inject` | Inject | 1 | **116.83 ± 0.31** | **0.95×** | **8.560** | **10.86 ± 0.03** | **0.498 ± 0.001** | 288.5 | 8.44 | 8.4 |
| `base17_soft4` | Soft | 4 | 377.09 ± 2.30 | 3.07× | 2.652 | 35.07 ± 0.21 | 1.607 ± 0.010 | 244.0 | 13.61 | 54.5 |
| `base17_soft8` | Soft | 8 | 689.41 ± 1.69 | 5.62× | 1.451 | 64.11 ± 0.16 | 2.939 ± 0.007 | 244.0 | 22.33 | 178.7 |
| `base17_soft_inject` | Soft+inject | 4 | 604.13 ± 3.50 | 4.93× | 1.655 | 56.18 ± 0.32 | 2.575 ± 0.015 | 288.5 | 22.45 | 89.8 |
| `base17_hard` | Hard | 4 | 1525.00 ± 4.63 | 12.43× | 0.656 | 141.82 ± 0.43 | 6.500 ± 0.020 | 244.0 | **60.91** | 243.7 |
| `loraA_vanilla` | Vanilla | 1 | 193.12 ± 3.35 | 1.57× | 5.179 | 17.96 ± 0.31 | 0.823 ± 0.014 | 244.0 | 8.40 | 8.4 |
| `loraA_inject` | Inject | 1 | 210.10 ± 0.38 | 1.71× | 4.760 | 19.54 ± 0.04 | 0.896 ± 0.002 | 288.5 | 8.58 | 8.6 |
| `loraA_soft8` | Soft | 8 | 1411.26 ± 16.13 | 11.51× | 0.709 | 131.25 ± 1.50 | 6.016 ± 0.069 | 244.0 | 33.57 | 268.6 |
| `loraB_vanilla` | Vanilla | 1 | 198.34 ± 2.15 | 1.62× | 5.042 | 18.45 ± 0.20 | 0.845 ± 0.009 | 244.0 | 8.53 | 8.5 |
| `loraB_inject` | Inject | 1 | 210.75 ± 2.69 | 1.72× | 4.745 | 19.60 ± 0.25 | 0.898 ± 0.011 | 288.5 | 8.57 | 8.6 |
| `loraB_soft8` | Soft | 8 | 1475.73 ± 7.95 | 12.03× | 0.678 | 137.24 ± 0.74 | 6.290 ± 0.034 | 244.0 | 33.85 | 270.8 |
| `base4_vanilla` | Vanilla | 1 | 185.04 ± 1.39 | 1.51× | 5.404 | 17.21 ± 0.13 | 0.789 ± 0.006 | 244.0 | 10.37 | 10.4 |
| `base4_soft8` | Soft | 8 | 459.45 ± 0.18 | 3.75× | 2.177 | 42.73 ± 0.02 | 1.958 ± 0.001 | 244.0 | 8.03 | 64.3 |
| `base4_hard` | Hard | 4 | 1833.10 ± 7.63 | 14.95× | 0.546 | 170.48 ± 0.71 | 7.814 ± 0.033 | 244.0 | **79.10** | 316.4 |

Energy = timed GPU-seconds × 165 W A30 TDP ÷ 3600. Treat as an **upper-bound estimate**, not measured joules.

Repeat variability is low: latency coefficient of variation is **0.04–1.73%** across all arms. This supports using the three-repeat means as stable controlled estimates.

## 3. LoRA OOD: quality and cost together

Quality is from the full 36-verb OOD evaluation; cost is from the controlled 93-cell calibration.

| Adapter / inference | Form ↑ | Naturalness ↑ | Correct main verb ↑ | Absent ↓ | Latency, ms/sent ↓ | Cost vs Base-vanilla |
|---|---:|---:|---:|---:|---:|---:|
| **Base 1.7B — Inject** | 94.2% | 3.94 | 75.7% | 3.3% | **116.83 ± 0.31** | **0.95×** |
| **Base 1.7B — Vanilla** | 22.0% | **4.52** | 21.5% | 59.2% | 122.66 ± 0.30 | 1.00× |
| **Base 1.7B — Soft B8** | 62.2% | 3.79 | 46.1% | 22.8% | 689.41 ± 1.69 | 5.62× |
| **LoRA-A — Inject** | **98.3%** | 4.51 | **96.1%** | 1.5% | 210.10 ± 0.38 | 1.71× |
| **LoRA-A — Vanilla** | 78.3% | **4.52** | 77.0% | 13.4% | 193.12 ± 3.35 | 1.57× |
| **LoRA-A — Soft B8** | 96.6% | 3.57 | 71.6% | 1.7% | 1411.26 ± 16.13 | 11.51× |
| **LoRA-B — Inject** | 93.8% | 4.44 | 92.5% | 2.8% | 210.75 ± 2.69 | 1.72× |
| **LoRA-B — Vanilla** | 86.3% | 4.45 | 85.8% | 6.3% | 198.34 ± 2.15 | 1.62× |
| **LoRA-B — Soft B8** | **98.5%** | 3.76 | 84.4% | **0.6%** | 1475.73 ± 7.95 | 12.03× |

### LoRA interpretation

- **If the gold surface form is available at inference**, Base 1.7B + Inject is the strongest low-cost baseline: 94.2% Form at essentially vanilla latency. LoRA-A + Inject adds 4.1 percentage points Form and substantially improves correct-main-verb use, but costs about **1.80× Base-Inject latency**.
- **If the gold form is unavailable**, LoRA-B + Vanilla is the clearest efficiency result: Form rises from 22.0% to 86.3% while latency rises from 122.66 to 198.34 ms (**1.62×**).
- Soft B8 is expensive with LoRA. Relative to the matching LoRA vanilla arm, it costs **7.31×** (LoRA-A) or **7.44×** (LoRA-B), produces about four times as many output tokens, and lowers naturalness.
- LoRA-B + Soft B8 achieves the highest Form score (98.5%), but its extra 12.2 points over LoRA-B + Vanilla require about **7.44×** latency and reduce naturalness from 4.45 to 3.76.

## 4. Direction 1.2: quality and cost together

Quality is from the full n150 evaluation; cost is from the controlled 93-cell calibration.

| Arm | Model | Form ↑ | LT ↑ | G ↑ | N ↑ | S ↑ | Latency, ms/sent ↓ | Relative cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Vanilla | 1.7B | 19.7% | 97.6% | 4.58 | 4.31 | 4.56 | **122.66 ± 0.30** | **1.00×** |
| Soft B4 | 1.7B | 53.8% | 94.5% | 4.36 | 3.78 | 4.13 | 377.09 ± 2.30 | 3.07× |
| Soft B8 | 1.7B | 60.1% | 94.7% | 4.25 | 3.64 | 4.01 | 689.41 ± 1.69 | 5.62× |
| Inject | 1.7B | 92.0% | 96.3% | 4.40 | 3.74 | 4.17 | **116.83 ± 0.31** | **0.95×** |
| Soft + Inject B4 | 1.7B | **99.8%** | 95.2% | 4.13 | 3.35 | 3.80 | 604.13 ± 3.50 | 4.93× |
| Hard B4 | 1.7B | 88.6% | 80.7% | 1.23 | 1.07 | 1.10 | 1525.00 ± 4.63 | 12.43× |
| Vanilla | 4B | 59.8% | 99.3% | **4.78** | **4.45** | **4.67** | 185.04 ± 1.39 | 1.51× |
| Soft B8 | 4B | 93.1% | **99.6%** | **4.78** | 4.24 | 4.50 | 459.45 ± 0.18 | 3.75× |
| Hard B4 | 4B | 84.7% | 82.9% | 2.78 | 2.45 | 2.64 | 1833.10 ± 7.63 | 14.95× |

### Direction 1.2 interpretation

- **Injection dominates decode-only control when the gold form is available:** 92.0% Form at effectively vanilla cost, versus Soft B8's 60.1% at 5.62× cost.
- Increasing soft beams from four to eight improves Form by 6.3 points (53.8% → 60.1%) but increases latency by **83%** (377 → 689 ms) and further lowers naturalness.
- Soft + Inject achieves near-perfect Form (99.8%), but adds roughly **5.17× latency over Inject alone** and reduces G/N/S. Its value is therefore narrowly constraint-satisfaction focused.
- Hard decoding is inefficient and low quality: it is 12.43–14.95× Base-vanilla latency, produces 61–79 tokens despite the short target, and severely damages grammar/naturalness.
- **Model scaling can beat complex decoding:** Base 4B Vanilla obtains almost identical Form to 1.7B Soft B8 (59.8% vs 60.1%) at only **27% of its latency** (185 vs 689 ms), while scoring much better on LT/G/N/S.
- Base 4B Soft B8 reaches 93.1% Form and strong quality, but 1.7B Inject reaches 92.0% Form at about **one quarter of the latency** when form injection is permitted.

## 5. Prompt and call cost

- Non-injected prompts average **243.97 tokens**.
- Injected prompts average **288.48 tokens**: an increase of **44.51 tokens (18.2%)**.
- Every method uses one logical inference request per cell.
- With controlled batch size four, every 93-cell arm uses **24 underlying `model.generate` calls** per repeat.
- Injection's additional prompt tokens had negligible measured latency on the unadapted 1.7B model (116.83 vs 122.66 ms); this small reversal should be interpreted as equivalent performance, not an injection speed-up.

## 6. LoRA one-off training cost

| Adapter | Training runtime | A30 GPU-hours |
|---|---:|---:|
| LoRA-A (form-given) | 2223 s | **0.62 h** |
| LoRA-B (no-inject) | 2153 s | **0.60 h** |

This cost is paid once. Inference overhead recurs for every sentence, so training cost should be presented separately and amortised over deployment volume.

## 7. Reliability and limitations

### Strengths

- All arms used the same GPU, node, cells, batch size and software environment.
- Arms ran sequentially, eliminating concurrent-GPU contention.
- Model loading and a four-cell warm-up were excluded from timing.
- Arm order was rotated across repeats to reduce order/thermal bias.
- All 45 runs completed with no errors.
- Repeat variability is very low (maximum latency CV 1.73%).

### Limitations

- Three verbs are a stratified approximation, not the full n36/n150 datasets.
- Timing represents controlled batch size four, not each method's maximum optimized throughput.
- Energy is estimated as timed GPU-seconds × A30 TDP (165 W), not measured with a power meter; treat Wh figures as upper-bound estimates.
- Generated output length is part of observed cost. This is appropriate for end-to-end inference, but means hard decoding's high latency partly reflects its pathological long outputs.
- Results are specific to this A30 hardware/software configuration.

## 8. Recommended dissertation claim

The experiments support a Pareto-style conclusion rather than a single universal winner:

1. **Form injection** provides the best morphology-control gain per unit inference cost when the gold form is available.
2. **LoRA-B + Vanilla** provides the best no-injection trade-off, greatly improving OOD morphology for modest recurring inference overhead plus a small one-off training cost.
3. **Soft beam decoding** can improve form satisfaction but exhibits sharply diminishing returns in latency and naturalness.
4. **Hard presence constraints** are dominated: high cost, long malformed outputs and poor quality.
5. **Scaling to 4B with vanilla decoding** can be substantially more efficient than complex decoding on 1.7B for comparable morphology quality.
