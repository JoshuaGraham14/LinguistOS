# GPU Cluster Access — Imperial DoC Slurm

> Status: operational guide (Jul 2026)  
> Scope: running LinguistOS research experiments on the DoC GPU cluster  
> Related: `research/scripts/cluster/research_cache_env.sh`, `research/scripts/cluster/qwen_batch_env.sh`

---

## 1. What this is

The Imperial Department of Computing GPU cluster is a shared pool of GPU machines managed by **Slurm**. You do not SSH directly into “a GPU laptop in the cloud.” Instead:

1. You connect to a **head node** (`gpucluster2` / `gpucluster3`) — a small login VM with **no GPU**.
2. You ask Slurm for a GPU (`salloc` or `sbatch`).
3. Slurm assigns you a **compute node** (e.g. `parrot`, `gpuvm36`) where your code actually runs.

Your Mac is for editing. The cluster is for running heavy HF/Qwen experiments at scale.

---

## 2. Mental model

```
MacBook (edit code)
    ↓ ssh / git pull / rsync
/vol/bitbucket/jjg25/LinguistOS   ← persistent cluster copy of repo
    ↓ salloc / sbatch (from head node)
GPU compute node (parrot, …)        ← Qwen inference runs here
```

Three separate places:

| Location | Role |
|---|---|
| Local Mac (`~/Desktop/Diss/LinguistOS`) | Development, quick iteration |
| Head node (`gpucluster2`) | Submit jobs, light commands only |
| Bitbucket volume (`/vol/bitbucket/jjg25/`) | Persistent repo + caches + venv |
| GPU node (`parrot`, etc.) | Actual experiment execution |

---

## 3. One-time setup

### 3.1 SSH config (Mac)

Add to `~/.ssh/config`:

```
Host gpucluster2
  HostName gpucluster2.doc.ic.ac.uk
  User jjg25
  ProxyJump shell3
  IdentityFile ~/.ssh/doc_ed25519
  IdentitiesOnly yes

Host gpucluster3
  HostName gpucluster3.doc.ic.ac.uk
  User jjg25
  ProxyJump shell3
  IdentityFile ~/.ssh/doc_ed25519
  IdentitiesOnly yes
```

Load your key once per Mac session:

```bash
ssh-add ~/.ssh/doc_ed25519
ssh gpucluster2
```

### 3.2 Repo on cluster

Preferred workflow:

```bash
# on gpucluster2
cd /vol/bitbucket/jjg25
git clone git@github.com:JoshuaGraham14/LinguistOS.git   # first time only
cd LinguistOS
git pull                                                  # day-to-day updates
```

Alternative for uncommitted local changes: `rsync` from Mac to `/vol/bitbucket/jjg25/LinguistOS/`.

**Never rsync `research.db` or per-arm `research/runs/*.db` while jobs are running** — use isolated `RESEARCH_DB` files per parallel arm (see §7).

### 3.3 Python environment (cluster)

Create once on the head node (light `pip install` is acceptable here):

```bash
cd /vol/bitbucket/jjg25/LinguistOS/research
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt torch transformers accelerate
```

Do **not** use `/vol/bitbucket/starter` for full pipeline runs — it lacks project dependencies.

### 3.4 Cache redirects (critical)

Home directory (`/homes/jjg25`) has a small quota. Hugging Face models (~3GB+) and LanguageTool (~260MB) must cache on the project volume instead.

Cluster SLURM scripts source this automatically. For interactive runs, set `PROJECT` then source:

```bash
export PROJECT=/vol/bitbucket/jjg25/LinguistOS
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
```

This sets:

- `HF_HOME`, `TRANSFORMERS_CACHE` → `${PROJECT}/.cache/huggingface`
- `LTP_PATH` → `${PROJECT}/.cache/language_tool_python`
- `PYTHONUNBUFFERED=1` for live log streaming

Without this, runs fail with `Disk quota exceeded` in home cache paths.

