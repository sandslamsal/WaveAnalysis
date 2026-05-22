"""
make_figures.py

Generate the validation and workflow figures for the WaveLabX SoftwareX
manuscript from known-truth synthetic data.

Outputs (figures/):
  validation_known_truth.png   incident/reflected recovery vs known truth
  three_probe_scenarios.png    three-probe accuracy across probe geometries
  workflow.png                 method-selection workflow (manuscript Figure 1)

Run from the repository root:
    python scripts/make_figures.py
"""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

from wavelabx.sensitivity import _synthetic_irregular_gauges
from wavelabx.three_probe import three_probe_array
from wavelabx.two_probe import two_probe_goda

FS, DURATION, H, TPEAK = 100.0, 200.0, 0.25, 1.33
HI, KR = 0.035, 0.15

plt.rcParams.update({
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
    "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "savefig.dpi": 300,
})

BLUE, ORANGE, GREEN, RED = "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"


def _run(eta, gpos):
    """Run both methods quietly; return (two_probe, three_probe) dicts.

    The two-probe result uses probes 1 and 2, a well-spaced pair.
    """
    with redirect_stdout(io.StringIO()):
        tp = two_probe_goda(eta[:, [0, 1]], fs=FS, h=H,
                            gpos=(gpos[0], gpos[1]))
        th = three_probe_array(eta, fs=FS, h=H, gpos=gpos)
    return tp, th


# ---------------------------------------------------------------------------
# Figure: validation against known truth
# ---------------------------------------------------------------------------
def fig_validation(fig_dir):
    gpos = (0.0, 0.35, 0.70)
    eta, truth = _synthetic_irregular_gauges(
        fs=FS, duration=DURATION, h=H, gpos=gpos,
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=42,
    )
    tp, th = _run(eta, gpos)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 3.1),
                                   constrained_layout=True)

    # Panel 1: incident / reflected Hm0
    groups = ["Incident $H_{m0}$", "Reflected $H_{m0}$"]
    true_v = [truth.Hi, truth.Hr]
    tp_v = [tp["Hi"], tp["Hr"]]
    th_v = [th["Hi"], th["Hr"]]
    x = np.arange(2)
    w = 0.26
    ax1.bar(x - w, true_v, w, label="True", color="0.4")
    ax1.bar(x, tp_v, w, label="Two-probe", color=BLUE)
    ax1.bar(x + w, th_v, w, label="Three-probe", color=GREEN)
    for xi, (t, a, b) in enumerate(zip(true_v, tp_v, th_v)):
        ax1.text(xi, max(t, a, b) * 1.05,
                 f"{100*(a-t)/t:+.1f}% / {100*(b-t)/t:+.1f}%",
                 ha="center", fontsize=7)
    ax1.set_xticks(x)
    ax1.set_xticklabels(groups)
    ax1.set_ylabel(r"$H_{m0}$ [m]")
    ax1.set_title("Wave-height recovery")
    ax1.set_ylim(0, max(true_v) * 1.30)
    ax1.legend(fontsize=7)

    # Panel 2: reflection coefficient
    kr_v = [truth.Kr, tp["Kr"], th["Kr"]]
    ax2.bar(["True", "Two-probe", "Three-probe"], kr_v,
            color=["0.4", BLUE, GREEN], width=0.6)
    ax2.set_ylabel(r"$K_r$ [-]")
    ax2.set_title("Reflection coefficient")
    ax2.set_ylim(0, max(kr_v) * 1.35)
    for xi, v in enumerate(kr_v):
        ax2.text(xi, v * 1.05, f"{v:.3f}", ha="center", fontsize=7)

    for ax in (ax1, ax2):
        ax.grid(axis="y", alpha=0.3)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    path = os.path.join(fig_dir, "validation_known_truth.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")


