"""Diagnostic 3A conditional results as a true Sankey diagram (Plotly).

No cartesian axes — just flow from 2A outcome into 3A sentence outcome.
Green family = knew the form in 2A; warm family = missed it in 2A.
"""

from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

out_dir = Path(__file__).resolve().parent.parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)

TOTAL = 4650
DATA = {
    "0.6B": {"ok2_ok3": 291, "ok2_bad3": 656, "bad2_ok3": 403, "bad2_bad3": 3300},
    "1.7B": {"ok2_ok3": 1965, "ok2_bad3": 1248, "bad2_ok3": 397, "bad2_bad3": 1040},
    "4B":   {"ok2_ok3": 2445, "ok2_bad3": 1311, "bad2_ok3": 340, "bad2_bad3": 554},
}

# Colour families
C_ALL = "#bdbdbd"
C_OK2 = "#41ab5d"          # correct in 2A
C_BAD2 = "#ef3b2c"         # incorrect in 2A
C_USED = "#006d2c"         # ok2 -> appears
C_BIND = "#a1d99b"         # ok2 -> missing (binding gap)
C_RECOVER = "#fd8d3c"      # bad2 -> appears
C_MISS = "#a50f15"         # bad2 -> missing


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def sankey_for_model(model: str) -> go.Sankey:
    d = DATA[model]
    known = d["ok2_ok3"] + d["ok2_bad3"]
    unknown = d["bad2_ok3"] + d["bad2_bad3"]

    # Node order
    # 0 All cells
    # 1 Correct in 2A
    # 2 Incorrect in 2A
    # 3 Present in 3A (given correct in 2A)
    # 4 Absent in 3A (given correct in 2A)
    # 5 Present in 3A (given incorrect in 2A)
    # 6 Absent in 3A (given incorrect in 2A)
    labels = [
        f"All cells<br>{TOTAL:,}",
        f"Correct in 2A<br>{known:,} ({known / TOTAL:.0%})",
        f"Incorrect in 2A<br>{unknown:,} ({unknown / TOTAL:.0%})",
        f"Present in 3A<br>{d['ok2_ok3']:,} ({d['ok2_ok3'] / known:.0%})",
        f"Absent in 3A<br>{d['ok2_bad3']:,} ({d['ok2_bad3'] / known:.0%})",
        f"Present in 3A<br>{d['bad2_ok3']:,} ({d['bad2_ok3'] / unknown:.0%})",
        f"Absent in 3A<br>{d['bad2_bad3']:,} ({d['bad2_bad3'] / unknown:.0%})",
    ]
    node_colors = [C_ALL, C_OK2, C_BAD2, C_USED, C_BIND, C_RECOVER, C_MISS]

    # Explicit x/y so columns read left → right as a funnel
    # y: larger = higher on plot in plotly sankey
    node_x = [0.01, 0.35, 0.35, 0.85, 0.85, 0.85, 0.85]
    # Place correct branch in lower half, incorrect in upper half
    node_y = [
        0.50,                          # all
        known / (2 * TOTAL),           # correct centre ~ lower
        0.5 + unknown / (2 * TOTAL),   # incorrect centre ~ upper
        d["ok2_ok3"] / (2 * TOTAL),
        (d["ok2_ok3"] + d["ok2_bad3"] / 2) / TOTAL,
        (known + d["bad2_ok3"] / 2) / TOTAL,
        (known + d["bad2_ok3"] + d["bad2_bad3"] / 2) / TOTAL,
    ]

    sources = [0, 0, 1, 1, 2, 2]
    targets = [1, 2, 3, 4, 5, 6]
    values = [known, unknown, d["ok2_ok3"], d["ok2_bad3"], d["bad2_ok3"], d["bad2_bad3"]]
    link_colors = [
        _rgba(C_OK2, 0.45),
        _rgba(C_BAD2, 0.45),
        _rgba(C_USED, 0.55),
        _rgba(C_BIND, 0.55),
        _rgba(C_RECOVER, 0.55),
        _rgba(C_MISS, 0.55),
    ]
    link_labels = [
        f"Correct in 2A: {known:,}",
        f"Incorrect in 2A: {unknown:,}",
        f"Present in 3A: {d['ok2_ok3']:,} ({d['ok2_ok3'] / known:.0%} of correct in 2A)",
        f"Absent in 3A: {d['ok2_bad3']:,} ({d['ok2_bad3'] / known:.0%} of correct in 2A)",
        f"Present in 3A: {d['bad2_ok3']:,} ({d['bad2_ok3'] / unknown:.0%} of incorrect in 2A)",
        f"Absent in 3A: {d['bad2_bad3']:,} ({d['bad2_bad3'] / unknown:.0%} of incorrect in 2A)",
    ]

    return go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18,
            thickness=22,
            line=dict(color="white", width=1),
            label=labels,
            color=node_colors,
            x=node_x,
            y=node_y,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            label=link_labels,
            hovertemplate="%{label}<extra></extra>",
        ),
    )


