"""Frontier ceiling: LoRA-A Neuro+inject vs GPT-5.5 (OOD n=1,116).

Outputs PNGs to research/diagnostics/figures/ using the same geometry/style
conventions as figure_scripts/diag1a_accuracy_figures.ipynb.

Quality from cluster DBs (full OOD). Cost: opportunistic wall latency from
generation timestamps; GPT-$ from a 10-call live usage sample extrapolated
to 1,116 cells at gpt-5.5 short-context rates ($5/$30 per 1M tokens).
LoRA-$ is A30 rental opportunity cost at $0.35/GPU-h on timed gen wall.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

out_dir = Path(__file__).resolve().parent.parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(plt.rcParamsDefault)
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
    "font.size": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
})

BAR_W = 0.3
PAIR_GAP = 0.025
PAIR_STEP = BAR_W + PAIR_GAP
INNER_GAP = 0.55
FIG_W = 8.8
FIG_H = 3.65
off_l, off_r = -PAIR_STEP / 2, PAIR_STEP / 2

COL_LORA = "#1f77b4"   # C0 — local LoRA-A Neuro+inject
COL_GPT = "#ff7f0e"    # C1 — GPT-5.5
LAB_LORA = "LoRA-A + Neuro+inject"
LAB_GPT = "GPT-5.5 (vanilla Fix-B)"

# ---- Data (spanish_lora_ood_n36, n=1116) --------------------------------
QUALITY_PCT = {
    # metric: (lora, gpt)
    "Form": (100.0, 100.0),
    "corr MV": (98.2, 98.7),
    "Unique%": (98.2, 99.5),
    "LT": (100.0, 100.0),
}
JUDGE = {
    "G": (4.89, 4.98),
    "N": (4.51, 4.87),
    "S": (4.75, 4.96),
}
ABSENT = (0.0, 0.0)  # both zero; shown only in annotation if needed

# Latency: opportunistic ms/sent from sentence created_at span / (n-1).
LATENCY_MS = (8833.0, 2642.9)
REL_COST = (72.0, 21.5)  # vs Base 1.7B vanilla controlled 122.66 ms
# Dollar estimates for one full OOD generation pass (n=1116).
COST_USD = (0.96, 3.49)  # LoRA: 2.74 GPU-h × $0.35; GPT: usage sample × rates


def style_ax(ax, ylabel=None, ymax=108, yticks=None):
    ax.set_ylim(0, ymax)
    if yticks is not None:
        ax.set_yticks(yticks)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel)


def label_bars(ax, bars, fmt="{:.0f}%", dy=0.9, fontsize=8):
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + dy,
            fmt.format(h),
            ha="center",
            va="bottom",
            fontsize=fontsize,
            zorder=5,
        )


def paired_positions(n):
    """Centres for n metric groups with INNER_GAP between groups."""
    step = PAIR_STEP + INNER_GAP
    return np.arange(n) * step


def fig_quality_pct():
    """Form / corr MV / Unique% / LT — grouped bars."""
    metrics = list(QUALITY_PCT.keys())
    x = paired_positions(len(metrics))
    lora = [QUALITY_PCT[m][0] for m in metrics]
    gpt = [QUALITY_PCT[m][1] for m in metrics]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    b1 = ax.bar(x + off_l, lora, width=BAR_W, color=COL_LORA, label=LAB_LORA, zorder=3)
    b2 = ax.bar(x + off_r, gpt, width=BAR_W, color=COL_GPT, label=LAB_GPT, zorder=3)
    label_bars(ax, b1, fmt="{:.1f}%", dy=0.7)
    label_bars(ax, b2, fmt="{:.1f}%", dy=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    style_ax(ax, ylabel="Score (%)", ymax=108, yticks=[0, 25, 50, 75, 100])
    ax.set_xlim(x[0] + off_l - BAR_W / 2 - 0.15, x[-1] + off_r + BAR_W / 2 + 0.15)
    ax.legend(loc="lower right", frameon=True, fancybox=False, edgecolor="0.6")
    fig.subplots_adjust(left=0.09, right=0.99, top=0.96, bottom=0.12)
    fig.savefig(out_dir / "frontier_quality_pct.png")
    plt.close(fig)


def fig_judge_scores():
    """LLM-judge G / N / S on 1–5 scale."""
    metrics = list(JUDGE.keys())
    x = paired_positions(len(metrics))
    lora = [JUDGE[m][0] for m in metrics]
    gpt = [JUDGE[m][1] for m in metrics]
    full_labels = {"G": "Grammaticality", "N": "Naturalness", "S": "Semantic coherence"}

    fig, ax = plt.subplots(figsize=(FIG_W * 0.78, FIG_H))
    b1 = ax.bar(x + off_l, lora, width=BAR_W, color=COL_LORA, label=LAB_LORA, zorder=3)
    b2 = ax.bar(x + off_r, gpt, width=BAR_W, color=COL_GPT, label=LAB_GPT, zorder=3)
    label_bars(ax, b1, fmt="{:.2f}", dy=0.05, fontsize=8)
    label_bars(ax, b2, fmt="{:.2f}", dy=0.05, fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([full_labels[m] for m in metrics])
    style_ax(ax, ylabel="LLM-judge score (1–5)", ymax=5.35, yticks=[1, 2, 3, 4, 5])
    ax.set_xlim(x[0] + off_l - BAR_W / 2 - 0.2, x[-1] + off_r + BAR_W / 2 + 0.2)
    ax.legend(loc="lower right", frameon=True, fancybox=False, edgecolor="0.6")
    fig.subplots_adjust(left=0.11, right=0.99, top=0.96, bottom=0.14)
    fig.savefig(out_dir / "frontier_judge_scores.png")
    plt.close(fig)


def fig_cost_latency():
    """Generation latency (s/sent) and relative cost vs Base-vanilla."""
    fig, axes = plt.subplots(1, 2, figsize=(FIG_W, FIG_H))

    # Panel A: latency in seconds
    ax = axes[0]
    vals_s = [LATENCY_MS[0] / 1000.0, LATENCY_MS[1] / 1000.0]
    x = np.array([0.0, PAIR_STEP + INNER_GAP])
    bars = ax.bar(x, vals_s, width=BAR_W * 1.35, color=[COL_LORA, COL_GPT], zorder=3)
    for bar, v in zip(bars, vals_s):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 0.18,
            f"{v:.2f}s",
            ha="center",
            va="bottom",
            fontsize=8,
            zorder=5,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([LAB_LORA.replace(" + ", "\n+ "), LAB_GPT.replace(" (", "\n(")])
    style_ax(ax, ylabel="Latency (s / sentence)", ymax=max(vals_s) * 1.18)
    ax.set_xlim(x[0] - 0.45, x[-1] + 0.45)

    # Panel B: relative cost
    ax = axes[1]
    bars = ax.bar(x, REL_COST, width=BAR_W * 1.35, color=[COL_LORA, COL_GPT], zorder=3)
    for bar, v in zip(bars, REL_COST):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 1.5,
            f"{v:.0f}×",
            ha="center",
            va="bottom",
            fontsize=8,
            zorder=5,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([LAB_LORA.replace(" + ", "\n+ "), LAB_GPT.replace(" (", "\n(")])
    style_ax(ax, ylabel="Relative cost vs Base 1.7B vanilla", ymax=max(REL_COST) * 1.18)
    ax.set_xlim(x[0] - 0.45, x[-1] + 0.45)
    ax.axhline(1.0, color="0.55", linestyle=":", linewidth=0.9, zorder=1)

    fig.subplots_adjust(left=0.08, right=0.99, top=0.96, bottom=0.18, wspace=0.32)
    fig.savefig(out_dir / "frontier_cost_latency.png")
    plt.close(fig)


def fig_cost_dollars():
    """Estimated $ for one full OOD generation pass (n=1,116)."""
    fig, ax = plt.subplots(figsize=(FIG_W * 0.62, FIG_H))
    x = np.array([0.0, PAIR_STEP + INNER_GAP])
    bars = ax.bar(x, COST_USD, width=BAR_W * 1.35, color=[COL_LORA, COL_GPT], zorder=3)
    for bar, v in zip(bars, COST_USD):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 0.08,
            f"${v:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
            zorder=5,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([LAB_LORA.replace(" + ", "\n+ "), LAB_GPT.replace(" (", "\n(")])
    style_ax(ax, ylabel="Estimated cost for OOD gen (n=1,116)", ymax=max(COST_USD) * 1.22)
    ax.set_xlim(x[0] - 0.5, x[-1] + 0.5)
    # Footnote-style note under axis via text
    ax.text(
        0.5,
        -0.22,
        "LoRA: A30 @ $0.35/h on gen wall · GPT: usage sample × $5/$30 per 1M tokens",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=7.5,
        color="0.35",
    )
    fig.subplots_adjust(left=0.14, right=0.98, top=0.96, bottom=0.22)
    fig.savefig(out_dir / "frontier_cost_dollars.png")
    plt.close(fig)


def fig_quality_cost_overview():
    """Two-panel overview: constraint fidelity vs estimated dollar cost."""
    fig, axes = plt.subplots(1, 2, figsize=(FIG_W, FIG_H))

    # Left: Form + corr MV
    ax = axes[0]
    metrics = ["Form", "corr MV"]
    lora = [QUALITY_PCT[m][0] for m in metrics]
    gpt = [QUALITY_PCT[m][1] for m in metrics]
    x = paired_positions(len(metrics))
    b1 = ax.bar(x + off_l, lora, width=BAR_W, color=COL_LORA, label=LAB_LORA, zorder=3)
    b2 = ax.bar(x + off_r, gpt, width=BAR_W, color=COL_GPT, label=LAB_GPT, zorder=3)
    label_bars(ax, b1, fmt="{:.1f}%", dy=0.7)
    label_bars(ax, b2, fmt="{:.1f}%", dy=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    style_ax(ax, ylabel="Score (%)", ymax=108, yticks=[0, 25, 50, 75, 100])
    ax.set_xlim(x[0] + off_l - BAR_W / 2 - 0.2, x[-1] + off_r + BAR_W / 2 + 0.2)
    ax.legend(loc="lower right", frameon=True, fancybox=False, edgecolor="0.6", fontsize=8)

    # Right: dollar cost
    ax = axes[1]
    x2 = np.array([0.0, PAIR_STEP + INNER_GAP])
    bars = ax.bar(x2, COST_USD, width=BAR_W * 1.35, color=[COL_LORA, COL_GPT], zorder=3)
    for bar, v in zip(bars, COST_USD):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 0.08,
            f"${v:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
            zorder=5,
        )
    ax.set_xticks(x2)
    ax.set_xticklabels(["LoRA-A\nNeuro+inject", "GPT-5.5\nvanilla"])
    style_ax(ax, ylabel="Est. $ / OOD gen (n=1,116)", ymax=max(COST_USD) * 1.25)
    ax.set_xlim(x2[0] - 0.45, x2[-1] + 0.45)

    fig.subplots_adjust(left=0.08, right=0.99, top=0.96, bottom=0.14, wspace=0.30)
    fig.savefig(out_dir / "frontier_quality_cost_overview.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_quality_pct()
    fig_judge_scores()
    fig_cost_latency()
    fig_cost_dollars()
    fig_quality_cost_overview()
    print(f"Wrote figures → {out_dir}")
    for name in (
        "frontier_quality_pct.png",
        "frontier_judge_scores.png",
        "frontier_cost_latency.png",
        "frontier_cost_dollars.png",
        "frontier_quality_cost_overview.png",
    ):
        print(f"  {name}")