# ---------------------------------------------------------------------------
# Figure: three-probe robustness across geometries
# ---------------------------------------------------------------------------
def fig_scenarios(fig_dir):
    scenarios = [
        ("Well-spaced\n(0, 0.35, 0.70)", (0.0, 0.35, 0.70)),
        ("Mixed spacing\n(0, 0.10, 0.60)", (0.0, 0.10, 0.60)),
        ("All probes too close\n(0, 0.05, 0.10)", (0.0, 0.05, 0.10)),
    ]
    labels, err_hi, retained = [], [], []
    for i, (label, gpos) in enumerate(scenarios):
        eta, truth = _synthetic_irregular_gauges(
            fs=FS, duration=DURATION, h=H, gpos=gpos,
            Tpeak=TPEAK, Hi=HI, Kr=KR, seed=10 + i,
        )
        with redirect_stdout(io.StringIO()):
            th = three_probe_array(eta, fs=FS, h=H, gpos=gpos)
        labels.append(label)
        err_hi.append(100.0 * (th["Hi"] - truth.Hi) / truth.Hi)
        retained.append(th["retained_energy_fraction"])

    fig, ax = plt.subplots(figsize=(6.2, 3.4), constrained_layout=True)
    colors = [GREEN if r >= 0.8 else RED for r in retained]
    bars = ax.bar(labels, err_hi, color=colors, width=0.55)
    ax.axhspan(-5, 5, color="0.85", zorder=0)
    ax.axhline(0, color="0.4", linewidth=0.8)
    ax.set_ylim(min(min(err_hi) - 9, -10), max(max(err_hi) + 9, 10))
    for b, e, r in zip(bars, err_hi, retained):
        y = b.get_height()
        off = 2.6 if y >= 0 else -2.6
        va = "bottom" if y >= 0 else "top"
        ax.text(b.get_x() + b.get_width() / 2, y + off,
                f"{e:+.1f}%\nretained {r:.0%}", ha="center", va=va,
                fontsize=7)
    ax.set_ylabel(r"Incident $H_{m0}$ error [%]")
    ax.set_title("Three-probe accuracy vs. probe geometry")
    ax.grid(axis="y", alpha=0.3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    # legend proxies
    ax.bar(0, 0, color=GREEN, label="retained energy $\\geq$ 80% (reliable)")
    ax.bar(0, 0, color=RED, label="retained energy < 80% (flagged)")
    ax.legend(fontsize=7, loc="lower left")

    path = os.path.join(fig_dir, "three_probe_scenarios.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")


# ---------------------------------------------------------------------------
# Figure 1: method-selection workflow
# ---------------------------------------------------------------------------
def _box(ax, cx, cy, w, h, text, fc):
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.0, edgecolor="0.3", facecolor=fc))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=8)


def _diamond(ax, cx, cy, w, h, text, fc):
    ax.add_patch(Polygon(
        [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2),
         (cx - w / 2, cy)],
        closed=True, linewidth=1.0, edgecolor="0.3", facecolor=fc))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=7.5)


def _arrow(ax, x1, y1, x2, y2, label=None):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
        linewidth=1.0, color="0.3"))
    if label:
        ax.text((x1 + x2) / 2 + 0.25, (y1 + y2) / 2, label,
                fontsize=7.5, style="italic", color="0.2")


def fig_workflow(fig_dir):
    fig, ax = plt.subplots(figsize=(7.0, 8.6), constrained_layout=True)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 17)
    ax.axis("off")

    io_c, proc_c, m3_c, m2_c = "#dbe9f6", "#eeeeee", "#d8f0d8", "#fde9d0"

    _box(ax, 5, 16, 7.4, 1.0,
         "Input: probe time series, sampling rate $f_s$,\n"
         "water depth $h$, probe positions", io_c)
    _box(ax, 5, 14, 7.4, 1.0,
         "Preprocess: detrend, optional energy-normalized Hann window",
         proc_c)
    _box(ax, 5, 12, 7.4, 1.0,
         "Zero-crossing statistics (probe 1)\n"
         r"$\rightarrow$ representative period, peak wavelength $L_p$",
         proc_c)
    _box(ax, 5, 10, 7.4, 1.0,
         "Evaluate every probe pair: spacing ratio $\\Delta x/L$\n"
         "and 2$\\times$2 inversion conditioning", proc_c)
    _diamond(ax, 5, 7.8, 5.6, 2.0,
             "Three probes available and\n"
             "three-probe retained energy\n$\\geq$ 80%?", "#fff2b2")
    _box(ax, 2.4, 5.2, 4.2, 1.3,
         "Three-probe redundant\narray method", m3_c)
    _box(ax, 7.6, 5.2, 4.2, 1.3,
         "Best admissible\ntwo-probe pair", m2_c)
    _box(ax, 5, 2.9, 8.6, 1.2,
         "Per-frequency incident/reflected decomposition.\n"
         "Both methods discard frequencies outside the Goda band\n"
         "$0.05 \\leq \\Delta x/L \\leq 0.45$ or with ill-conditioned inversion",
         proc_c)
    _box(ax, 5, 0.8, 8.6, 1.1,
         "Output: $H_i$, $H_r$, $K_r$, incident/reflected spectra,\n"
         "diagnostics (retained-energy fraction, conditioning flags)",
         io_c)

    _arrow(ax, 5, 15.5, 5, 14.5)
    _arrow(ax, 5, 13.5, 5, 12.5)
    _arrow(ax, 5, 11.5, 5, 10.5)
    _arrow(ax, 5, 9.5, 5, 8.8)
    _arrow(ax, 3.9, 7.3, 2.4, 5.85, "yes")
    _arrow(ax, 6.1, 7.3, 7.6, 5.85, "no")
    _arrow(ax, 2.4, 4.55, 4.0, 3.5)
    _arrow(ax, 7.6, 4.55, 6.0, 3.5)
    _arrow(ax, 5, 2.3, 5, 1.35)

    path = os.path.join(fig_dir, "workflow.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fig_dir = os.path.join(here, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    fig_validation(fig_dir)
    fig_scenarios(fig_dir)
    fig_workflow(fig_dir)


if __name__ == "__main__":
    main()
