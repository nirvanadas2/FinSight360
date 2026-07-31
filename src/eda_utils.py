"""Reusable EDA plotting functions shared across the notebooks.

Color follows the project's data-viz conventions: a single blue hue for
magnitude/sequential encodings, a blue<->red diverging ramp with a neutral
gray midpoint for correlation, and muted chart chrome (light surface,
recessive gridlines) throughout.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

SEQUENTIAL_BLUE = "#2a78d6"
_SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list("seq_blue", ["#cde2fb", "#0d366b"])
_DIVERGING_CMAP = LinearSegmentedColormap.from_list(
    "diverging_blue_red", ["#184f95", "#f0efec", "#b23a39"]
)

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "axes.titlecolor": INK_PRIMARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "grid.color": GRIDLINE,
    "grid.linewidth": 0.8,
    "axes.grid": True,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def sequential_shades(n: int, start: float = 0.2, end: float = 1.0) -> list:
    """n evenly-spaced hex colors along the sequential blue ramp (light -> dark)."""
    return [_SEQUENTIAL_CMAP(v) for v in np.linspace(start, end, n)]


def plot_distribution(df: pd.DataFrame, column: str, bins: int = 40, kde: bool = True,
                       ax=None, title: str = None, log_scale: bool = False):
    """Histogram (+ optional KDE) of a numeric column."""
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4.5))

    data = df[column].dropna()
    sns.histplot(data, bins=bins, color=SEQUENTIAL_BLUE, edgecolor=SURFACE,
                 linewidth=0.5, kde=kde, log_scale=log_scale, ax=ax)
    if kde:
        ax.lines[-1].set_color(INK_PRIMARY)
        ax.lines[-1].set_linewidth(1.5)

    ax.set_title(title or f"Distribution of {column}", loc="left", fontsize=12, fontweight="bold")
    ax.set_xlabel(column)
    ax.set_ylabel("Count")
    ax.grid(axis="x", visible=False)
    ax.figure.tight_layout()
    return ax


def plot_missing_map(df: pd.DataFrame, ax=None, top_n: int = None, title: str = None):
    """Horizontal bar chart of % missing per column, sorted descending.

    Only columns with at least one missing value are shown.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * min(len(df.columns), top_n or 999))))

    missing_pct = (df.isna().mean() * 100).sort_values(ascending=False)
    missing_pct = missing_pct[missing_pct > 0]
    if top_n:
        missing_pct = missing_pct.head(top_n)

    if missing_pct.empty:
        ax.text(0.5, 0.5, "No missing values", ha="center", va="center",
                color=INK_SECONDARY, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return ax

    colors = sequential_shades(len(missing_pct))[::-1]
    bars = ax.barh(missing_pct.index[::-1], missing_pct.values[::-1], color=colors[::-1])
    for bar, value in zip(bars, missing_pct.values[::-1]):
        ax.text(bar.get_width() + max(missing_pct.values) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{value:.1f}%", va="center", fontsize=9, color=INK_SECONDARY)

    ax.set_title(title or "Missing values by column", loc="left", fontsize=12, fontweight="bold")
    ax.set_xlabel("% missing")
    ax.grid(axis="y", visible=False)
    ax.figure.tight_layout()
    return ax


def plot_correlation_heatmap(df: pd.DataFrame, columns: list = None, method: str = "pearson",
                              ax=None, title: str = None, annot: bool = True):
    """Diverging correlation heatmap (blue<->red, gray midpoint at 0) for numeric columns."""
    cols = columns or df.select_dtypes(include="number").columns.tolist()
    corr = df[cols].corr(method=method)

    if ax is None:
        size = max(5, 0.6 * len(cols))
        _, ax = plt.subplots(figsize=(size, size))

    sns.heatmap(corr, cmap=_DIVERGING_CMAP, vmin=-1, vmax=1, center=0,
                annot=annot, fmt=".2f", square=True, linewidths=2, linecolor=SURFACE,
                cbar_kws={"shrink": 0.8, "label": f"{method.title()} correlation"}, ax=ax)

    ax.set_title(title or "Correlation heatmap", loc="left", fontsize=12, fontweight="bold")
    ax.tick_params(axis="x", rotation=45)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    ax.figure.tight_layout()
    return ax
