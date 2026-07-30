"""Diagnostic 3A conditional-on-2A figures (several options to choose from).

Outputs PNGs to research/diagnostics/figures/ using the same geometry/style
conventions as figure_scripts/diag1a_accuracy_figures.ipynb.
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

# ---- Data --------------------------------------------------------------
# P(gold form appears in 3A sentence | status in 2A), as percentages.
MODELS = ["0.6B", "1.7B", "4B"]
GIVEN_CORRECT = {"0.6B": 31, "1.7B": 61, "4B": 65}      # 3A correct | 2A correct
GIVEN_INCORRECT = {"0.6B": 11, "1.7B": 28, "4B": 38}    # 3A correct | 2A incorrect
N_CORRECT = {"0.6B": 947, "1.7B": 3213, "4B": 3756}
N_INCORRECT = {"0.6B": 3703, "1.7B": 1437, "4B": 894}

COL_KNEW = "#2ca02c"      # green: knew it in 2A
COL_MISSED = "#d62728"    # red: missed it in 2A


def style_ax(ax, ylabel=None):
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel)


def label_bars(ax, bars, fmt="{:.0f}%", dy=0.9):
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + dy, fmt.format(h),
                ha="center", va="bottom", fontsize=8, zorder=5)


# ---- Option A: grouped bars, conditional success given 2A correct/incorrect
def option_a():
    x = np.arange(len(MODELS)) * (2 * PAIR_STEP + INNER_GAP)
    correct = [GIVEN_CORRECT[m] for m in MODELS]
    incorrect = [GIVEN_INCORRECT[m] for m in MODELS]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    b1 = ax.bar(x + off_l, correct, width=BAR_W, color=COL_KNEW,
                label="Given correct in 2A", zorder=3)
    b2 = ax.bar(x + off_r, incorrect, width=BAR_W, color=COL_MISSED,
                label="Given incorrect in 2A", zorder=3)
    label_bars(ax, b1)
    label_bars(ax, b2)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Qwen3 {m}" for m in MODELS])
    style_ax(ax, ylabel="3A form accuracy (%)")
    ax.set_xlim(x[0] + off_l - BAR_W / 2 - 0.12, x[-1] + off_r + BAR_W / 2 + 0.12)
    ax.legend(loc="upper left", frameon=True, fancybox=False, edgecolor="0.6",
              title="Diagnostic 2A outcome")
    fig.subplots_adjust(left=0.09, right=0.99, top=0.96, bottom=0.10)
    fig.savefig(out_dir / "diag3a_conditional_grouped.png")
    plt.close(fig)


# ---- Option B: binding-failure focus (failure rate GIVEN 2A correct) --------
def option_b():
    x = np.arange(len(MODELS)) * (PAIR_STEP + INNER_GAP)
    fail = [100 - GIVEN_CORRECT[m] for m in MODELS]  # knew it, didn't use it

    fig, ax = plt.subplots(figsize=(FIG_W * 0.7, FIG_H))
    bars = ax.bar(x, fail, width=BAR_W, color=COL_MISSED, zorder=3)
    label_bars(ax, bars)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Qwen3 {m}" for m in MODELS])
    style_ax(ax, ylabel="Binding failure rate (%)")
    ax.set_xlim(x[0] - BAR_W / 2 - 0.2, x[-1] + BAR_W / 2 + 0.2)
    ax.set_title("Forms known in 2A but missing from the 3A sentence",
                 fontsize=9, pad=6)
    fig.subplots_adjust(left=0.12, right=0.98, top=0.90, bottom=0.10)
    fig.savefig(out_dir / "diag3a_binding_failure.png")
    plt.close(fig)


# ---- Option C: 100% stacked bars, full 2x2 split ---------------------------
def option_c():
    x = np.arange(len(MODELS)) * (2 * PAIR_STEP + INNER_GAP)
    labels = ["Given correct in 2A", "Given incorrect in 2A"]
    used = {"Given correct in 2A": [GIVEN_CORRECT[m] for m in MODELS],
            "Given incorrect in 2A": [GIVEN_INCORRECT[m] for m in MODELS]}

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    for i, lab in enumerate(labels):
        off = off_l if i == 0 else off_r
        u = used[lab]
        nu = [100 - v for v in u]
        b_used = ax.bar(x + off, u, width=BAR_W, color=COL_KNEW,
                        zorder=3, label="Form appears in sentence" if i == 0 else None)
        ax.bar(x + off, nu, width=BAR_W, bottom=u, color=COL_MISSED,
               zorder=3, label="Form missing from sentence" if i == 0 else None)
        label_bars(ax, b_used, dy=-11)
        for xi in x:
            ax.text(xi + off, 104, lab.split()[1][:4], ha="center",
                    va="bottom", fontsize=7, color="0.35")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Qwen3 {m}" for m in MODELS])
    style_ax(ax, ylabel="Share of cells (%)")
    ax.set_xlim(x[0] + off_l - BAR_W / 2 - 0.12, x[-1] + off_r + BAR_W / 2 + 0.12)
    ax.legend(loc="lower right", frameon=True, fancybox=False, edgecolor="0.6")
    fig.subplots_adjust(left=0.09, right=0.99, top=0.96, bottom=0.10)
    fig.savefig(out_dir / "diag3a_conditional_stacked.png")
    plt.close(fig)


# ---- Option D: slopegraph, 2A -> 3A conditional success --------------------
def option_d():
    fig, ax = plt.subplots(figsize=(FIG_W * 0.62, FIG_H))
    colours = {"0.6B": "#d62728", "1.7B": "#ff7f0e", "4B": "#2ca02c"}
    x0, x1 = 0.0, 1.0
    for m in MODELS:
        y0 = GIVEN_CORRECT[m]
        y1 = GIVEN_INCORRECT[m]
        ax.plot([x0, x1], [y0, y1], "-o", color=colours[m], linewidth=2,
                markersize=6, zorder=3, label=f"Qwen3 {m}")
        ax.text(x0 - 0.04, y0, f"{y0}%", ha="right", va="center", fontsize=8)
        ax.text(x1 + 0.04, y1, f"{y1}%", ha="left", va="center", fontsize=8)
    ax.set_xticks([x0, x1])
    ax.set_xticklabels(["Correct in 2A", "Incorrect in 2A"])
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_ylabel("3A form accuracy (%)")
    ax.legend(loc="upper right", frameon=True, fancybox=False, edgecolor="0.6")
    fig.subplots_adjust(left=0.12, right=0.98, top=0.96, bottom=0.10)
    fig.savefig(out_dir / "diag3a_conditional_slope.png")
    plt.close(fig)


if __name__ == "__main__":
    option_a()
    option_b()
    option_c()
    option_d()
    print("Wrote:")
    for name in ("diag3a_conditional_grouped", "diag3a_binding_failure",
                 "diag3a_conditional_stacked", "diag3a_conditional_slope"):
        print(f"  figures/{name}.png")
