# Cluster research playbook

> **Phone bookmark:** Cluster playbook  
> **Formerly:** `diagnostic_5_lessons_learned.md`  
> **Scope:** Mac vs cluster workflow, databases, metrics, and lessons from large pipeline runs (especially Diagnostic 5, July 2026)  
> **See also:** [GPU cluster access](gpu_cluster_access.md) (SSH, Slurm, env setup) · [Diagnostic 5 handoff](../handoff/diagnostic_5_handoff.md)

For arm design and how to re-run Diagnostic 5, see the handoff doc. For headline science numbers, query `research/runs/diagnostic_5*.db` on the cluster or run `research/scripts/analyze_diagnostic_5_results.py`.

---

## 0. Mac vs cluster — code syncs, databases do not

### Mental model

| | **Mac** (`~/Desktop/Diss/LinguistOS`) | **Cluster** (`/vol/bitbucket/jjg25/LinguistOS`) |
|--|--------------------------------------|--------------------------------------------------|
| **Purpose** | Edit code, smoke tests, quick local debugging | Serious GPU experiments (Diagnostic 5, Direction 1, …) |
| **Synced via** | `git push` / `git pull` | `git pull` (code only) |
| **`research.db`** | Separate local file (optional, for dev) | Canonical DB on cluster (may lag per-arm files — see §2) |
| **`research/runs/*.db`** | Usually absent | **Source of truth** for completed per-arm runs |

**`*.db` is gitignored.** Git never keeps Mac and cluster databases aligned. Treat them as **different lab notebooks**.

### Policy (default)

1. **Serious experiment results live on the cluster** — Diagnostic 5, Direction 1, any multi-hour job.
2. **Never `rsync` or copy `.db` files** to/from the cluster while jobs are running (or as part of a blind full-repo sync).
3. **Never assume** your Mac `research.db` contains cluster results after a `git pull`.
4. **Mac DB** is fine for mock runs, 2-verb smokes, and pipeline dev — not for thesis headline numbers.

### When you need data on the Mac

Pull a **read-only snapshot** after jobs finish:

```bash
scp jjg25@gpucluster2:/vol/bitbucket/jjg25/LinguistOS/research/runs/diagnostic_5a.db research/runs/
```

Or run export/analysis on the cluster and copy small CSV/JSON outputs. Mac copies are **archives for analysis**, not writable production DBs.

### Parallel arms

```text
N parallel jobs  →  N files under research/runs/  →  optional merge into research.db
```

```bash
export RESEARCH_DB=research/runs/my_arm.db
python3 -m research.run_experiment ... --live
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

### What happened

Each Diagnostic 5 arm took **~20–24 hours** wall time on an A30. Roughly half was generation (~9–11 h); the other half was **post-generation scoring** (~10 h), dominated by one metric.

| Metric | Scope | Cost at n=150 |
|--------|--------|----------------|
| **`self_bleu_experiment`** | All 46,500 sentences | **O(n²)** |
| `self_bleu` (per cell) | 10 sentences × 4,650 cells | O(10²) per cell — minutes |
| Other experiment-wide metrics | Linear in n | Seconds to minutes |

### Fixes in place

| Fix | Purpose |
|-----|---------|
| **`--skip-experiment-group-metrics`** | Skip pooled experiment-scope metrics on large benchmarks |
| **`SELF_BLEU_EXPERIMENT_CAP=500`** | Subsample if experiment Self-BLEU is enabled |
| Incremental metric commits | Progress visibility during long metric phases |
| `PYTHONUNBUFFERED=1` | Real-time Slurm logs |

### Rule of thumb

| Scale | Experiment-wide group metrics? |
|-------|--------------------------------|
| ≤500 sentences | Optional |
| 4,650+ cells / 46k+ sentences | **Skip** |
| Need corpus Self-BLEU | Enable with cap, or compute offline |

**Expected post-gen after fixes:** ~30–60 minutes, not ~10 hours.

---

## 2. Database: rsync overwrite, parallel jobs, and merge limits

### What happened

First cluster attempt **crashed ~50%** with `disk I/O error` — **`rsync` replaced `research.db` while three jobs were writing.** All three arms had also shared one `research.db`.

### Fixes in place

| Practice | Detail |
|----------|--------|
| **Per-arm `RESEARCH_DB`** | e.g. `research/runs/diagnostic_5a.db` |
| **Merge after completion** | `merge_databases.py` / `diagnostic_5_merge.sh` |
| **Never rsync `*.db` while jobs run** | Sync code only |
| **`--resume`** | Safe restart without regenerating finished cells |

### Merge is additive, not a sync

`merge_databases` **copies new rows** into `research.db`. It does **not update** existing `sentence_evaluations` when scores change later.

Example (Diagnostic 5, July 2026):

1. **06:13** — merge job 258309 copied all three arms into `research.db` (with grammar 0% from LT quota failure).
2. **14:39** — grammar rescore updated `research/runs/diagnostic_5{a,b,c}.db` in place (~99% grammar).
3. Re-running merge reported `+0 evals` — experiments already existed, stale grammar stayed in `research.db`.

**Authoritative Diagnostic 5 results (with valid grammar):** `research/runs/diagnostic_5{a,b,c}.db` on the cluster.

To refresh `research.db`: run rescore against it directly, or delete the D5 experiment rows and re-merge.

### Safe monitoring

```bash
sqlite3 "file:/path/to/diagnostic_5a.db?mode=ro" \
  "SELECT status, completed_at FROM experiments;"
