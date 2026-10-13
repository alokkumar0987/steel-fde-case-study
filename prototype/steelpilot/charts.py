"""Four PNG charts for the report. Palette and mark rules follow the dataviz reference
palette (validated: categorical slots 1-5, light surface). Every chart has a data
table in results.md, because three slots sit below 3:1 contrast on the surface."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from . import config as C  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]  # fixed order, never cycled

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def _save(fig, name: str) -> str:
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = C.OUTPUT_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return name


def waste_by_cause(by_cause: pd.DataFrame) -> str:
    data = by_cause.drop(index="Total")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    bottom = pd.Series(0.0, index=data.index)
    for color, cause in zip(SERIES, data.columns):
        ax.bar(data.index, data[cause], bottom=bottom, color=color, width=0.5,
               edgecolor=SURFACE, linewidth=2, label=cause)
        bottom += data[cause]
    for x, total in zip(data.index, bottom):
        ax.annotate(f"{total:.1f} t", (x, total), xytext=(0, 4), textcoords="offset points",
                    ha="center", color=INK_2)
    ax.set_title("Waste by cause, per project (synthetic data)")
    ax.set_ylabel("Tonnes")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    return _save(fig, "waste_by_cause.png")


def benchmark_paired(nests: pd.DataFrame, weighted_gain: float) -> str:
    d = nests.sort_values("gain_pts").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    sizes = 20 + 160 * d["parts_t"] / d["parts_t"].max()
    ax.scatter(d.index, d["gain_pts"], s=sizes, color=SERIES[0], edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.axhline(0, color=AXIS, linewidth=1)
    th = C.THRESHOLDS["profile_gain_pts"]
    ax.axhline(th, color=MUTED, linewidth=1.2, linestyle="--")
    ax.annotate(f"Pass threshold +{th:.0f} pt", (0, th), xytext=(2, 4), textcoords="offset points", color=INK_2)
    ax.axhline(weighted_gain, color=SERIES[1], linewidth=2)
    ax.annotate(f"Tonnage-weighted gain {weighted_gain:+.2f} pts", (len(d) - 1, weighted_gain),
                xytext=(-2, -14 if weighted_gain < th / 2 else 4), textcoords="offset points",
                ha="right", color=INK)
    ax.set_title("Automatic minus manual yield, per nest (dot size = tonnes)")
    ax.set_xlabel("30 benchmark nests, sorted by gain")
    ax.set_ylabel("Yield gain, percentage points")
    ax.set_xticks([])
    return _save(fig, "benchmark_paired.png")


def stock_length(study: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    x = range(len(study))
    w = 0.36
    ax.bar([i - w / 2 - 0.01 for i in x], study["scrap_pct"], width=w, color=SERIES[0], label="Scrap + kerf")
    ax.bar([i + w / 2 + 0.01 for i in x], study["offcut_pct"], width=w, color=SERIES[1], label="Offcut back to stock")
    for i, (s, o) in enumerate(zip(study["scrap_pct"], study["offcut_pct"])):
        ax.annotate(f"{s:.1f}%", (i - w / 2, s), xytext=(0, 3), textcoords="offset points", ha="center", color=INK_2)
        ax.annotate(f"{o:.1f}%", (i + w / 2, o), xytext=(0, 3), textcoords="offset points", ha="center", color=INK_2)
    ax.set_xticks(list(x), study["stock"])
    ax.set_title("Same cut lists, different stock lengths (automatic nesting)")
    ax.set_ylabel("% of steel consumed")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    return _save(fig, "stock_length_drop.png")


def plate_profile_range(grid: pd.DataFrame, m: dict) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.axvspan(m["p_low"], m["p_high"], color=GRID, alpha=0.7, linewidth=0)
    ax.annotate("Plate share allowed by your ranges", (m["p_high"], 0), xytext=(-4, 6),
                textcoords="offset points", ha="right", color=INK_2)
    ax.plot(grid["plate_share"], grid["plate_waste_t"], color=SERIES[0], linewidth=2, label="Plate waste")
    ax.plot(grid["plate_share"], grid["profile_waste_t"], color=SERIES[1], linewidth=2, label="Profile waste")
    for p, label in [(m["p_mid"], f"Midpoints: {m['p_mid']:.0%}"), (m["crossover_mid"], f"Equal: {m['crossover_mid']:.0%}")]:
        ax.axvline(p, color=MUTED, linewidth=1, linestyle="--")
        ax.annotate(label, (p, ax.get_ylim()[1] * 0.92), xytext=(4, 0), textcoords="offset points", color=INK_2)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_title("Plate vs profile waste across the plate share (midpoint waste rates)")
    ax.set_xlabel("Plate share of 80,000 t")
    ax.set_ylabel("Tonnes wasted per year")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    return _save(fig, "plate_profile_range.png")
