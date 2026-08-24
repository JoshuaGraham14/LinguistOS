"""Cost figures for the computational-cost section.

Reads the controlled calibration JSONs written by cost_cal_arm.sh and pairs
them with the OOD quality numbers from the 36-verb held-out evaluation.

Outputs (PNG + PDF) into docs/report-writing/figures/:
  cost_mainverb_vs_latency   quality against latency, log x
  cost_latency_ladder        latency ranking, log x
  cost_marginal_per_point    ms bought per point of correct main-verb use
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnchoredOffsetbox, DrawingArea, HPacker, TextArea, VPacker
from matplotlib.patches import Circle, Rectangle

ROOT = Path(__file__).resolve().parents[2]
CAL_DIR = ROOT / "research" / "runs" / "cost_cal_sequential"
FIG_DIR = ROOT / "docs" / "report-writing" / "figures"

# Shared palette with the quality Pareto figures.
C_BASE = "#6c757d"
C_LORA_A = "#1f4e79"
C_LORA_B = "#2a9d8f"
C_GPT = "#c9a227"
C_TEXT = "#3a3a3a"
C_GRID = "#d0d0d0"

ADAPTERS = {
    "base": ("Base 1.7B", C_BASE, "o", 62),
    "A": ("LoRA-with-inject", C_LORA_A, "D", 58),
    "B": ("LoRA-no-inject", C_LORA_B, "^", 78),
}

# arm_label -> (adapter key, displayed generation configuration, Form %, Main
# verb %, G, N, S)
# Quality is the 36-verb held-out set (n = 1,116); see tab:td-combined.
ARMS = {
    "base17_vanilla":      ("base", "Greedy",          22.0, 21.5, 4.69, 4.52, 4.78),
    "base17_inject":       ("base", "Greedy + Inject", 94.2, 75.7, 4.37, 3.92, 4.33),
    "base17_soft8":        ("base", "Soft",         62.2, 45.8, 4.34, 3.79, 4.14),
    "base17_neuro":        ("base", "Neuro",        78.2, 69.1, 4.77, 4.29, 4.60),
    "base17_neuro_inject": ("base", "Neuro + Inject", 99.8, 83.6, 4.43, 3.96, 4.38),
    "loraA_vanilla":       ("A", "Greedy",           78.3, 77.4, 4.80, 4.54, 4.76),
    "loraA_inject":        ("A", "Greedy + Inject",  98.3, 96.6, 4.89, 4.54, 4.74),
    "loraA_soft8":         ("A", "Soft",            96.6, 72.0, 4.47, 3.59, 3.92),
    "loraA_neuro":         ("A", "Neuro",           97.9, 94.3, 4.90, 4.50, 4.74),
    "loraA_neuro_inject":  ("A", "Neuro + Inject", 100.0, 98.6, 4.91, 4.54, 4.76),
    "loraB_vanilla":       ("B", "Greedy",          86.3, 86.2, 4.75, 4.47, 4.74),
    "loraB_inject":        ("B", "Greedy + Inject", 93.8, 92.9, 4.82, 4.46, 4.72),
    "loraB_soft8":         ("B", "Soft",            98.5, 84.7, 4.32, 3.78, 4.09),
    "loraB_neuro":         ("B", "Neuro",           98.8, 96.6, 4.90, 4.57, 4.77),
    "loraB_neuro_inject":  ("B", "Neuro + Inject",  99.7, 97.4, 4.88, 4.50, 4.70),
}

# API wall-clock over a network, not on-device compute. Flagged in captions.
GPT = {"label": "GPT-5.5", "ms": 2642.9, "mv": 99.3, "n": 4.89}

# Configurations recommended in the deployment analysis: real-time with a
# conjugator, pre-computed generation, and real-time without a conjugator.
RECOMMENDED = {
    "loraA_inject",
    "loraA_neuro_inject",
    "loraB_vanilla",
}


def load_cost() -> dict[str, dict]:
    """Mean and sample sd of ms/sentence per arm across the three repeats."""
    runs: dict[str, list[float]] = defaultdict(list)
    meta: dict[str, dict] = {}
    for path in sorted(CAL_DIR.glob("repeat_*/*.json")):
        rec = json.loads(path.read_text())
        label = rec["arm_label"]
        runs[label].append(rec["ms_per_sentence"])
        meta[label] = {"beams": rec.get("num_beams"), "batch": rec.get("hf_batch_size")}

    out = {}
    for label, values in runs.items():
        out[label] = {
            "ms": statistics.mean(values),
            "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
            "repeats": len(values),
            **meta[label],
        }
    return out


def build_rows(cost: dict[str, dict]) -> list[dict]:
    missing = [a for a in ARMS if a not in cost]
    if missing:
        raise SystemExit(f"Missing calibration data for: {', '.join(sorted(missing))}")

    base_ms = cost["base17_vanilla"]["ms"]
    rows = []
    for label, (adapter, decode, form, mv, gram, nat, sem) in ARMS.items():
        c = cost[label]
        rows.append(
            {
                "label": label,
                "adapter": adapter,
                "decode": decode,
                "adapter_name": ADAPTERS[adapter][0],
                "colour": ADAPTERS[adapter][1],
                "marker": ADAPTERS[adapter][2],
                "size": ADAPTERS[adapter][3],
                "form": form,
                "mv": mv,
                "g": gram,
                "n": nat,
                "s": sem,
                "ms": c["ms"],
                "sd": c["sd"],
                "rel": c["ms"] / base_ms,
                "beams": c["beams"],
            }
        )
    return rows


def save(fig, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{stem}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {stem}.png / .pdf")


def style_axes(ax) -> None:
    ax.grid(True, which="major", axis="both", color=C_GRID, lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#8a8a8a")
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=C_TEXT, labelsize=9)


# ── Figure 1: main verb against latency ──────────────────────────────────────

# arm -> (label text, bearing in degrees with 0 = north and clockwise,
#         leader length in axes fractions)
F1_LABELS = {
    "base17_vanilla":      ("Base 1.7B [Greedy]", 25, 0.075),
    "base17_inject":       ("Base 1.7B [Greedy + Inject]", 145, 0.105),
    "loraA_vanilla":       ("LoRA-with-inject [Greedy]", 138, 0.085),
    "base17_soft8":        ("Base 1.7B [Soft]", 32, 0.080),
    "loraA_soft8":         ("LoRA-with-inject [Soft]", 182, 0.085),
    "base17_neuro":        ("Base 1.7B [Neuro]", 182, 0.080),
    "base17_neuro_inject": ("Base 1.7B [Neuro + Inject]", 234, 0.105),
}

# Two clusters are too tight for bearings to separate: the adapter NeuroLogic
# arms sit within 620 ms and 4.3 points of each other, and the low-latency
# adapter arms within 18 ms. Fan both into empty lanes at explicit
# axes-fraction positions instead.
F1_FANNED = {
    "loraA_inject":       ("LoRA-with-inject [Greedy + Inject]", 0.250, 0.975),
    "loraB_inject":       ("LoRA-no-inject [Greedy + Inject]", 0.250, 0.893),
    "loraB_vanilla":      ("LoRA-no-inject [Greedy]", 0.250, 0.812),
    "loraB_soft8":        ("LoRA-no-inject [Soft]", 0.250, 0.733),
    "loraA_neuro_inject": ("LoRA-with-inject [Neuro + Inject]", 0.845, 0.945),
    "loraB_neuro_inject": ("LoRA-no-inject [Neuro + Inject]", 0.845, 0.850),
    "loraB_neuro":        ("LoRA-no-inject [Neuro]", 0.845, 0.755),
    "loraA_neuro":        ("LoRA-with-inject [Neuro]", 0.845, 0.660),
}


def bearing_offset(bearing_deg: float, dist: float) -> tuple[float, float]:
    rad = math.radians(bearing_deg)
    return dist * math.sin(rad), dist * math.cos(rad)


def align_for_bearing(bearing_deg: float) -> tuple[str, str]:
    b = bearing_deg % 360
    if b < 22.5 or b >= 337.5:
        return "center", "bottom"
    if b < 67.5:
        return "left", "bottom"
    if b < 112.5:
        return "left", "center"
    if b < 157.5:
        return "left", "top"
    if b < 202.5:
        return "center", "top"
    if b < 247.5:
        return "right", "top"
    if b < 292.5:
        return "right", "center"
    return "right", "bottom"


def fig_mainverb_vs_latency(rows: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(10.6, 6.4))
    style_axes(ax)

    ax.set_xscale("log")
    ax.set_xlim(90, 60000)
    ax.set_ylim(14, 106)

    by_label = {r["label"]: r for r in rows}

    # GPT reference first so local points sit above it where they overlap.
    ax.scatter(
        GPT["ms"], GPT["mv"], marker="*", s=330, c=C_GPT,
        edgecolors="none", linewidths=0, zorder=4,
    )

    for r in rows:
        ax.scatter(
            r["ms"], r["mv"], marker=r["marker"], s=r["size"],
            c=r["colour"], edgecolors="none", linewidths=0, zorder=5,
        )

    trans = ax.transData
    inv = ax.transAxes.inverted()

    def place(x, y, text, colour, target, ha, va):
        px, py = inv.transform(trans.transform((x, y)))
        ax.annotate(
            text,
            xy=(px, py), xycoords="axes fraction",
            xytext=target, textcoords="axes fraction",
            ha=ha, va=va, fontsize=8.4, color=colour, zorder=7,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=1.0),
            arrowprops=dict(
                arrowstyle="-", color=colour, lw=0.7, alpha=0.55,
                shrinkA=1.0, shrinkB=3.0,
            ),
        )

    def annotate(x, y, text, bearing, dist, colour):
        px, py = inv.transform(trans.transform((x, y)))
        dx, dy = bearing_offset(bearing, dist)
        ha, va = align_for_bearing(bearing)
        place(x, y, text, colour, (px + dx, py + dy), ha, va)

    for label, (text, bearing, dist) in F1_LABELS.items():
        r = by_label[label]
        annotate(r["ms"], r["mv"], text, bearing, dist, r["colour"])

    for label, (text, tx, ty) in F1_FANNED.items():
        r = by_label[label]
        place(r["ms"], r["mv"], text, r["colour"], (tx, ty), "left", "center")

    annotate(GPT["ms"], GPT["mv"], "GPT-5.5 (reference)", 185, 0.075, C_GPT)

    ax.set_xlabel("Latency per sentence (ms, log scale)", fontsize=10.5, color=C_TEXT)
    ax.set_ylabel("Correct main-verb use (%)", fontsize=10.5, color=C_TEXT)
    ax.set_xticks([100, 200, 500, 1000, 2000, 5000, 10000])
    ax.set_xticklabels(["100", "200", "500", "1,000", "2,000", "5,000", "10,000"])
    ax.set_yticks([20, 30, 40, 50, 60, 70, 80, 90, 100])

    handles = [
        Line2D([], [], marker=m, color="none", markerfacecolor=c,
               markersize=8, label=name)
        for name, c, m, _ in ADAPTERS.values()
    ]
    handles.append(
        Line2D([], [], marker="*", color="none", markerfacecolor="none",
               markeredgecolor=C_GPT, markeredgewidth=1.5, markersize=15,
               label="GPT-5.5 (API latency)")
    )
    leg = ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.23, 0.0),
                    frameon=True, fontsize=8.8, framealpha=0.95,
                    edgecolor="#cccccc")
    leg.get_frame().set_linewidth(0.6)

    save(fig, "cost_mainverb_vs_latency")


# ── Figure 2: latency ladder ─────────────────────────────────────────────────

def fig_latency_ladder(rows: list[dict]) -> None:
    base_ms = next(r["ms"] for r in rows if r["label"] == "base17_vanilla")
    gpt_row = {
        "label": "gpt55",
        "display_name": "GPT-5.5",
        "adapter_name": "GPT-5.5",
        "decode": "API reference",
        "colour": C_GPT,
        "mv": GPT["mv"],
        "n": GPT["n"],
        "ms": GPT["ms"],
        "rel": GPT["ms"] / base_ms,
    }
    ordered = sorted([*rows, gpt_row], key=lambda r: r["ms"])
    fig, ax = plt.subplots(figsize=(9.0, 6.0))
    style_axes(ax)
    ax.grid(True, which="major", axis="y", color="none")

    ax.set_xscale("log")
    ax.set_xlim(60, 40000)

    ys = range(len(ordered))
    for y, r in zip(ys, ordered):
        ax.barh(y, r["ms"], height=0.66, color=r["colour"], alpha=0.9,
                edgecolor="none", zorder=3)
        ax.text(
            r["ms"] * 1.10, y,
            rf"$\mathbf{{{r['ms']:,.0f}\ \mathsf{{\mathbf{{ms}}}}\ \;({r['rel']:.2f}\times)}}$"
            f"   [MV {r['mv']:.1f}%; N {r['n']:.2f}]",
            va="center", ha="left", fontsize=8.4, color=C_TEXT, zorder=4,
        )

    ax.set_yticks(list(ys))
    ax.set_yticklabels(
        [r.get("display_name", f"{r['adapter_name']} [{r['decode']}]") for r in ordered],
                       fontsize=8.8, color=C_TEXT)
    for tick, r in zip(ax.get_yticklabels(), ordered):
        if r["label"] in RECOMMENDED:
            tick.set_bbox(
                dict(boxstyle="square,pad=0.14", facecolor="#fff3a3",
                     edgecolor="none", alpha=0.85)
            )
    ax.invert_yaxis()
    ax.set_ylim(len(ordered) - 0.4, -0.6)

    ax.set_xlabel(
        "Latency per sentence (ms, log scale)",
        fontsize=10.0, color=C_TEXT,
    )
    ax.set_ylabel("Generation configuration", fontsize=10.0, color=C_TEXT)
    ax.set_xticks([100, 200, 500, 1000, 2000, 5000, 10000])
    ax.set_xticklabels(["100", "200", "500", "1,000", "2,000", "5,000", "10,000"])

    def text_box(text: str, *, highlighted: bool = False) -> TextArea:
        props = {"color": C_TEXT, "fontsize": 8.8}
        if highlighted:
            props["bbox"] = dict(
                boxstyle="square,pad=0.12", facecolor="#fff3a3",
                edgecolor="none", alpha=0.85,
            )
        return TextArea(text, textprops=props)

    def swatch(colour: str | None = None) -> DrawingArea:
        area = DrawingArea(11, 11, 0, 0)
        if colour is not None:
            area.add_artist(
                Rectangle((1, 1), 8, 8, facecolor=colour,
                          edgecolor=C_TEXT, linewidth=0.6)
            )
        else:
            area.add_artist(
                Circle((5, 5), radius=1.1, facecolor=C_TEXT, edgecolor="none")
            )
        return area

    def legend_row(label: str, colour: str | None = None):
        return HPacker(
            children=[swatch(colour), text_box(label)],
            align="center", pad=0, sep=3,
        )

    highlighted_row = HPacker(
        children=[
            swatch(),
            HPacker(
                children=[
                    text_box("Highlighted", highlighted=True),
                    text_box(" label: recommended configuration"),
                ],
                align="center", pad=0, sep=0,
            ),
        ],
        align="center", pad=0, sep=3,
    )

    legend_box = VPacker(
        children=[
            legend_row("Base 1.7B", C_BASE),
            legend_row("LoRA-with-inject", C_LORA_A),
            legend_row("LoRA-no-inject", C_LORA_B),
            legend_row("GPT-5.5", C_GPT),
            highlighted_row,
            legend_row("Parentheses (\u00d7): relative latency\nas a multiple of Base 1.7B vanilla"),
            legend_row("MV: correct main-verb use"),
            legend_row("N: naturalness"),
        ],
        align="left", pad=4, sep=2,
    )
    legend = AnchoredOffsetbox(
        loc="upper right", child=legend_box, pad=0.3, borderpad=0.0,
        frameon=True, bbox_to_anchor=(1.15, 1.0), bbox_transform=ax.transAxes,
    )
    legend.patch.set_alpha(0.95)
    legend.patch.set_edgecolor("#cccccc")
    legend.patch.set_linewidth(0.6)
    ax.add_artist(legend)

    save(fig, "cost_latency_ladder")


# ── Figure 3: marginal cost per point of correct main-verb use ───────────────

# (from arm, to arm, what the step adds, colour)
C_ADD_ADAPTER = "#1f4e79"
C_ADD_INJECT = "#2a9d8f"
C_ADD_SOFT = "#c45c26"
C_ADD_NEURO = "#9b2226"

STEPS = [
    ("base17_vanilla", "base17_inject",       "Add injection",  C_ADD_INJECT),
    ("loraA_vanilla",  "loraA_inject",        "Add injection",  C_ADD_INJECT),
    ("base17_vanilla", "loraB_vanilla",       "Add adapter",    C_ADD_ADAPTER),
    ("base17_vanilla", "loraA_vanilla",       "Add adapter",    C_ADD_ADAPTER),
    ("loraB_vanilla",  "loraB_inject",        "Add injection",  C_ADD_INJECT),
    ("base17_vanilla", "base17_soft8",        "Add soft bias",  C_ADD_SOFT),
    ("base17_inject",  "base17_neuro_inject", "Add NeuroLogic", C_ADD_NEURO),
    ("loraB_vanilla",  "loraB_neuro",         "Add NeuroLogic", C_ADD_NEURO),
    ("loraA_inject",   "loraA_neuro_inject",  "Add NeuroLogic", C_ADD_NEURO),
]

# Steps whose main-verb accuracy falls, so a cost per point is undefined.
DOMINATED = [
    ("loraA_vanilla", "loraA_soft8", "Add soft bias", C_ADD_SOFT),
    ("loraB_vanilla", "loraB_soft8", "Add soft bias", C_ADD_SOFT),
]


def step_name(row: dict) -> str:
    return f"{row['adapter_name']} [{row['decode']}]"


def fig_marginal_cost(rows: list[dict]) -> None:
    by_label = {r["label"]: r for r in rows}

    entries = []
    for src, dst, kind, colour in STEPS:
        a, b = by_label[src], by_label[dst]
        d_ms = b["ms"] - a["ms"]
        d_mv = b["mv"] - a["mv"]
        entries.append(
            {
                "text": f"{step_name(a)}  \u2192  {step_name(b)}",
                "kind": kind,
                "colour": colour,
                "d_ms": d_ms,
                "d_mv": d_mv,
                "per_point": d_ms / d_mv,
            }
        )

    free = [e for e in entries if e["per_point"] <= 0]
    paid = sorted((e for e in entries if e["per_point"] > 0),
                  key=lambda e: e["per_point"])

    dominated = []
    for src, dst, kind, colour in DOMINATED:
        a, b = by_label[src], by_label[dst]
        dominated.append(
            {
                "text": f"{step_name(a)}  \u2192  {step_name(b)}",
                "kind": kind,
                "colour": colour,
                "d_ms": b["ms"] - a["ms"],
                "d_mv": b["mv"] - a["mv"],
            }
        )

    ordered = free + paid + dominated
    n = len(ordered)

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    style_axes(ax)
    ax.grid(True, which="major", axis="y", color="none")

    ax.set_xscale("log")
    floor = 0.30
    ax.set_xlim(floor, 90000)

    # Bars span [floor, right] in data units, so on the log axis the drawn
    # width must be right - floor for the bar end to land on the value.
    stub = 0.85

    for y, e in enumerate(ordered):
        is_free = e in free
        is_dom = e in dominated

        if is_free:
            ax.barh(y, stub - floor, left=floor, height=0.62, color=e["colour"],
                    alpha=0.9, edgecolor="none", zorder=3)
            note = (f"no extra cost  ({e['d_ms']:+.1f} ms "
                    f"for {e['d_mv']:+.1f} pts)")
            ax.text(stub * 1.18, y, note, va="center", ha="left",
                    fontsize=8.2, color=C_TEXT, zorder=4)
        elif is_dom:
            ax.barh(y, stub - floor, left=floor, height=0.62, color=e["colour"],
                    alpha=0.30, edgecolor=e["colour"], linewidth=0.8,
                    hatch="///", zorder=3)
            note = (f"no gain to buy  ({e['d_ms']:+,.0f} ms "
                    f"for {e['d_mv']:+.1f} pts)")
            ax.text(stub * 1.18, y, note, va="center", ha="left",
                    fontsize=8.2, color=C_TEXT, zorder=4)
        else:
            ax.barh(y, e["per_point"] - floor, left=floor, height=0.62,
                    color=e["colour"], alpha=0.9, edgecolor="none", zorder=3)
            val = (f"{e['per_point']:,.0f}" if e["per_point"] >= 10
                   else f"{e['per_point']:.2f}")
            ax.text(e["per_point"] * 1.18, y, f"{val} ms / pt",
                    va="center", ha="left", fontsize=8.4, color=C_TEXT, zorder=4)

    ax.set_yticks(range(n))
    ax.set_yticklabels([e["text"] for e in ordered], fontsize=8.4, color=C_TEXT)
    ax.invert_yaxis()
    ax.set_ylim(n - 0.4, -0.6)

    ax.set_xlabel(
        "Additional latency bought per percentage point of correct "
        "main-verb use (ms, log scale)",
        fontsize=10.0, color=C_TEXT,
    )
    ax.set_xticks([1, 10, 100, 1000, 10000])
    ax.set_xticklabels(["1", "10", "100", "1,000", "10,000"])

    seen, handles = set(), []
    for e in ordered:
        if e["kind"] in seen:
            continue
        seen.add(e["kind"])
        handles.append(
            Line2D([], [], marker="s", color="none", markerfacecolor=e["colour"],
                   markersize=9, label=e["kind"])
        )
    leg = ax.legend(handles=handles, loc="lower right", frameon=True,
                    fontsize=8.8, framealpha=0.95, edgecolor="#cccccc")
    leg.get_frame().set_linewidth(0.6)

    save(fig, "cost_marginal_per_point")


# ── Figure 4: latency against main verb, restricted to the Pareto set ────────

# The arms shown in lora_matrix_pareto_mainverb_naturalness_ge60, which is the
# companion quality figure. LoRA-with-inject Soft+inject appears there but is
# absent here: it was never timed in the controlled calibration.
GE60_LABELS = {
    "loraA_vanilla":       ("LoRA-with-inject [Greedy]", 0, 0.062),
    "loraB_vanilla":       ("LoRA-no-inject [Greedy]", 0, 0.062),
    "loraB_inject":        ("LoRA-no-inject [Greedy + Inject]", 180, 0.062),
    "loraA_inject":        ("LoRA-with-inject [Greedy + Inject]", 0, 0.062),
    "base17_neuro":        ("Base 1.7B [Neuro]", 180, 0.070),
    "base17_neuro_inject": ("Base 1.7B [Neuro + Inject]", 180, 0.070),
    "loraA_neuro":         ("LoRA-with-inject [Neuro]", 270, 0.075),
    "loraB_neuro":         ("LoRA-no-inject\n[Neuro]", 0, 0.075),
    "loraA_neuro_inject":  ("LoRA-with-inject\n[Neuro + Inject]", 200, 0.090),
}


def fig_latency_vs_mainverb_ge60(rows: list[dict]) -> None:
    by_label = {r["label"]: r for r in rows}
    fig, ax = plt.subplots(figsize=(10.0, 5.8))
    style_axes(ax)

    ax.set_yscale("log")
    ax.set_xlim(60, 104)
    ax.set_ylim(95, 30000)

    ax.scatter(
        GPT["mv"], GPT["ms"], marker="*", s=330, c=C_GPT,
        edgecolors="none", linewidths=0, zorder=4,
    )
    for key in GE60_LABELS:
        r = by_label[key]
        ax.scatter(
            r["mv"], r["ms"], marker=r["marker"], s=r["size"],
            c=r["colour"], edgecolors="none", linewidths=0, zorder=5,
        )

    trans = ax.transData
    inv = ax.transAxes.inverted()

    def annotate(x, y, text, bearing, dist, colour):
        px, py = inv.transform(trans.transform((x, y)))
        dx, dy = bearing_offset(bearing, dist)
        ha, va = align_for_bearing(bearing)
        ax.annotate(
            text,
            xy=(px, py), xycoords="axes fraction",
            xytext=(px + dx, py + dy), textcoords="axes fraction",
            ha=ha, va=va, fontsize=8.4, color=colour, zorder=7,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=1.0),
            arrowprops=dict(
                arrowstyle="-", color=colour, lw=0.7, alpha=0.55,
                shrinkA=1.0, shrinkB=3.0,
            ),
        )

    for key, (text, bearing, dist) in GE60_LABELS.items():
        r = by_label[key]
        annotate(r["mv"], r["ms"], text, bearing, dist, r["colour"])

    annotate(GPT["mv"], GPT["ms"], "GPT-5.5 (reference)", 250, 0.085, C_GPT)

    ax.set_xlabel("Correct main-verb use (%)", fontsize=10.5, color=C_TEXT)
    ax.set_ylabel("Latency per sentence (ms, log scale)", fontsize=10.5,
                  color=C_TEXT)
    ax.set_xticks([60, 70, 80, 90, 100])
    ax.set_yticks([100, 200, 500, 1000, 2000, 5000, 10000])
    ax.set_yticklabels(["100", "200", "500", "1,000", "2,000", "5,000", "10,000"])

    handles = [
        Line2D([], [], marker=m, color="none", markerfacecolor=c,
               markersize=8, label=name)
        for name, c, m, _ in ADAPTERS.values()
    ]
    handles.append(
        Line2D([], [], marker="*", color="none", markerfacecolor=C_GPT,
               markersize=14, label="GPT-5.5 (API latency)")
    )
    leg = ax.legend(handles=handles, loc="lower left", frameon=True,
                    fontsize=8.8, framealpha=0.95, edgecolor="#cccccc")
    leg.get_frame().set_linewidth(0.6)

    save(fig, "cost_latency_vs_mainverb_ge60")


def main() -> None:
    cost = load_cost()
    rows = build_rows(cost)

    print(f"{'arm':22s} {'ms':>9s} {'sd':>6s} {'rel':>7s} {'MV':>6s}")
    for r in sorted(rows, key=lambda r: r["ms"]):
        print(f"{r['label']:22s} {r['ms']:9.1f} {r['sd']:6.2f} "
              f"{r['rel']:6.2f}x {r['mv']:5.1f}%")

    fig_mainverb_vs_latency(rows)
    fig_latency_ladder(rows)
    fig_marginal_cost(rows)
    fig_latency_vs_mainverb_ge60(rows)


if __name__ == "__main__":
    main()
