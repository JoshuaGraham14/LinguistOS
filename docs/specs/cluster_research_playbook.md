# Cluster research playbook

> **Phone bookmark name:** Cluster playbook  
> **Scope:** Mac vs cluster workflow, databases, metrics, and lessons from large pipeline runs (especially Diagnostic 5)  
> **See also:** [GPU cluster access](gpu_cluster_access.md) (SSH, Slurm, env setup) · [Diagnostic 5 handoff](../handoff/diagnostic_5_handoff.md) (how to re-run 5A/5B/5C)

---

## 0. Mac vs cluster — code syncs, databases do not

### Mental model

| | **Mac** (`~/Desktop/Diss/LinguistOS`) | **Cluster** (`/vol/bitbucket/jjg25/LinguistOS`) |
|--|--------------------------------------|--------------------------------------------------|
| **Purpose** | Edit code, smoke tests, quick local debugging | Serious GPU experiments (Diagnostic 5, Direction 1, …) |
| **Synced via** | `git push` / `git pull` | `git pull` (code only) |
| **`research.db`** | Separate local file (optional, for dev) | **Source of truth** for production results |
| **`research/runs/*.db`** | Usually absent | Per-arm isolated DBs during parallel jobs |

**`*.db` is gitignored.** Git never keeps Mac and cluster databases aligned. Treat them as **different lab notebooks**.

### Policy (default)

1. **Serious experiment results live on the cluster only** — Diagnostic 5, Direction 1 beam-search runs, any multi-hour job.
2. **Never `rsync` or copy `.db` files to the cluster** while jobs are running (or as part of a blind full-repo sync).
3. **Never assume** your Mac `research.db` contains cluster results after a `git pull`.
4. **Mac DB** is fine for mock runs, 2-verb smokes, and pipeline dev — not for thesis headline numbers.

### When you need data on the Mac

Pull a **read-only snapshot** after jobs finish (for canvas, thesis plots, spot-checks):

```bash
scp jjg25@gpucluster2:/vol/bitbucket/jjg25/LinguistOS/research/runs/diagnostic_5a.db research/runs/
```

Or run export/analysis scripts on the cluster and copy small CSV/JSON outputs. Treat Mac copies as **archives for analysis**, not writable production DBs.

### Parallel arms (Diagnostic 5, Direction 1, …)

```text
N parallel jobs  →  N files under research/runs/  →  merge into research.db when all done
```

```bash
export RESEARCH_DB=research/runs/my_arm.db   # one file per arm
# … run experiment …
python3 -m research.merge_databases research/runs/arm_*.db   # or cluster merge script
```

### Rsync checklist (code only)

```bash
rsync -az \
  --exclude research/.venv \
  --exclude 'research/*.db' \
  --exclude 'research/runs/' \
  --exclude frontend/node_modules \
  ~/Desktop/Diss/LinguistOS/ jjg25@gpucluster2:/vol/bitbucket/jjg25/LinguistOS/
```

---

## 1. Runtime: O(n²) experiment-wide Self-BLEU

### What happened (Diagnostic 5, July 2026)

Each arm took **~20–24 hours** wall time on an A30 GPU node. Roughly half was generation (~9–11 h); the other half was **post-generation scoring** (~10 h), dominated by one metric.

The pipeline registers **18 group metrics** — 9 at `constraint_set` scope (per cell) and 9 at `experiment` scope (all sentences pooled). The bottleneck was:

| Metric | Scope | Cost at n=150 |
|--------|--------|----------------|
| **`self_bleu_experiment`** | All 46,500 sentences | **O(n²)** — each sentence scored against ~46,499 references via sacrebleu |
| `self_bleu` (per cell) | 10 sentences × 4,650 cells | O(10²) per cell — minutes total |
| All other experiment-wide metrics | Linear in n or tokens | Seconds to minutes |

At 46,500 sentences, experiment-wide Self-BLEU implies on the order of **2×10⁹** reference comparisons. That alone accounts for most of the post-gen wall time. The job was not stuck: CPU sat at ~96% while `experiment_metrics` row count stayed at 0 until a single batch commit at the end.

### Why it was hard to diagnose