```

---

## 3. Experiment-wide group metrics

Two scopes: **`constraint_set`** (per cell) and **`experiment`** (all sentences pooled). Sentence **roll-ups** (`pass_rate::…`) are separate — always report EF/length/grammar from roll-ups.

For Diagnostic 5–style census grids:

- **Do** report mean per-cell uniqueness, Self-BLEU, template rate.
- **Do not** headline `uniqueness_ratio_experiment` or `self_bleu_experiment` on 150-verb grids.

---

## 4. LanguageTool and grammar rescore

### First pass failure

Grammar was **0% on all sentences** — LanguageTool hit home-disk quota:

```text
Disk quota exceeded: '/homes/jjg25/.cache/language_tool_python'
```

### Fixes

| Fix | Detail |
|-----|--------|
| **`LTP_PATH`** on project volume | `research_cache_env.sh` |
| **Grammar rescore** | `python3 -m research.scripts.rescore_diagnostic_5_grammar` |

### Rescore results (job 258917, ~34 min all arms)

| Arm | Grammar pass |
|-----|-------------|
| 5A | 99.46% |
| 5B | 98.60% |
| 5C | 98.97% |

Rescore updates eval rows **in place** in whichever DB you point at (`RESEARCH_DB`). No regeneration needed.

---

## 5. Scientific takeaways (Diagnostic 5)

**Setup:** Qwen3-1.7B, T=0.7, 10 sentences/cell, `short` length, 4,650 cells, 46,500 sentences/arm.

| Arm | EF | Length in band | Mean per-cell uniqueness | Grammar |
|-----|---:|---------------:|-------------------------:|--------:|
| 5A baseline | 24% | 45% | 81.5% | ~99% |
| 5B form-injected | 89.5% | 44% | 90.4% | ~99% |
| 5C inject + explicit | 93.6% | **65%** | 92.2% | ~99% |

- Form injection: **+65 pp EF** (5A → 5B).
- Explicit overlay (5C): **+20 pp length**, +4 pp EF.
- **Participle** weakest tense (~77% EF on 5C).
- High per-cell uniqueness often = slot-filling variation (*Él X la Y*), not structural diversity.

### Common failure modes (5C spot-check)

| Failure | Example |
|---------|---------|
| Wrong tense | `sobrepasarán` for conditional `sobrepasarían` |
| Paraphrase | `estarían ausentes` instead of `ausentarían` |
| Infinitive | `comer helado` for `comería` |
| Participle | finite verb instead of participle token |
| Too long | Correct form in 6–12 token sentence (band 2–5) |
| Too short | Bare verb only (`vertido`) |

---

## 6. Checklist for future pipeline experiments

### Before submit

- [ ] Estimate cells × samples_per_case.
- [ ] If **>5,000 sentences**, `--skip-experiment-group-metrics`.
- [ ] Parallel arms → separate `RESEARCH_DB` on cluster.
- [ ] Source `research_cache_env.sh`; verify LanguageTool (grammar ≠ 0%).
- [ ] Deploy **code only** (`git pull` or rsync excluding `*.db`).

### During run

- [ ] Monitor with `ps` + read-only SQLite.
- [ ] Do not rsync or edit the DB a job is writing.

### After run

- [ ] Query per-arm DBs for authoritative results.
- [ ] Merge into `research.db` only if you need one combined file (first time).
- [ ] Rescore grammar in place if LT failed on first pass.
- [ ] Report diversity as **mean per-cell**; EF/length/grammar as sentence roll-ups.

### CLI reference

```bash
python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5b_hf_qwen3_17b_n10 \
  --live --resume --skip-experiment-group-metrics

export RESEARCH_DB=research/runs/diagnostic_5a.db
python3 -m research.scripts.rescore_diagnostic_5_grammar --arm 5a
```

---

## 7. Related code

| Item | Location |
|------|----------|
| Skip experiment metrics | `research/run_experiment.py`, `research/pipeline.py` |
| Per-arm DB + merge | `research/db/database.py`, `research/merge_databases.py` |
| Grammar rescore | `research/evaluation/rescore.py`, `research/scripts/rescore_diagnostic_5_grammar.py` |
| Cluster env | `research/scripts/cluster/research_cache_env.sh` |
| D5 analysis | `research/scripts/analyze_diagnostic_5_results.py` |

---

## 8. Summary one-liners

1. **Code via git; databases on cluster** — never treat Mac and cluster DBs as synced.
2. **Per-arm DBs are authoritative** after rescore; merge does not refresh existing evals.
3. **Skip experiment-wide metrics** on 46k+ sentence runs.
4. **Mean per-cell uniqueness** — not experiment-pooled ratios.
5. **Grammar rescore in place** — no regeneration needed when LT cache was wrong.
