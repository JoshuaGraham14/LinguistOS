# GPU cluster access — Imperial DoC Slurm

> Status: operational guide (Jul 2026)  
> Scope: SSH, Slurm, env setup, and first-time cluster configuration  
> **Playbook:** [Cluster research playbook](cluster_research_playbook.md) (databases, metrics, D5 lessons)

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

| Location | Role |
|---|---|
| Local Mac (`~/Desktop/Diss/LinguistOS`) | Development, quick iteration |
| Head node (`gpucluster2`) | Submit jobs, light commands only |
| Bitbucket volume (`/vol/bitbucket/jjg25/`) | Persistent repo + caches + venv |
| GPU node (`parrot`, etc.) | Actual experiment execution |

Database policy (Mac vs cluster, per-arm DBs, rsync rules): see the [playbook](cluster_research_playbook.md).

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

```bash
cd /vol/bitbucket/jjg25
git clone git@github.com:JoshuaGraham14/LinguistOS.git   # first time only
cd LinguistOS
git pull                                                  # day-to-day updates
```

For uncommitted local changes: `rsync` code only (exclude `*.db` — see playbook §0).

### 3.3 Python environment (cluster)

```bash
cd /vol/bitbucket/jjg25/LinguistOS/research
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt torch transformers accelerate
```

Do **not** use `/vol/bitbucket/starter` for full pipeline runs.

### 3.4 Cache redirects (critical)

```bash
export PROJECT=/vol/bitbucket/jjg25/LinguistOS
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"   # HF batching
```

Sets `HF_HOME`, `LTP_PATH`, `PYTHONUNBUFFERED` on the project volume (not home quota).

### 3.5 GitHub auth (cluster)

Use SSH remote (`git@github.com:...`). Add cluster `~/.ssh/id_ed25519.pub` to GitHub.

---

## 4. Day-to-day workflow (interactive)

**Terminal 1** — allocate GPU:

```bash
ssh gpucluster2
salloc --gres=gpu:1 --partition=a30 --no-shell
squeue --me
```

**Terminal 2** — run on GPU node:

```bash
ssh -J gpucluster2 jjg25@parrot.doc.ic.ac.uk
export PROJECT=/vol/bitbucket/jjg25/LinguistOS
cd "${PROJECT}" && source research/.venv/bin/activate
source research/scripts/cluster/research_cache_env.sh
python3 -m research.run_experiment --benchmark spanish_basic_grid \
  --method baseline_hf_qwen3_17b_n10 --live
```

Release GPU: `scancel <JOBID>` in Terminal 1.

---

## 5. Batch workflow

```bash
sbatch research/scripts/cluster/diagnostic_5a_n150_gpu.sh
```

Logs in `logs/*.out`. Prefer batch for long runs; interactive for debugging.

---

## 6. What runs where

| Command | Where | OK? |
|---|---|---|
| `salloc`, `sbatch`, `squeue` | Head node | Yes |
| `python -m research.run_experiment --live` | GPU node | Yes |
| Heavy `python` | Head node | **No** |

---

## 7. GPU device check

```bash
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

`baseline_hf.py` selects `cuda` → `mps` → `cpu`.

---

## 8. Sanity checks

```bash
python3 -c "
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
print(ev.evaluate('Yo como manzanas.', 'I eat apples.', {'target_language': 'es'}).score)
"
# Expected: 1.0
```

---

## 9. Common failures

| Symptom | Fix |
|---|---|
| `Disk quota exceeded` in `~/.cache/...` | Source `research_cache_env.sh` |
| `grammar_languagetool: 0.0` everywhere | Fix `LTP_PATH`; see playbook §4 |
| Mid-run DB corruption | Never rsync DBs during jobs; see playbook §0–2 |
| Post-gen stuck ~10h | `--skip-experiment-group-metrics` (playbook §1) |
| `Permission denied` on `shell3` | `ssh-add ~/.ssh/doc_ed25519` |
| Job stuck in `PD` | Wait or try `a30` partition |

---

## 10. Slurm quick reference

```bash
salloc --gres=gpu:1 --partition=a30 --no-shell
squeue --me
scancel <JOBID>
sbatch research/scripts/cluster/diagnostic_5a_n150_gpu.sh
```

---

## 11. Related docs

| Doc | Contents |
|---|---|
| [cluster_research_playbook.md](cluster_research_playbook.md) | Mac/cluster DB policy, D5 lessons, metrics, checklists |
| [diagnostic_5_handoff.md](../handoff/diagnostic_5_handoff.md) | How to re-run 5A/5B/5C |