- Group metrics had **no incremental commits or progress logs** during the first run (later fixed with per-metric logging and commits every 500 cells).
- Slurm `.out` logs were **buffered** — tail looked idle long after generation finished.
- Monitoring query `SELECT COUNT(*) FROM experiment_metrics` showed **0 for hours** by design (one commit at end), not because the process had crashed.

### Fixes in place

| Fix | Purpose |
|-----|---------|
| **`--skip-experiment-group-metrics`** | Skip all 9 pooled experiment-scope metrics; keep per-cell metrics + sentence roll-ups. **Use on any large multi-cell benchmark.** |
| **`SELF_BLEU_EXPERIMENT_CAP=500`** | If experiment Self-BLEU is enabled, subsample to 500 sentences (deterministic seed). |
| Incremental commits in `_compute_and_store_group_metrics` | Visibility + smaller WAL spikes. |
| `PYTHONUNBUFFERED=1` in cluster env | Logs flush in real time. |
| Diagnostic 5 cluster scripts | `--skip-experiment-group-metrics` enabled by default. |

### Rule of thumb for future runs

| Scale | Experiment-wide group metrics? |
|-------|--------------------------------|
| ≤500 sentences (e.g. Exp 9 grid) | Optional — fast enough |
| 4,650+ cells / 46k+ sentences | **Skip** (`--skip-experiment-group-metrics`) |
| Need corpus-level Self-BLEU anyway | Enable with cap, or compute offline on a sample |

**Expected post-gen time after fixes:** ~30–60 minutes (sentence eval + per-cell metrics + roll-ups), not ~10 hours.

---

## 2. Database: rsync overwrite and parallel jobs

### What happened

The first cluster attempt (jobs 258146–258148) **crashed around 50%** with `sqlite3.OperationalError: disk I/O error`. Cause: **`rsync` replaced `research/research.db` on the shared filesystem while three GPU jobs were writing to it.** SQLite does not tolerate the DB file being swapped out from under an open connection.

All three arms had been pointed at the **same** canonical `research.db`, so they also contended on one file even without rsync.

### Fixes in place

| Practice | Detail |
|----------|--------|
| **Per-arm `RESEARCH_DB`** | Each job writes to an isolated file, e.g. `research/runs/diagnostic_5a.db`. Set via `RESEARCH_DB` env in cluster scripts; supported in `research/db/database.py`. |
| **Merge after completion** | `research/merge_databases.py` / `diagnostic_5_merge.sh` copies completed experiments into canonical `research.db` by stable names. |
| **Never rsync `*.db` while jobs run** | Sync code only; copy DBs read-only for analysis, or merge after jobs finish. |
| **WAL mode + 60s busy timeout** | Reduces (but does not eliminate) pain from concurrent readers; does **not** fix overwrite-from-rsync. |
| **`--resume`** | Safe restart after crash without regenerating finished cells. |

### Safe monitoring (read-only)

```bash
sqlite3 "file:/path/to/diagnostic_5a.db?mode=ro" \
  "SELECT status, completed_at FROM experiments;"
```

Check process CPU on the compute node (`ps`) rather than assuming a stalled log means a dead job.

### Rule of thumb

- **N parallel arms → N database files** until merge.
- Treat `research.db` and `research/runs/*.db` on the **cluster** as production; keep the Mac out of the write path.

---

## 3. Experiment-wide group metrics — what they are and when to use them

The pipeline runs two **scopes** of distribution metrics:

| Scope | Unit | Stored as |
|-------|------|-----------|
| **`constraint_set`** | 10 sentences for **one** verb + morphological form | One row per cell per metric |
| **`experiment`** | All sentences in the run pooled | One row per metric |

Sentence **roll-ups** (`pass_rate::expected_form_match`, etc.) are separate: they aggregate sentence evaluator scores and are always experiment-level (and per-cell). **Do not confuse roll-ups with group metrics.**

### Experiment-wide metrics (9 total)

| Metric | What it measures | Useful at n=150? | Runtime |
|--------|------------------|------------------|---------|
| `uniqueness_ratio_experiment` | Distinct strings / 46,500 | **Poor headline** — different lemmas ⇒ mostly distinct by construction | Fast |
| `self_bleu_experiment` | Mean sentence BLEU vs all other sentences | Cross-verb similarity only; **prohibitively slow** | **O(n²)** |
| `template_rate_experiment` | Share of sentences sharing a 3-token opening with *any* other sentence in run | Niche (global template reuse) | Fast |
| `distinct_1_experiment`, `distinct_2_experiment` | Corpus lexical diversity (type/token on n-grams) | Optional footnote | Fast |
| `mean_token_count_experiment`, `length_cv_experiment` | Global length distribution | Partially redundant with `length_in_band` roll-ups | Fast |
| `mean_clauses_experiment` | Global mean clause count | Optional | Fast |
| `lt_error_breakdown_experiment` | Pooled grammar-error histogram | Only when LT works | Fast |

