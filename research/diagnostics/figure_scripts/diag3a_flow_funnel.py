"""Diagnostic 3A conditional flow (sankey/funnel) figures on absolute counts.

Left node = 2A outcome split (green = correct, red = incorrect), scaled to 4,650.
Curved bands flow into 3A outcomes:
  correct-in-2A  -> green shades (used vs binding-gap)
  incorrect-in-2A -> warm shades (recovered vs missed-both)
Each flow/node is labelled with count and conditional percentage.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
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

TOTAL = 4650

DATA = {
    "0.6B": {"ok2_ok3": 291, "ok2_bad3": 656, "bad2_ok3": 403, "bad2_bad3": 3300},
    "1.7B": {"ok2_ok3": 1965, "ok2_bad3": 1248, "bad2_ok3": 397, "bad2_bad3": 1040},
    "4B":   {"ok2_ok3": 2445, "ok2_bad3": 1311, "bad2_ok3": 340, "bad2_bad3": 554},
}
MODELS = ["0.6B", "1.7B", "4B"]

# Correct-in-2A node + green shades
COL_CORRECT = "#74c476"          # 2A correct node
COL_USED = "#238b45"             # correct -> appears in sentence
COL_BIND = "#c7e9c0"             # correct -> missing (binding gap), pale green
# Incorrect-in-2A node + warm shades
COL_INCORRECT = "#fb6a4a"        # 2A incorrect node
COL_RECOVER = "#fdae6b"          # incorrect -> appears (orange)
COL_MISS = "#a50f15"             # incorrect -> missing (deep red)


def style_count_ax(ax, ylabel=True):
    ax.set_ylim(0, TOTAL * 1.04)
    ax.set_yticks([0, 1000, 2000, 3000, 4000, TOTAL])
    ax.set_yticklabels(["0", "1,000", "2,000", "3,000", "4,000", "4,650"])
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if ylabel:
        ax.set_ylabel("Number of cells")


def sankey_band(ax, x0, x1, yl0, yl1, yr0, yr1, color, alpha=0.6):
    """Filled cubic-bezier band from left edge (x0, yl0..yl1) to right (x1, yr0..yr1)."""
    xc = (x0 + x1) / 2.0
    verts = [
        (x0, yl1),
        (xc, yl1), (xc, yr1), (x1, yr1),   # top curve L->R
        (x1, yr0),                          # down right edge
        (xc, yr0), (xc, yl0), (x0, yl0),    # bottom curve R->L
        (x0, yl1),                          # close
    ]
    codes = [
        MPath.MOVETO,
        MPath.CURVE4, MPath.CURVE4, MPath.CURVE4,
        MPath.LINETO,
        MPath.CURVE4, MPath.CURVE4, MPath.CURVE4,
        MPath.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none",
                           alpha=alpha, zorder=2))


def draw_model(ax, m, title):
    d = DATA[m]
    known = d["ok2_ok3"] + d["ok2_bad3"]
    unknown = d["bad2_ok3"] + d["bad2_bad3"]

    x_lnode = (0.0, 0.5)        # left node (2A)
    x_rnode = (1.75, 1.99)      # right node (3A)
    xl = x_lnode[1]
    xr = x_rnode[0]
    nodew = x_lnode[1] - x_lnode[0]

    # ---- Left node: 2A split (bottom correct, top incorrect) ----
    ax.add_patch(plt.Rectangle((x_lnode[0], 0), nodew, known,
                               facecolor=COL_CORRECT, edgecolor="white", lw=0.8, zorder=4))
    ax.add_patch(plt.Rectangle((x_lnode[0], known), nodew, unknown,
                               facecolor=COL_INCORRECT, edgecolor="white", lw=0.8, zorder=4))

    # ---- Right nodes: 4 outcomes (bottom->top) ----
    r_y = 0.0
    right_segments = [
        (d["ok2_ok3"], COL_USED),
        (d["ok2_bad3"], COL_BIND),
        (d["bad2_ok3"], COL_RECOVER),
        (d["bad2_bad3"], COL_MISS),
    ]
    right_bounds = []
    for h, col in right_segments:
        ax.add_patch(plt.Rectangle((x_rnode[0], r_y), nodew, h,
                                   facecolor=col, edgecolor="white", lw=0.8, zorder=4))
        right_bounds.append((r_y, r_y + h))
        r_y += h

    # ---- Flows ----
    # correct path (green shades): leaves left 0..known
    l_y = 0.0
    sankey_band(ax, xl, xr, l_y, l_y + d["ok2_ok3"],
                right_bounds[0][0], right_bounds[0][1], COL_USED, alpha=0.55)
    l_y += d["ok2_ok3"]
    sankey_band(ax, xl, xr, l_y, l_y + d["ok2_bad3"],
                right_bounds[1][0], right_bounds[1][1], COL_BIND, alpha=0.7)
    l_y += d["ok2_bad3"]
    # incorrect path (warm): leaves left known..4650
    sankey_band(ax, xl, xr, l_y, l_y + d["bad2_ok3"],
                right_bounds[2][0], right_bounds[2][1], COL_RECOVER, alpha=0.6)
    l_y += d["bad2_ok3"]
    sankey_band(ax, xl, xr, l_y, l_y + d["bad2_bad3"],
                right_bounds[3][0], right_bounds[3][1], COL_MISS, alpha=0.5)

    # ---- Labels ----
    pct_known = known / TOTAL * 100
    pct_unknown = unknown / TOTAL * 100
    lcx = np.mean(x_lnode)
    if known > 900:
        ax.text(lcx, known / 2, f"Correct\nin 2A\n{known:,} ({pct_known:.0f}%)",
                ha="center", va="center", fontsize=7.5, color="white", zorder=6)
    else:
        ax.text(lcx, known / 2, f"{known:,}\n({pct_known:.0f}%)",
                ha="center", va="center", fontsize=7, color="white", zorder=6)
    if unknown > 900:
        ax.text(lcx, known + unknown / 2,
                f"Incorrect\nin 2A\n{unknown:,} ({pct_unknown:.0f}%)",
                ha="center", va="center", fontsize=7.5, color="white", zorder=6)
    else:
        ax.text(lcx, known + unknown / 2, f"{unknown:,}\n({pct_unknown:.0f}%)",
                ha="center", va="center", fontsize=7, color="white", zorder=6)

    # right labels: count + conditional %; dark text on pale segments
    rcx = np.mean(x_rnode)
    cond = [
        (d["ok2_ok3"], d["ok2_ok3"] / known * 100, "white"),
        (d["ok2_bad3"], d["ok2_bad3"] / known * 100, "0.15"),
        (d["bad2_ok3"], d["bad2_ok3"] / unknown * 100, "0.15"),
        (d["bad2_bad3"], d["bad2_bad3"] / unknown * 100, "white"),
    ]
    for (b0, b1), (cnt, pct, tcol) in zip(right_bounds, cond):
        h = b1 - b0
        if h > 430:
            ax.text(rcx, (b0 + b1) / 2, f"{cnt:,}\n({pct:.0f}%)", ha="center",
                    va="center", fontsize=7, color=tcol, zorder=6)
        elif h > 250:
            ax.text(rcx, (b0 + b1) / 2, f"{cnt:,} ({pct:.0f}%)", ha="center",
                    va="center", fontsize=6.3, color=tcol, zorder=6)
        else:
            ax.text(x_rnode[1] + 0.03, (b0 + b1) / 2, f"{cnt:,} ({pct:.0f}%)",
                    ha="left", va="center", fontsize=6.8, color="0.2", zorder=6)

    ax.axhline(TOTAL, color="0.75", linestyle=":", linewidth=0.9, zorder=0)
    ax.set_xlim(-0.05, 2.34)
    ax.set_xticks([np.mean(x_lnode), np.mean(x_rnode)])
    ax.set_xticklabels(["Diagnostic 2A", "Diagnostic 3A"])
    ax.set_title(title, fontsize=10, pad=4)


def main():
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 4.6), sharey=True)
    for ax, m in zip(axes, MODELS):
        draw_model(ax, m, f"Qwen3 {m}")
        style_count_ax(ax, ylabel=(ax is axes[0]))

    handles = [
        mpatches.Patch(color=COL_USED, label="Correct in 2A, appears in sentence"),
        mpatches.Patch(color=COL_BIND, label="Correct in 2A, missing (binding gap)"),
        mpatches.Patch(color=COL_RECOVER, label="Incorrect in 2A, appears in sentence"),
        mpatches.Patch(color=COL_MISS, label="Incorrect in 2A, missing"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=True,
               fancybox=False, edgecolor="0.6", fontsize=8.5,
               bbox_to_anchor=(0.5, 1.05))
    fig.subplots_adjust(left=0.07, right=0.99, top=0.80, bottom=0.09, wspace=0.14)
    fig.savefig(out_dir / "diag3a_flow_funnel.png")
    plt.close(fig)
    print("Wrote figures/diag3a_flow_funnel.png")


if __name__ == "__main__":
    main()
