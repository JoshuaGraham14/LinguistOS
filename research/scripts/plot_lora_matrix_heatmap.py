"""Four-panel held-out adapter--configuration heatmap.

Recreates the supplementary 36-verb OOD matrix figure from the values reported
in Table td-combined.  Outputs PNG and PDF under docs/report-writing/figures/.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "docs" / "report-writing" / "figures"
STEM = "lora_matrix_judge_mainverb_heatmap_4panel_mako"

ADAPTERS = ["Base", "LoRA-with-inject", "LoRA-no-inject"]
CONFIGURATIONS = [
    "Greedy",
    "Greedy + Inject",
    "Soft",
    "Soft + Inject",
    "Neuro",
    "Neuro + Inject",
]

# Rows: adapters; columns: generation configurations. Values are from the
# Spanish 36-verb held-out set (n = 1,116).
MAIN_VERB = np.array(
    [
        [21.5, 75.7, 45.8, 66.8, 69.1, 83.6],
        [77.4, 96.6, 72.0, 88.6, 94.3, 98.6],
        [86.2, 92.9, 84.7, 82.6, 96.6, 97.4],
    ]
)
NATURALNESS = np.array(
    [
        [4.52, 3.92, 3.79, 3.22, 4.29, 3.96],
        [4.54, 4.54, 3.59, 3.81, 4.50, 4.54],
        [4.47, 4.46, 3.78, 3.59, 4.57, 4.50],
    ]
)
GRAMMATICALITY = np.array(
    [
        [4.69, 4.37, 4.34, 3.77, 4.77, 4.43],
        [4.80, 4.89, 4.47, 4.36, 4.90, 4.91],
        [4.75, 4.82, 4.32, 4.11, 4.90, 4.88],
    ]
)
SEMANTIC_COHERENCE = np.array(
    [
        [4.78, 4.33, 4.14, 3.65, 4.60, 4.38],
        [4.76, 4.74, 3.92, 4.14, 4.74, 4.76],
        [4.74, 4.72, 4.09, 3.86, 4.77, 4.70],
    ]
)

C_TEXT = "#2b2b2b"
CMAP = sns.color_palette("mako", as_cmap=True)


def draw_panel(
    ax,
    data: np.ndarray,
    title: str,
    colourbar_label: str,
    vmin: float,
    vmax: float,
    *,
    show_y_labels: bool,
    percentage: bool = False,
) -> None:
    image = ax.imshow(data, cmap=CMAP, vmin=vmin, vmax=vmax, aspect="auto")

    for row_idx, row in enumerate(data):
        for col_idx, value in enumerate(row):
            scaled = (value - vmin) / (vmax - vmin)
            text_colour = "white" if scaled < 0.42 else C_TEXT
            annotation = f"{value:.1f}" if percentage else f"{value:.2f}"
            ax.text(
                col_idx, row_idx, annotation, ha="center", va="center",
                fontsize=10, color=text_colour,
            )

    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=8, color=C_TEXT)
    ax.set_xticks(range(len(CONFIGURATIONS)), CONFIGURATIONS, rotation=24, ha="right")
    ax.set_xlabel("Generation configuration", fontsize=10, color=C_TEXT)
    ax.set_yticks(range(len(ADAPTERS)), ADAPTERS if show_y_labels else [])
    if show_y_labels:
        ax.set_ylabel("Adapter", fontsize=10, color=C_TEXT)
    ax.tick_params(axis="both", length=0, labelsize=9, colors=C_TEXT)

    ax.set_xticks(np.arange(-0.5, len(CONFIGURATIONS), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ADAPTERS), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.1)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_color("#888888")
        spine.set_linewidth(0.8)

    colourbar = ax.figure.colorbar(image, ax=ax, fraction=0.046, pad=0.025)
    colourbar.ax.tick_params(labelsize=9, colors=C_TEXT)
    colourbar.set_label(colourbar_label, fontsize=10, color=C_TEXT)


def main() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 6.25), constrained_layout=True)

    draw_panel(
        axes[0, 0], MAIN_VERB, "(a) Correct main-verb use (%)", "Main verb (%)",
        0, 100, show_y_labels=True, percentage=True,
    )
    draw_panel(
        axes[0, 1], NATURALNESS, "(b) Naturalness (1--5)", "Judge score (1--5)",
        3, 5, show_y_labels=False,
    )
    draw_panel(
        axes[1, 0], GRAMMATICALITY, "(c) Grammaticality (1--5)",
        "Judge score (1--5)", 3, 5, show_y_labels=True,
    )
    draw_panel(
        axes[1, 1], SEMANTIC_COHERENCE, "(d) Semantic coherence (1--5)",
        "Judge score (1--5)", 3, 5, show_y_labels=False,
    )

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{STEM}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {STEM}.png / .pdf")


if __name__ == "__main__":
    main()