### What you lose by skipping experiment-wide metrics

You **keep**:

- Sentence-level evals and **roll-ups** (EF, length, grammar pass rates).
- All **per-cell** diversity metrics (uniqueness, Self-BLEU, template rate, distinct-n, …).
- Any analysis that **means per-cell scores** (correct for morphological benchmarks).

You **lose**:

- Single-number **corpus-pooled** diversity stats across unrelated target forms.
- Detection of **cross-cell** template reuse (same scaffold for different verbs).
- Pooled LT error histogram at experiment scope (per-cell LT breakdown still exists when grammar runs).

For Diagnostic 5–style census grids, **per-cell → mean** is the right unit of analysis. Experiment-pooled uniqueness was actively misleading as a headline (and experiment-pooled uniqueness for 5A was **lower** than mean per-cell uniqueness because cross-cell duplicate strings deflate the ratio).

### Correct diversity aggregation for multi-cell benchmarks

**Do:**

1. Compute uniqueness / Self-BLEU / template rate **per constraint set** (10 samples, same target form).
2. Report **mean (or median) over cells**, optionally grouped by tense.
3. Use sentence roll-ups for EF and length pass rates.

**Do not:**

- Headline `uniqueness_ratio_experiment` or `self_bleu_experiment` on 150-verb grids.
- Assume high experiment-wide uniqueness means “creative” output — it often just means different lemmas.

---

## 4. LanguageTool and grammar rescore

### What happened (first D5 eval pass)

**Grammar was 0% on all 46,500 sentences in every arm** — not a model result. LanguageTool failed on init:

```text
[Errno 122] Disk quota exceeded: '/homes/jjg25/.cache/language_tool_python'
```

The evaluator catches the exception and scores 0.0.

### Fixes in place

| Fix | Detail |
|-----|--------|
| **`LTP_PATH`** on project volume | `research/scripts/cluster/research_cache_env.sh` sets `LTP_PATH="${PROJECT}/.cache/language_tool_python"`. |
| **LT init failure cache** | After first init failure for a language, do not retry on every sentence. |
| **Grammar rescore** | `python3 -m research.scripts.rescore_diagnostic_5_grammar` re-runs LT only (no regeneration). |

### Grammar rescore results (July 2026, job 258917)

After rescore with `LTP_PATH` on the project volume (~34 min for all three arms):

| Arm | Grammar pass (sentence mean) |
|-----|------------------------------|
| 5A | 99.46% |
| 5B | 98.60% |
| 5C | 98.97% |

Per-arm DBs: `research/runs/diagnostic_5{a,b,c}.db`. Merge into canonical `research.db`:

```bash
bash research/scripts/cluster/diagnostic_5_merge.sh
```

---

## 5. Scientific takeaways (Diagnostic 5)

### Generation and scoring unit

- **10 sentences per cell** via batched generation with `samples_per_case: 10`.
- **Headline metric = sentence-level pass rate** over all sentences, not pass@k per cell.
- **Length is in the prompt:** `sentence_length: short` → 2–5 **tokens** in constraints; 5C explicit overlay says “words” but evaluator uses tokens.

### Main findings (Qwen 1.7B, n=150)

| Arm | EF (sentence) | Length in band | Mean per-cell uniqueness | Grammar (after rescore) |
|-----|--------------:|---------------:|-------------------------:|------------------------:|
| 5A baseline | 24% | 45% | 81.5% | ~99% |
| 5B form-injected | 89.5% | 44% | 90.4% | ~99% |
| 5C inject + explicit | 93.6% | **65%** | 92.2% | ~99% |

- Form injection replicates Exp 9 at scale (+65 pp EF).
- Explicit overlay (5C) mainly adds **length compliance**, not EF.
- **Participle** remains weakest tense even with injection (~77% EF for 5C).
- High per-cell uniqueness often reflects **slot-filling variation** (*Él X la Y*), not structural diversity — read alongside Self-BLEU and template rate.

