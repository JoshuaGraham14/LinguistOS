"""Diagnostic 3A conditional figures on absolute counts (n out of 4,650).

Y-axis is cell count, not percentage. Several funnel / cascade layouts.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon
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
FIG_W = 8.8
FIG_H = 4.0

# Exact contingency: (2A correct, 3A correct) etc.
DATA = {
    "0.6B": {
        "ok2_ok3": 291,
        "ok2_bad3": 656,   # binding failure
        "bad2_ok3": 403,
        "bad2_bad3": 3300,
    },
    "1.7B": {
        "ok2_ok3": 1965,
        "ok2_bad3": 1248,
        "bad2_ok3": 397,
        "bad2_bad3": 1040,
    },
    "4B": {
        "ok2_ok3": 2445,
        "ok2_bad3": 1311,
        "bad2_ok3": 340,
        "bad2_bad3": 554,
    },
}
MODELS = ["0.6B", "1.7B", "4B"]

COL_USED = "#2ca02c"       # form appears in 3A
COL_BIND = "#d62728"       # known in 2A, missing in 3A
COL_RECOVER = "#1f77b4"    # missed in 2A, appears in 3A
COL_MISS = "#7f7f7f"       # missed in both
COL_TOTAL = "#e0e0e0"      # full pool reference
COL_KNOWN = "#98df8a"      # 2A correct pool (light)


def style_count_ax(ax, ylabel=True):
    ax.set_ylim(0, TOTAL * 1.06)
    ax.set_yticks([0, 1000, 2000, 3000, 4000, TOTAL])
    ax.set_yticklabels(["0", "1,000", "2,000", "3,000", "4,000", "4,650"])
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ylabel:
        ax.set_ylabel("Number of cells")


def annotate_seg(ax, x, y0, h, text, color="black", fontsize=8):
    if h < 180:
        return
    ax.text(x, y0 + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=color, zorder=6)


# ---- Option E: count-scale stacked bar for known-in-2A path only ----------
# Grey full pool to 4650; coloured bar to n(known in 2A), split used vs binding fail.
def option_e_known_path():
    x = np.arange(len(MODELS))
    w = 0.55

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    # full pool reference
    ax.bar(x, [TOTAL] * len(MODELS), width=w, color=COL_TOTAL, zorder=1,
           label="All cells (4,650)")

    used = [DATA[m]["ok2_ok3"] for m in MODELS]
    bind = [DATA[m]["ok2_bad3"] for m in MODELS]
    known = [u + b for u, b in zip(used, bind)]

    b_used = ax.bar(x, used, width=w * 0.72, color=COL_USED, zorder=3,
                    label="Known in 2A and used in sentence")
    b_bind = ax.bar(x, bind, width=w * 0.72, bottom=used, color=COL_BIND, zorder=3,
                    label="Known in 2A but missing from sentence")

    for i, m in enumerate(MODELS):
        ax.text(x[i], known[i] + 80, f"n={known[i]:,} known in 2A",
                ha="center", va="bottom", fontsize=8, color="0.25")
        annotate_seg(ax, x[i], 0, used[i], f"{used[i]:,}\nused", color="white")
        annotate_seg(ax, x[i], used[i], bind[i], f"{bind[i]:,}\nmissed", color="white")

    ax.set_xticks(x)
    ax.set_xticklabels([f"Qwen3 {m}" for m in MODELS])
    style_count_ax(ax)
    ax.legend(loc="upper right", frameon=True, fancybox=False, edgecolor="0.6")
    fig.subplots_adjust(left=0.10, right=0.98, top=0.96, bottom=0.10)
    fig.savefig(out_dir / "diag3a_funnel_known_path.png")
    plt.close(fig)


# ---- Option F: two-stage funnel per model (2A split -> 3A split) -----------
def option_f_two_stage_funnel():
    fig, axes = plt.subplots(1, 3, figsize=(FIG_W, FIG_H), sharey=True)

    for ax, m in zip(axes, MODELS):
        d = DATA[m]
        known = d["ok2_ok3"] + d["ok2_bad3"]
        unknown = d["bad2_ok3"] + d["bad2_bad3"]

        # Stage 1: 2A outcome (centred, full width)
        x1, w1 = 0.0, 0.9
        ax.bar(x1, known, width=w1, color=COL_KNOWN, zorder=3)
        ax.bar(x1, unknown, width=w1, bottom=known, color=COL_MISS, zorder=3, alpha=0.55)
        annotate_seg(ax, x1, 0, known, f"Correct in 2A\n{known:,}", fontsize=7.5)
        if unknown > 280:
            annotate_seg(ax, x1, known, unknown, f"Incorrect\nin 2A\n{unknown:,}",
                         fontsize=7, color="white")

        # Stage 2: 3A outcomes as two narrower columns under each path
        # Left column = from known; right = from unknown
        gap = 0.12
        w2 = 0.38
        x_left = -0.22
        x_right = 0.22

        # Connecting trapezoids (funnel feel)
        # known -> left stack
        trap_k = Polygon(
            [[x1 - w1 / 2, 0], [x1 + w1 / 2, 0],
             [x_left + w2 / 2, -0.02], [x_left - w2 / 2, -0.02]],
            closed=True, facecolor=COL_KNOWN, alpha=0.15, zorder=1,
            transform=ax.get_xaxis_transform(),  # won't work well — use data coords instead
        )
        # Use data-coord connectors between stages instead
        y_top_k = known
        # draw soft wedges in data coords between x≈0.55 and x≈1.4 conceptually
        # Simpler: place stage 2 at x=1.35
        x2l, x2r = 1.25, 1.85
        w2 = 0.48

        # redraw stage 1 at x=0.35
        ax.clear()
        x1 = 0.35
        w1 = 0.7
        ax.bar(x1, known, width=w1, color="#a1d99b", zorder=3, edgecolor="white", linewidth=0.6)
        ax.bar(x1, unknown, width=w1, bottom=known, color="#bdbdbd", zorder=3,
               edgecolor="white", linewidth=0.6)
        annotate_seg(ax, x1, 0, known, f"Correct\nin 2A\n{known:,}", fontsize=7.5)
        if unknown > 300:
            annotate_seg(ax, x1, known, unknown, f"Incorrect\nin 2A\n{unknown:,}",
                         fontsize=7, color="0.15")

        # stage 2 bars
        ax.bar(x2l, d["ok2_ok3"], width=w2, color=COL_USED, zorder=3,
               edgecolor="white", linewidth=0.6)
        ax.bar(x2l, d["ok2_bad3"], width=w2, bottom=d["ok2_ok3"], color=COL_BIND, zorder=3,
               edgecolor="white", linewidth=0.6)
        ax.bar(x2r, d["bad2_ok3"], width=w2, bottom=known, color=COL_RECOVER, zorder=3,
               edgecolor="white", linewidth=0.6)
        ax.bar(x2r, d["bad2_bad3"], width=w2, bottom=known + d["bad2_ok3"], color=COL_MISS,
               zorder=3, edgecolor="white", linewidth=0.6)

        # funnel connectors (known path)
        poly_k = Polygon(
            [
                [x1 + w1 / 2, 0],
                [x1 + w1 / 2, known],
                [x2l - w2 / 2, d["ok2_ok3"] + d["ok2_bad3"]],
                [x2l - w2 / 2, 0],
            ],
            closed=True, facecolor=COL_USED, alpha=0.12, zorder=2,
        )
        ax.add_patch(poly_k)
        # unknown path connector
        poly_u = Polygon(
            [
                [x1 + w1 / 2, known],
                [x1 + w1 / 2, TOTAL],
                [x2r - w2 / 2, TOTAL],
                [x2r - w2 / 2, known],
            ],
            closed=True, facecolor=COL_MISS, alpha=0.12, zorder=2,
        )
        ax.add_patch(poly_u)

        annotate_seg(ax, x2l, 0, d["ok2_ok3"], f"{d['ok2_ok3']:,}\nused",
                     color="white", fontsize=7)
        annotate_seg(ax, x2l, d["ok2_ok3"], d["ok2_bad3"], f"{d['ok2_bad3']:,}\nmissed",
                     color="white", fontsize=7)
        if d["bad2_ok3"] > 220:
            annotate_seg(ax, x2r, known, d["bad2_ok3"], f"{d['bad2_ok3']:,}",
                         color="white", fontsize=7)
        if d["bad2_bad3"] > 280:
            annotate_seg(ax, x2r, known + d["bad2_ok3"], d["bad2_bad3"],
                         f"{d['bad2_bad3']:,}", color="white", fontsize=7)

        # dashed total reference
        ax.axhline(TOTAL, color="0.7", linestyle=":", linewidth=0.9, zorder=0)
        ax.set_xlim(-0.15, 2.25)
        ax.set_xticks([x1, (x2l + x2r) / 2])
        ax.set_xticklabels(["2A", "3A sentence"])
        ax.set_title(f"Qwen3 {m}", fontsize=10, pad=4)
        style_count_ax(ax, ylabel=(ax is axes[0]))

    # shared legend
    handles = [
        mpatches.Patch(color="#a1d99b", label="Correct in 2A"),
        mpatches.Patch(color="#bdbdbd", label="Incorrect in 2A"),
        mpatches.Patch(color=COL_USED, label="Form appears in sentence"),
        mpatches.Patch(color=COL_BIND, label="Known in 2A, missing in sentence"),
        mpatches.Patch(color=COL_RECOVER, label="Missed in 2A, appears in sentence"),
        mpatches.Patch(color=COL_MISS, label="Missed in both"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=True,
               fancybox=False, edgecolor="0.6", fontsize=8,
               bbox_to_anchor=(0.5, 1.02))
    fig.subplots_adjust(left=0.08, right=0.99, top=0.82, bottom=0.12, wspace=0.18)
    fig.savefig(out_dir / "diag3a_funnel_two_stage.png")
    plt.close(fig)


# ---- Option G: alluvial / sankey-lite, one panel focused on 1.7B (+ small others)
def option_g_alluvial():
    """Per model: left stack = 2A status (to 4650), right stack = 3A×2A joint,
    with flowing bands between them."""
    fig, axes = plt.subplots(1, 3, figsize=(FIG_W, FIG_H), sharey=True)

    for ax, m in zip(axes, MODELS):
        d = DATA[m]
        known = d["ok2_ok3"] + d["ok2_bad3"]
        unknown = TOTAL - known

        xl, xr, wl, wr = 0.0, 1.4, 0.55, 0.55

        # Left: 2A
        ax.bar(xl, known, width=wl, color="#a1d99b", zorder=3, edgecolor="white")
        ax.bar(xl, unknown, width=wl, bottom=known, color="#bdbdbd", zorder=3, edgecolor="white")
        annotate_seg(ax, xl, 0, known, f"{known:,}\ncorrect\nin 2A", fontsize=7.5)
        if unknown > 300:
            annotate_seg(ax, xl, known, unknown, f"{unknown:,}\nincorrect\nin 2A", fontsize=7)

        # Right: four outcomes stacked in order matching flows
        # bottom→top: ok2_ok3, ok2_bad3, bad2_ok3, bad2_bad3
        segs = [
            (d["ok2_ok3"], COL_USED, "used"),
            (d["ok2_bad3"], COL_BIND, "missed"),
            (d["bad2_ok3"], COL_RECOVER, "recovered"),
            (d["bad2_bad3"], COL_MISS, "missed"),
        ]
        y = 0
        for h, col, _ in segs:
            ax.bar(xr, h, width=wr, bottom=y, color=col, zorder=3, edgecolor="white")
            annotate_seg(ax, xr, y, h, f"{h:,}", color="white" if h > 350 else "black",
                         fontsize=7)
            y += h

        # Flow bands
        # known -> ok2_ok3 and ok2_bad3
        def band(y0_l, h, y0_r, color):
            if h <= 0:
                return
            xs = [xl + wl / 2, xr - wr / 2, xr - wr / 2, xl + wl / 2]
            ys = [y0_l, y0_r, y0_r + h, y0_l + h]
            ax.add_patch(Polygon(list(zip(xs, ys)), closed=True,
                                 facecolor=color, alpha=0.22, zorder=2, linewidth=0))

        band(0, d["ok2_ok3"], 0, COL_USED)
        band(d["ok2_ok3"], d["ok2_bad3"], d["ok2_ok3"], COL_BIND)
        band(known, d["bad2_ok3"], known, COL_RECOVER)
        band(known + d["bad2_ok3"], d["bad2_bad3"], known + d["bad2_ok3"], COL_MISS)

        ax.axhline(TOTAL, color="0.7", linestyle=":", linewidth=0.9, zorder=0)
        ax.set_xlim(-0.45, 1.85)
        ax.set_xticks([xl, xr])
        ax.set_xticklabels(["Diagnostic 2A", "Diagnostic 3A"])
        ax.set_title(f"Qwen3 {m}", fontsize=10, pad=4)
        style_count_ax(ax, ylabel=(ax is axes[0]))

    handles = [
        mpatches.Patch(color=COL_USED, label="Correct in 2A → appears in sentence"),
        mpatches.Patch(color=COL_BIND, label="Correct in 2A → missing from sentence"),
        mpatches.Patch(color=COL_RECOVER, label="Incorrect in 2A → appears in sentence"),
        mpatches.Patch(color=COL_MISS, label="Incorrect in 2A → missing from sentence"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=True,
               fancybox=False, edgecolor="0.6", fontsize=8,
               bbox_to_anchor=(0.5, 1.03))
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.12, wspace=0.16)
    fig.savefig(out_dir / "diag3a_funnel_alluvial.png")
    plt.close(fig)


# ---- Option H: single-model deep dive for 1.7B (clearest funnel) ----------
def option_h_17b_focus():
    m = "1.7B"
    d = DATA[m]
    known = d["ok2_ok3"] + d["ok2_bad3"]
    unknown = TOTAL - known

    fig, ax = plt.subplots(figsize=(FIG_W * 0.85, FIG_H + 0.3))
    xl, xm, xr = 0.0, 1.3, 2.6
    w = 0.7

    # Stage 0: all cells
    ax.bar(xl, TOTAL, width=w, color=COL_TOTAL, zorder=3, edgecolor="white")
    annotate_seg(ax, xl, 0, TOTAL, f"All cells\n{TOTAL:,}", fontsize=9)

    # Stage 1: 2A split
    ax.bar(xm, known, width=w, color="#a1d99b", zorder=3, edgecolor="white")
    ax.bar(xm, unknown, width=w, bottom=known, color="#bdbdbd", zorder=3, edgecolor="white")
    annotate_seg(ax, xm, 0, known, f"Correct in 2A\n{known:,}", fontsize=8.5)
    annotate_seg(ax, xm, known, unknown, f"Incorrect in 2A\n{unknown:,}", fontsize=8)

    # Stage 2: 3A outcomes — two bars side by side at right
    w2 = 0.55
    x_k, x_u = xr - 0.32, xr + 0.32
    ax.bar(x_k, d["ok2_ok3"], width=w2, color=COL_USED, zorder=3, edgecolor="white")
    ax.bar(x_k, d["ok2_bad3"], width=w2, bottom=d["ok2_ok3"], color=COL_BIND,
           zorder=3, edgecolor="white")
    ax.bar(x_u, d["bad2_ok3"], width=w2, bottom=known, color=COL_RECOVER,
           zorder=3, edgecolor="white")
    ax.bar(x_u, d["bad2_bad3"], width=w2, bottom=known + d["bad2_ok3"], color=COL_MISS,
           zorder=3, edgecolor="white")

    annotate_seg(ax, x_k, 0, d["ok2_ok3"], f"{d['ok2_ok3']:,}\nused\n(61%)",
                 color="white", fontsize=8)
    annotate_seg(ax, x_k, d["ok2_ok3"], d["ok2_bad3"],
                 f"{d['ok2_bad3']:,}\nmissed\n(39%)", color="white", fontsize=8)
    annotate_seg(ax, x_u, known, d["bad2_ok3"], f"{d['bad2_ok3']:,}\n(28%)",
                 color="white", fontsize=7.5)
    annotate_seg(ax, x_u, known + d["bad2_ok3"], d["bad2_bad3"],
                 f"{d['bad2_bad3']:,}\n(72%)", color="white", fontsize=7.5)

    # Connectors
    def band(x0, x1, y0_l, y1_l, y0_r, y1_r, color, alpha=0.18):
        ax.add_patch(Polygon(
            [[x0, y0_l], [x0, y1_l], [x1, y1_r], [x1, y0_r]],
            closed=True, facecolor=color, alpha=alpha, zorder=2, linewidth=0,
        ))

    band(xl + w / 2, xm - w / 2, 0, TOTAL, 0, TOTAL, "0.6", alpha=0.10)
    band(xm + w / 2, x_k - w2 / 2, 0, known, 0, known, COL_USED, alpha=0.15)
    band(xm + w / 2, x_u - w2 / 2, known, TOTAL, known, TOTAL, COL_MISS, alpha=0.12)

    ax.set_xlim(-0.55, 3.3)
    ax.set_xticks([xl, xm, (x_k + x_u) / 2])
    ax.set_xticklabels(["All cells", "Split by 2A", "Split by 3A sentence"])
    style_count_ax(ax)
    ax.set_title("Qwen3 1.7B — conditional path from paradigm to sentence",
                 fontsize=10, pad=6)

    handles = [
        mpatches.Patch(color=COL_USED, label="Appears in sentence (given correct in 2A)"),
        mpatches.Patch(color=COL_BIND, label="Missing from sentence (given correct in 2A)"),
        mpatches.Patch(color=COL_RECOVER, label="Appears in sentence (given incorrect in 2A)"),
        mpatches.Patch(color=COL_MISS, label="Missing from sentence (given incorrect in 2A)"),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=True, fancybox=False,
              edgecolor="0.6", fontsize=8)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.90, bottom=0.10)
    fig.savefig(out_dir / "diag3a_funnel_17b.png")
    plt.close(fig)


if __name__ == "__main__":
    option_e_known_path()
    option_f_two_stage_funnel()
    option_g_alluvial()
    option_h_17b_focus()
    print("Wrote:")
    for name in (
        "diag3a_funnel_known_path",
        "diag3a_funnel_two_stage",
        "diag3a_funnel_alluvial",
        "diag3a_funnel_17b",
    ):
        print(f"  figures/{name}.png")