For Qwen HF batching (Diagnostic 5 and spike scripts), also source:

```bash
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
```

### 3.5 GitHub auth (cluster)

Cluster git remote should use SSH (`git@github.com:...`). Add the cluster public key (`~/.ssh/id_ed25519.pub` on gpucluster2) to GitHub → Settings → SSH keys.

---

## 4. Day-to-day workflow (interactive — recommended)

Supervisor guidance: use **interactive** mode while developing; use **batch** for long unattended sweeps.

### Terminal 1 — allocate GPU (keep open)

```bash
ssh gpucluster2
salloc --gres=gpu:1 --partition=a30 --no-shell
squeue --me    # note node name, e.g. parrot; note JOBID
```

### Terminal 2 — run on GPU node

```bash
ssh -J gpucluster2 jjg25@parrot.doc.ic.ac.uk

export PROJECT=/vol/bitbucket/jjg25/LinguistOS
cd "${PROJECT}"
source research/.venv/bin/activate
source research/scripts/cluster/research_cache_env.sh

/usr/bin/time -p python3 -m research.run_experiment \
  --benchmark spanish_basic_grid \
  --method baseline_hf_qwen3_17b_n10 \
  --live
```

### When finished — release GPU

Back in Terminal 1:

```bash
scancel <JOBID>
```

---

## 5. Batch workflow (recommended for long runs)

For overnight or multi-hour sweeps, submit a Slurm script with `sbatch` from the head node. Example:

```bash
sbatch research/scripts/cluster/diagnostic_5a_n150_gpu.sh
```

Output goes to `logs/*.out`. Diagnostic cluster scripts already source cache env, set `RESEARCH_DB`, and pass `--skip-experiment-group-metrics` for large grids.

Interactive mode is better for debugging; batch is better once a command is stable.

---

## 6. What runs where

| Command | Where | OK? |
|---|---|---|
| `ssh gpucluster2` | Head node | Yes |
| `salloc`, `sbatch`, `squeue`, `scancel` | Head node | Yes |
| `git pull`, `ls`, `cd` | Head node | Yes |
| `python -m research.run_experiment --live` | **GPU node only** | Yes |
| `python` heavy jobs | Head node | **No** — use Slurm |

The head-node banner (“solely for submitting sbatch jobs”) means: don’t run compute on the login VM; submit to Slurm instead.

---

## 7. Example experiment commands

From repo root on a GPU node (venv + `research_cache_env.sh` sourced):

```bash
# Small grid (50 cells)
python3 -m research.run_experiment \
  --benchmark spanish_basic_grid \
  --method baseline_hf_qwen3_17b_n10 \
  --live

# Large grid — skip experiment-wide metrics (saves ~10h post-gen on 46k+ sentences)
python3 -m research.run_experiment \
  --benchmark spanish_diagnostic_n150 \
  --method diagnostic_5a_hf_qwen3_17b_n10 \
  --live \
  --skip-experiment-group-metrics

# Parallel arms — isolated DB per job (never share one DB across concurrent writes)
export RESEARCH_DB="${PROJECT}/research/runs/diagnostic_5a.db"
python3 -m research.run_experiment ... --live --skip-experiment-group-metrics

# Merge per-arm DBs into canonical research.db after all arms complete
bash research/scripts/cluster/diagnostic_5_merge.sh
```

Results default to `research/research.db` unless `RESEARCH_DB` overrides the path.

---

## 8. Mac vs cluster — when to use which

| Use Mac when… | Use cluster when… |
|---|---|
| Debugging prompts / small spikes | Running full grid benchmarks (50+ cells) |
| Quick 5–20 verb probes | Beam search / constrained decoding (slower) |
| Runs finishing in ~10 minutes | Multiple conditions or models in a sweep |
| You want zero SSH overhead | You want laptop free for other work |
| | Queue crunch approaches (late August) |