### Common failure modes (from spot-checking 5C outputs)

| Failure | Example pattern |
|---------|-----------------|
| EF fail — wrong tense | `sobrepasarán` for conditional `sobrepasarían` |
| EF fail — paraphrase | `estarían ausentes` instead of `ausentarían` |
| EF fail — infinitive | `comer helado` for `comería` |
| EF fail — participle | finite verb or nominalization instead of participle token |
| Length fail — too long | Correct form in 6–12 token sentence (band is 2–5) |
| Length fail — too short | Bare verb token only (`vertido`, `mazaríamos`) |
| Low uniqueness cell | Identical string repeated 10× |

---

## 6. Checklist for future pipeline experiments

### Before submit

- [ ] Benchmark size estimate: cells × samples_per_case = total sentences.
- [ ] If **>5,000 sentences**, add `--skip-experiment-group-metrics`.
- [ ] Parallel arms use **separate `RESEARCH_DB`** files on the **cluster**.
- [ ] Cluster script sources `research_cache_env.sh` (`LTP_PATH`, `HF_HOME`, `PYTHONUNBUFFERED`).
- [ ] Smoke run on a 2-verb benchmark end-to-end including metrics.
- [ ] Verify LanguageTool on cluster (grammar not all-zero).
- [ ] Deploy **code only** (`git pull` or rsync excluding `*.db`).

### During run

- [ ] Use `ps` + read-only SQLite (`mode=ro`) for progress.
- [ ] Do not interpret `experiment_metrics` count = 0 as crash during metrics phase (check CPU).
- [ ] Do not rsync or edit the DB file the job is writing.

### After run

- [ ] Merge per-arm DBs on cluster: `bash research/scripts/cluster/diagnostic_5_merge.sh` (or `merge_databases.py`).
- [ ] Report diversity as **mean per-cell** metrics; EF/length/grammar as **sentence roll-ups**.
- [ ] Validate grammar evals (no `error` in `sentence_evaluations.details`).
- [ ] Pull read-only DB snapshots to Mac only if needed for local analysis.

### CLI reference

```bash
# Large benchmark (recommended)
python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5b_hf_qwen3_17b_n10 \
  --live --resume \
  --skip-experiment-group-metrics

# Grammar rescore only (after LT fix)
export RESEARCH_DB=research/runs/diagnostic_5a.db
python3 -m research.scripts.rescore_diagnostic_5_grammar --arm 5a

# Isolated DB for cluster arm
export RESEARCH_DB=research/runs/my_arm.db
```

---

## 7. Related code and docs

| Item | Location |
|------|----------|
| SSH / Slurm / first-time setup | [gpu_cluster_access.md](gpu_cluster_access.md) |
| Skip experiment metrics flag | `research/run_experiment.py`, `research/pipeline.py` |
| Metric scope filter | `research/evaluation/distribution/__init__.py` |
| Self-BLEU cap | `research/evaluation/distribution/self_bleu.py` |
| Per-arm DB + merge | `research/db/database.py`, `research/merge_databases.py` |
| Grammar rescore | `research/evaluation/rescore.py`, `research/scripts/rescore_diagnostic_5_grammar.py` |
| Cluster env | `research/scripts/cluster/research_cache_env.sh` |
| Diagnostic 5 cluster scripts | `research/scripts/cluster/diagnostic_5{a,b,c}_n150_gpu.sh` |
| D5 merge | `research/scripts/cluster/diagnostic_5_merge.sh` |

---

## 8. Summary one-liners

1. **Code via git; databases on cluster** — never treat Mac and cluster DBs as synced.
2. **~10 h post-gen delay** → experiment-wide Self-BLEU at 46k sentences; use `--skip-experiment-group-metrics`.
3. **Mid-run DB corruption** → rsync overwrote `research.db`; use per-arm `RESEARCH_DB`.
4. **Experiment-wide uniqueness** → wrong aggregation for census grids; use mean per-cell uniqueness.
5. **Grammar 0% (first pass)** → home-directory LT cache; rescore with `LTP_PATH` on project volume.
6. **Looks stuck but isn't** → metrics batch commit + log buffering; check CPU, not just row counts.