def save_single(model: str, filename: str, width: int = 900, height: int = 520):
    fig = go.Figure(data=[sankey_for_model(model)])
    fig.update_layout(
        title=dict(
            text=f"Qwen3 {model}: from paradigm knowledge (2A) to sentence use (3A)",
            x=0.5,
            xanchor="center",
            font=dict(size=14, family="Helvetica, Arial, sans-serif"),
        ),
        font=dict(size=12, family="Helvetica, Arial, sans-serif", color="#222"),
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        width=width,
        height=height,
    )
    path = out_dir / filename
    fig.write_image(str(path), scale=2)
    fig.write_html(str(path.with_suffix(".html")), include_plotlyjs="cdn")
    print(f"Wrote {path.name} and {path.with_suffix('.html').name}")


def save_trio(filename: str = "diag3a_sankey.png"):
    """Three Sankeys stacked vertically — one per model."""
    models = ["0.6B", "1.7B", "4B"]
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=[f"Qwen3 {m}" for m in models],
        vertical_spacing=0.06,
        specs=[[{"type": "sankey"}], [{"type": "sankey"}], [{"type": "sankey"}]],
    )
    for i, m in enumerate(models, start=1):
        fig.add_trace(sankey_for_model(m), row=i, col=1)

    fig.update_layout(
        title=dict(
            text="Conditional form use: Diagnostic 2A → Diagnostic 3A",
            x=0.5,
            xanchor="center",
            font=dict(size=15, family="Helvetica, Arial, sans-serif"),
        ),
        font=dict(size=11, family="Helvetica, Arial, sans-serif", color="#222"),
        margin=dict(l=20, r=20, t=70, b=20),
        paper_bgcolor="white",
        height=1400,
        width=920,
    )
    for ann in fig.layout.annotations:
        ann.font = dict(size=13)

    path = out_dir / filename
    fig.write_image(str(path), scale=2)
    fig.write_html(str(path.with_suffix(".html")), include_plotlyjs="cdn")
    print(f"Wrote {path.name} and {path.with_suffix('.html').name}")


def _crop_even_padding(path: Path, pad_px: int = 10) -> None:
    """Trim excess whitespace, then add the same thin pad on all four sides."""
    from PIL import Image
    import numpy as np

    im = Image.open(path).convert("RGB")
    arr = np.asarray(im)
    mask = np.any(arr < 250, axis=2)
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return
    cropped = im.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))
    canvas = Image.new("RGB", (cropped.width + 2 * pad_px, cropped.height + 2 * pad_px), "white")
    canvas.paste(cropped, (pad_px, pad_px))
    canvas.save(path)


def save_pair(filename: str = "diag3a_sankey_17b_4b_revised.png"):
    """1.7B and 4B side by side — main thesis figure.

    Diagram geometry is unchanged. Only outer padding and the gap between
    panels are adjusted: each Sankey is nudged toward the figure centre so
    left/right outer margins match and the middle gap stays thin. A final
    crop then applies the same thin pad on every side.
    """
    models = ["1.7B", "4B"]
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[f"Qwen3 {m}" for m in models],
        horizontal_spacing=0.035,
        specs=[[{"type": "sankey"}, {"type": "sankey"}]],
    )
    for i, m in enumerate(models, start=1):
        fig.add_trace(sankey_for_model(m), row=1, col=i)

    # Keep the original node span (diagram size), but park each panel toward
    # the shared centre: left panel flush-right in its domain, right panel
    # flush-left. That equalises outer white space and shortens the middle gap.
    inset = 0.02
    left, right = fig.data[0], fig.data[1]
    for trace, align in ((left, "right"), (right, "left")):
        xs = list(trace.node.x)
        x_min = min(xs)
        span = max(xs) - x_min
        if align == "right":
            start = 1.0 - inset - span
        else:
            start = inset
        trace.node.x = [start + (x - x_min) for x in xs]

    # Equal outer domains; slightly wider centre gap.
    left.domain = dict(x=[0.0, 0.482], y=[0.03, 0.97])
    right.domain = dict(x=[0.518, 1.0], y=[0.03, 0.97])

    # Reposition subplot titles over the recentred panel centres.
    fig.layout.annotations[0].update(x=0.241, xanchor="center")
    fig.layout.annotations[1].update(x=0.759, xanchor="center")

    fig.update_layout(
        font=dict(size=17, family="Helvetica, Arial, sans-serif", color="#222"),
        margin=dict(l=12, r=12, t=40, b=16),
        paper_bgcolor="white",
        height=580,
        width=1400,
    )
    for ann in fig.layout.annotations:
        ann.font = dict(size=19)

    path = out_dir / filename
    fig.write_image(str(path), scale=2)
    fig.write_html(str(path.with_suffix(".html")), include_plotlyjs="cdn")
    _crop_even_padding(path, pad_px=10)

    download_path = Path.home() / "Downloads" / filename
    download_path.write_bytes(path.read_bytes())
    print(
        f"Wrote {path.name}, {path.with_suffix('.html').name}, "
        f"and {download_path}"
    )


if __name__ == "__main__":
    save_single("1.7B", "diag3a_sankey_17b.png")
    save_single("4B", "diag3a_sankey_4b.png")
    save_pair("diag3a_sankey_17b_4b.png")
    save_trio("diag3a_sankey.png")