Observed speedup for one Exp 9 baseline run (Jul 2026): **~9.4 min (Mac MPS) vs ~7.5 min (A16 GPU)** — modest for that pipeline because evaluation (LanguageTool, metrics) adds CPU overhead. Cluster value increases as generation becomes the bottleneck (beam search, larger sweeps, HF batching).

---

## 9. GPU device selection in code

`research/generation/baseline_hf.py` selects device in order:

1. `cuda` (cluster GPU nodes)
2. `mps` (Apple Silicon Mac)
3. `cpu` (fallback)

Verify on a GPU node:

```bash
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

---

## 10. Sanity checks

```bash
# LanguageTool (after research_cache_env.sh)
python3 -c "
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
print(ev.evaluate('Yo como manzanas.', 'I eat apples.', {'target_language': 'es'}).score)
"
# Expected: 1.0

# Pipeline import
python3 -c "from research.pipeline import run_experiment; print('ok')"
```

---

## 11. Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `Disk quota exceeded` in `~/.cache/huggingface` | HF caching to home | Source `research_cache_env.sh` |
| `Disk quota exceeded` in `~/.cache/language_tool_python` | LT caching to home | same — sets `LTP_PATH` on project volume |
| `ModuleNotFoundError: dotenv` / `sacrebleu` | Wrong env (starter venv) | Use `research/.venv` |
| `grammar_languagetool: 0.0` on all sentences | LT failed silently (quota or missing download) | Fix cache path; re-run experiment |
| Mid-run DB corruption | `rsync` overwrote `research.db` during job | Per-arm `RESEARCH_DB`; never sync DBs while jobs run |
| Post-gen stuck ~10h | Experiment-wide Self-BLEU at 46k sentences | `--skip-experiment-group-metrics` |
| `Permission denied (publickey)` on `shell3` | SSH key not loaded | `ssh-add ~/.ssh/doc_ed25519` |
| Can't SSH to `parrot` directly | Need jump host | `ssh -J gpucluster2 jjg25@parrot.doc.ic.ac.uk` |
| Job stuck in `PD` | GPUs busy | Wait, or try another partition (`a30` for Diagnostic 5) |

---

## 12. Sync checklist (Mac → cluster)

```bash
# Option A: git (committed changes)
git push origin main
ssh gpucluster2
cd /vol/bitbucket/jjg25/LinguistOS && git pull

# Option B: rsync (uncommitted local changes — exclude DBs and venv)
rsync -az --exclude research/.venv --exclude 'research/*.db' --exclude 'research/runs/' \
  --exclude frontend/node_modules \
  ~/Desktop/Diss/LinguistOS/ jjg25@gpucluster2:/vol/bitbucket/jjg25/LinguistOS/
```

---

## 13. Slurm quick reference

```bash
salloc --gres=gpu:1 --partition=a30 --no-shell   # request interactive GPU
squeue --me                                       # your jobs
scancel <JOBID>                                   # release GPU
sbatch research/scripts/cluster/diagnostic_5a_n150_gpu.sh   # submit batch job
```

`a30` (24 GB VRAM) is used for Diagnostic 5 Qwen 1.7B with HF batching. `a16` (16 GB) works for smaller grids.

---

## 14. Files in this repo

| Path | Purpose |
|---|---|
| `research/scripts/cluster/research_cache_env.sh` | HF + LanguageTool cache redirects |
| `research/scripts/cluster/qwen_batch_env.sh` | Recommended HF batch sizes for Qwen models |
| `research/scripts/cluster/diagnostic_5*_n150_gpu.sh` | Example long-run SLURM jobs |
| `research/scripts/cluster/diagnostic_5_merge.sh` | Merge per-arm DBs into `research.db` |
| `research/merge_databases.py` | DB merge utility |
| `research/.venv/` | Cluster Python environment (created on bitbucket, not in git) |
| `research/research.db` | Canonical experiment results DB |
| `research/runs/*.db` | Per-arm isolated DBs during parallel jobs |
| `docs/specs/gpu_cluster_access.md` | This document |
