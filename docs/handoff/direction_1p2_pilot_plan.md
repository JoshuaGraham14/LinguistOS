# Handoff: Direction 1.2 pilot — second run with methodological fixes

> **Status:** planned rerun of `spanish_direction_hl50` after the D1.1 pilot
> exposed methodological gaps. Successor to `direction_1_pilot_plan.md` (D1.1).
> Codebase changes live on branch `direction_1.2`.

---

## 1. What changed vs Direction 1.1

D1.1 produced these headline numbers on `spanish_direction_hl50` (Qwen3-1.7B,
1,550 cells, 1 sample/cell):

| Arm | Expected-form match |
|-----|--------------------:|
| inject-plain | **96%** |
| inject-json  | 94.7% |
| hard-plain   | 57% |
| soft-plain   | 44% |
| soft-json    | 56% |
| hard-json    | 44% (partial, 1064/1550) |

**Grammar (LanguageTool)** came back **0% everywhere** — not a scientific
result. Cause: cluster scripts never sourced `research_cache_env.sh`, so
`LTP_PATH` defaulted to `~/.cache/language_tool_python` and hit the home
directory disk quota, exactly the D5 failure. Without grammar we cannot
answer the actual research question ("can decode-time control match injection
on form without corrupting grammar?").

### Headline finding worth keeping (methodological, cite-worthy)

> `force_words_ids` guarantees a subsequence appears **somewhere in the
> surface form**. It does not encode syntactic role, morphological
> agreement, or clause position. Beam+`force_words_ids` therefore satisfies
> the constraint by *inserting* the token, then keeps generating
> — producing outputs like `"Com como un comes bebes bebe bebe..."` where
> the constraint has "fired" but the sentence has collapsed.

This is a real, citable observation about the mismatch between a **presence
primitive** and a **role/agreement requirement**. D1.2 is designed to
support this claim with better controls and richer instrumentation.

---

## 2. What D1.2 fixes

| Issue in D1.1 | D1.2 fix |
|---|---|
| LT `LTP_PATH` never set → grammar all-zero | All D1 cluster scripts now `source research_cache_env.sh`. Added `direction_1_grammar_rescore.sh` + `research.scripts.rescore_direction_1_grammar` as safety net. Cluster runner also does a LT pre-flight check. |
| No true baseline — every arm had some intervention | Added **vanilla-plain** control (`baseline_hf_plain`, no inject, greedy T=0). |
| Prompt/decode confound — could not tell if beam's poor score was the decoder or the missing gold-form line in the prompt | Added **hard-inject-plain** combo arm: beam+`force_words_ids` **plus** gold form in the prompt. Separates "does injection help beam?" from "does beam help by itself?". |
| No way to distinguish "constraint fired but wrong role" from "constraint never fired" | Beam generators now log `fired=1/0` per cell and a `firing_rate=k/N` per batch (case-insensitive substring of `expected_form` in decoded text). |
| `</think>` leaked through the custom constrained-beam path even with `enable_thinking=False` in the chat template | Hardened `_strip_thinking`: strips any prefix up to and including a stray `</think>` (belt-and-braces). |
| Tokenisation of accented forms silently untested | Added `research.scripts.inspect_force_variants` to dump token-id variants for every `expected_form` in a benchmark. |
| Per-arm DB pattern not applied to D1 (single `research.db` was shared) | Cluster runner uses `RESEARCH_DB=research/runs/direction_1p2_<arm>.db` per arm (D5 pattern). |

---

## 3. D1.2 arm matrix

Five arms, one benchmark (`spanish_direction_hl50`, 1,550 cells), one sample
per cell, Qwen3-1.7B, greedy or deterministic beam:

| ID | Registry method | Prompt injects form? | Decode | Purpose |
|----|----------------|----------------------|--------|---------|
| **vanilla-plain**       | `baseline_hf_plain` | No  | Greedy T=0 | **Control.** How well does Qwen3-1.7B do with neither prompt injection nor decode-time forcing? |
| **inject-plain**        | `baseline_hf_form_injected_plain` | Yes | Greedy T=0 | Prompt-mechanism arm. |
| **hard-plain**          | `constrained_hf_hard_plain` | No | Beam + `force_words_ids` | Decode-mechanism arm. |
| **hard-inject-plain**   | `constrained_hf_hard_inject_plain` | Yes | Beam + `force_words_ids` | **Both mechanisms.** Does prompt injection additionally rescue beam? |
| **soft-plain**          | `constrained_hf_soft_plain` | No | Beam + logit bias λ=5 | Soft variant for comparison. |

**JSON arms are dropped from D1.2** — D1.1 already showed JSON is a
consistent secondary regression for both mechanisms. A single format ×
2 × 2 mechanism factorial is cleaner for the write-up. JSON arms remain
runnable via their existing YAMLs if needed.

**Explicit-overlay arms** (`build_prompt_explicit` variants) are deliberately
**out of scope for D1.2** — that's Diagnostic 5C territory. Add later if
D1.2 leaves a clear residual explained by prompt strength.

---

## 4. Instrumentation added

### Constraint firing (in `constrained_hf.py`)

Per-cell log line now includes `fired=<0|1>`:

```
[constrained_hf_hard_plain batch call 1 job 3] parsed=1 mode=plain fired=1
```

Per-batch summary:

```
[constrained_hf_hard_plain batch call 1] firing_rate=6/8
```

- `fired=1` and EF=0 → constraint fired, wrong syntactic role (interesting).
- `fired=0` and EF=0 → constraint never fired (mechanism failure).

### Thinking-leak defence (in `baseline_hf._strip_thinking`)

Regex now handles a bare trailing `</think>` in addition to full `<think>…</think>` pairs. Prevents raw CoT text leaking into stored sentences under the community `custom_generate` constrained-beam path.

### Tokenisation sanity script

```bash
python3 -m research.scripts.inspect_force_variants \
  --benchmark research/benchmarks/spanish_direction_hl50.yaml \
  --model Qwen/Qwen3-1.7B --summary
```

Prints token-length histogram of `expected_form` variants and flags forms whose decoded round-trip doesn't match the surface string (accent drift / multi-piece splits). Cheap check before every rerun.

---

## 5. Rerun plan

### Preconditions

- [ ] Push `direction_1.2` branch, `git pull` on cluster.
- [ ] `source research/scripts/cluster/research_cache_env.sh` on the cluster interactive shell.
- [ ] Run tokenisation inspector (`--summary`) → confirm no red flags.
- [ ] Run **cluster smoke** (2 verbs, all five arms) using the same runner — verify LT pre-flight passes and firing telemetry appears.

### Full rerun

```bash
sbatch research/scripts/cluster/direction_1p2_all_hl50_gpu.sh
```

- Sequential, one GPU, one DB per arm (`research/runs/direction_1p2_<arm>.db`).
- Includes a LanguageTool pre-flight before any generation runs — the whole job aborts if LT can't init, so grammar-0% cannot happen silently.
- Expect **~8–14 h** wall time for all five arms (beam arms are the tall pole; vanilla + inject are fast).

### If grammar still fails

```bash
sbatch research/scripts/cluster/direction_1_grammar_rescore.sh
```

Rescores in place; ~30–60 min per arm. This is only needed if the pre-flight
somehow succeeds but sentences still come back grammar-0%.

---

## 6. Reporting frame (write-up outline)

The pilot section should now read as:

1. **Setup** — hl50, 1 sample/cell, five arms (vanilla / inject / hard / hard-inject / soft), matched prompt scaffolds.
2. **Headline** — EF, grammar, length, firing rate per arm. Report grammar with LT working.
3. **Findings**
   - The presence-vs-role gap: `force_words_ids` is a presence primitive; even at 100% firing rate we observe token-injection collapse rather than agreement-correct sentences.
   - Compare hard-plain (no inject, beam) with hard-inject-plain (inject, beam) to bound whether prompt-level cue is what beam is missing.
   - Vanilla-plain sets the floor; inject-plain the ceiling for prompt mechanism; hard-inject-plain tests whether the two mechanisms are complementary.
4. **Limitations** (explicit list, not a footnote)
   - Beam width fixed at 4; a width sweep is future work.
   - Deterministic n=1; no sample-noise reporting for beam (by design).
   - `custom_generate` community constrained-beam-search kernel dependency.
   - `enable_thinking=False` was hardened defensively; any residual leakage would inflate garbage output rather than form match.
5. **Motivation for Direction 2** — role-anchored / agreement-aware decoding, since presence constraints do not encode morphosyntactic structure.

---

## 7. What is *not* changed in D1.2

- Benchmark, model, sample count, beam width, bias strength, seed — all
  identical to D1.1 for direct comparability.
- Prompt builders — the beam prompt is still `build_prompt_plain` with the
  same constraint block as inject arms. What differs is that we now include
  the vanilla control (no injection, no beam) and the combo (both), so the
  2×2 is complete.
- JSON arms — still exist as method YAMLs, just not in the D1.2 default runner.

---

## 8. File index (D1.2 additions)

| Path | Purpose |
|---|---|
| `research/methods/baseline/direction_1_vanilla_plain_hl50.yaml` | Control arm |
| `research/methods/baseline/direction_1a_hard_inject_plain_hl50.yaml` | Combo arm |
| `research/generation/constrained_hf.py` (`ConstrainedHFHardInjectPlainGenerator`, `_form_fired`) | Combo generator + firing telemetry |
| `research/scripts/cluster/direction_1p2_all_hl50_gpu.sh` | Sequential runner with per-arm DBs + LT pre-flight |
| `research/scripts/cluster/direction_1_grammar_rescore.sh` | Safety-net rescore |
| `research/scripts/rescore_direction_1_grammar.py` | D1-aware rescore CLI (D5 pattern) |
| `research/scripts/inspect_force_variants.py` | Tokenisation sanity check |
| Existing D1 cluster scripts | Now source `research_cache_env.sh` (LT fix) |
