# Git worktree workflows

This repo uses **git worktrees** so parallel work (stable app, research, frontend) stays isolated without constant branch switching.

> **Note:** Any specific folder paths or branch names below are **examples only**. Cursor generates worktree paths automatically (under `~/.cursor/worktrees/…`); branch names should follow the topic you are working on, not a fixed list. Always run `git worktree list` to see what exists right now.

## Checkouts

| Location | Branch (example) | Use for |
|---|---|---|
| `~/Desktop/Diss/LinguistOS` | `main` | Stable app — frontend, backend, demos, general fixes |
| `~/.cursor/worktrees/<id>/LinguistOS-<hash>` | e.g. `research/<topic>` | Research pipeline, benchmarks, experiments |
| `~/.cursor/worktrees/<id>/LinguistOS-<hash>` | e.g. `feat/<topic>` or `frontend/<topic>` | Feature / frontend work in isolation |

List all worktrees anytime:

```bash
git worktree list
```

## Branching strategy

Work happens on **topic branches**, merged into `main` when ready.

| Prefix | Typical use |
|---|---|
| `research/<topic>` | Evaluation pipeline, benchmarks, experiments, thesis docs |
| `feat/<topic>` | App features (frontend, backend, vocab, etc.) |
| `docs/<topic>` | Documentation-only changes |

Examples from history: `research/eval-diversity-metrics`, `feat/unified-vocab-views`, `docs/experiment-results-reports`. Name branches after the **task**, not after a worktree folder.

## Merge strategy

We merge topic branches into `main` with **merge commits** (not squash, not rebase onto main). This preserves branch history and matches existing repo convention.

Merge commit message format:

```
Merge <branch-name>: <short description>.
```

Examples:

```
Merge research/eval-diversity-metrics: diversity metrics and spanish_challenging benchmark.
Merge feat/unified-vocab-views: unified /vocab database with saved views.
```

Typical flow when a branch is ready:

```bash
cd ~/Desktop/Diss/LinguistOS
git switch main
git pull
git merge <branch-name>
# resolve conflicts if any
git push origin main
```

Delete the topic branch locally/remotely after merge if it is no longer needed.

## Day-to-day

**Default:** open `~/Desktop/Diss/LinguistOS` — you are on `main`.

**Side work (research, features, agents):** open the relevant worktree folder in Cursor (File → Open Folder). Commit and push from **that** checkout on its branch:

```bash
cd "$(git worktree list | awk '/research\/my-topic/{print $1; exit}')"  # or paste path from git worktree list
git push origin research/my-topic
```

## Research database

`research/research.db` is gitignored. **Each checkout has its own copy.** Run experiments from the research worktree so results stay with that branch. Copy the DB manually if you need to share history between checkouts.

## Rules of thumb

- **One branch per worktree** — don’t check out the same branch in two folders.
- **One agent / task per worktree** — avoids editing the same files in parallel.
- **Main folder stays on `main`** — topic branches live in side worktrees.
- **Don’t treat example paths as canonical** — use `git worktree list` and your branch name, not a memorised directory.

## Cursor agents

Use `/worktree` in a chat to spin up an isolated checkout for parallel agent work. Each agent gets its own worktree path and topic branch; merge back to `main` with a merge commit when the work is done.
