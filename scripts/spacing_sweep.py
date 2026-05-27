"""
spacing_sweep.py

Reproducible probe-spacing sensitivity analysis for WaveLabX.

This script directly addresses the SoftwareX review request for:
  * a systematic assessment of probe-spacing effects, and
  * quantified error trends as the non-dimensional spacing dx/L varies.

It generates known-truth synthetic three-gauge records via linear wave
theory (see wavelabx.sensitivity), runs the WaveLabX algorithms, and
compares the recovered incident/reflected wave heights against the truth.

Outputs
-------
  figures/spacing_sensitivity.png   two-panel figure: two-probe (left)
                                    and three-probe (right) Hi error vs
                                    dx/L, both clean and noisy
  results/spacing_sweep.csv         per-dx/L errors for both methods,
                                    machine-readable
  (stdout)                          three-probe scenario table (best /
                                    mixed / worst geometries)

Run from the repository root:
    python scripts/spacing_sweep.py
"""

from __future__ import annotations

import csv
import io
import os
from contextlib import redirect_stdout

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wavelabx.core import compute_wavelength
from wavelabx.sensitivity import _synthetic_irregular_gauges, spacing_sensitivity
from wavelabx.two_probe import two_probe_goda
from wavelabx.three_probe import three_probe_array

# --- Fixed wave / sampling parameters for the known-truth synthetic case ----
FS = 100.0        # sampling frequency [Hz]
DURATION = 200.0  # record length [s]
H = 0.25          # water depth [m]
TPEAK = 1.33      # peak period [s]
HI = 0.035        # true incident Hm0 [m]
KR = 0.15         # true reflection coefficient [-]

LP = compute_wavelength(H, TPEAK)  # peak wavelength [m]

# Goda (1976) admissible spacing band
GODA_LO, GODA_HI = 0.05, 0.45


def two_probe_sweep(dx_over_L, noise_std=0.0, seed0=1000):
    """Run two-probe analysis over a range of dx/L on known-truth data."""
    rows = []
    for i, r in enumerate(dx_over_L):
        dx = r * LP
        gpos = (0.0, dx, 2.0 * dx)
        eta, truth = _synthetic_irregular_gauges(
            fs=FS, duration=DURATION, h=H, gpos=gpos,
            Tpeak=TPEAK, Hi=HI, Kr=KR, seed=seed0 + i, noise_std=noise_std,
        )
        # Suppress the per-call ill-conditioning warnings during the sweep.
        with redirect_stdout(io.StringIO()):
            out = two_probe_goda(
                eta[:, [0, 1]], fs=FS, h=H, gpos=(gpos[0], gpos[1]),
                plot=False,
            )
        rows.append(dict(
            dx_over_L=float(r),
            Hi=float(out["Hi"]),
            err_Hi=100.0 * (out["Hi"] - truth.Hi) / truth.Hi,
            Hr=float(out["Hr"]),
            err_Hr=100.0 * (out["Hr"] - truth.Hr) / truth.Hr,
            Kr=float(out["Kr"]),
            err_Kr=float(out["Kr"] - truth.Kr),
            cond_max=float(np.nanmax(out["cond"])),
        ))
    return rows


def three_probe_sweep(dx_over_L, noise_std=0.0, seed0=2000):
    """Three-probe sweep with equal-spacing geometry (X12 = X23 = dx).

    For each dx/L, the three gauges sit at (0, dx, 2*dx). This makes the
    1D sweep directly comparable to the two-probe case while still
    exercising the redundant three-probe routine and its per-pair Goda
    + conditioning masking.
    """
    rows = []
    for i, r in enumerate(dx_over_L):
        dx = r * LP
        gpos = (0.0, dx, 2.0 * dx)
        eta, truth = _synthetic_irregular_gauges(
            fs=FS, duration=DURATION, h=H, gpos=gpos,
            Tpeak=TPEAK, Hi=HI, Kr=KR, seed=seed0 + i, noise_std=noise_std,
        )
        with redirect_stdout(io.StringIO()):
            out = three_probe_array(eta, fs=FS, h=H, gpos=gpos, plot=False)
        Hi_t = truth.Hi
        Hr_t = truth.Hr
        rows.append(dict(
            dx_over_L=float(r),
            Hi=float(out["Hi"]),
            err_Hi=100.0 * (out["Hi"] - Hi_t) / Hi_t,
            Hr=float(out["Hr"]),
            err_Hr=100.0 * (out["Hr"] - Hr_t) / Hr_t,
            Kr=float(out["Kr"]),
            err_Kr=float(out["Kr"] - KR),
            retained=float(out["retained_energy_fraction"]),
        ))
    return rows


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fig_dir = os.path.join(here, "figures")
    res_dir = os.path.join(here, "results")
    os.makedirs(fig_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    print(f"Peak wavelength Lp = {LP:.3f} m  (h={H} m, Tp={TPEAK} s)")
    print(f"True: Hi = {HI:.4f} m, Kr = {KR:.3f}\n")

    # ---- Two- and three-probe dx/L sweeps, multiple noise levels --------
    # Noise levels expressed as fractions of the true incident Hi.
    noise_levels_pct = [0, 3, 10, 30]
    dx_over_L = np.linspace(0.02, 0.55, 45)
    two_runs, three_runs = {}, {}
    for pct in noise_levels_pct:
        sigma = (pct / 100.0) * HI
        two_runs[pct] = two_probe_sweep(dx_over_L, noise_std=sigma)
        three_runs[pct] = three_probe_sweep(dx_over_L, noise_std=sigma)

    # Save machine-readable results (both methods, all noise levels)
    csv_path = os.path.join(res_dir, "spacing_sweep.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        header = ["dx_over_L"]
        for pct in noise_levels_pct:
            header += [
                f"2P_err_Hi_pct_n{pct}",
                f"3P_err_Hi_pct_n{pct}",
                f"3P_retained_n{pct}",
            ]
        w.writerow(header)
        for i in range(len(dx_over_L)):
            row = [f"{dx_over_L[i]:.4f}"]
            for pct in noise_levels_pct:
                row += [
                    f"{two_runs[pct][i]['err_Hi']:.2f}",
                    f"{three_runs[pct][i]['err_Hi']:.2f}",
                    f"{three_runs[pct][i]['retained']:.3f}",
                ]
            w.writerow(row)
    print(f"Wrote {csv_path}")

    # ---- Combined two-panel figure: 2P (left) + 3P (right) -------------
    # Each method gets its own colour family so the method identity is
    # visually obvious even before reading the title; within each panel
    # the noise level is encoded by line shade plus marker shape.
    panel_styles = {
        "a": {  # two-probe — blue family
            "title_color": "#0b3d91",
            "noise": {
                0:  {"color": "#000000", "marker": "o", "label": "noise-free"},
                3:  {"color": "#5b8fd6", "marker": "s", "label": r"3\% of $H_i$"},
                10: {"color": "#1f5fa6", "marker": "^", "label": r"10\% of $H_i$"},
                30: {"color": "#0b3d91", "marker": "D", "label": r"30\% of $H_i$"},
            },
        },
        "b": {  # three-probe — orange/red family
            "title_color": "#993300",
            "noise": {
                0:  {"color": "#000000", "marker": "o", "label": "noise-free"},
                3:  {"color": "#f6b26b", "marker": "s", "label": r"3\% of $H_i$"},
                10: {"color": "#e6692a", "marker": "^", "label": r"10\% of $H_i$"},
                30: {"color": "#a32a04", "marker": "D", "label": r"30\% of $H_i$"},
            },
        },
    }

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6),
                             constrained_layout=True, sharey=True)
    for ax, runs, title, key in zip(
        axes,
        (two_runs, three_runs),
        ("(a) Two-probe Goda--Suzuki",
         "(b) Three-probe redundant array (equal spacing)"),
        ("a", "b"),
    ):
        pstyle = panel_styles[key]
        ax.axhspan(-5, 5, color="0.88", label=r"$\pm 5\%$ band",
                   zorder=0)
        ax.axvspan(GODA_LO, GODA_HI, color="#d6ead6", alpha=0.55,
                   label=f"Goda band {GODA_LO:g}-{GODA_HI:g}", zorder=0)
        ax.axhline(0.0, color="0.4", linewidth=0.6, zorder=0)
        for pct in noise_levels_pct:
            ns = pstyle["noise"][pct]
            ax.plot([d["dx_over_L"] for d in runs[pct]],
                    [d["err_Hi"] for d in runs[pct]],
                    linestyle="-", marker=ns["marker"], ms=4.0,
                    lw=1.4, color=ns["color"], label=ns["label"],
                    markeredgecolor=ns["color"],
                    markerfacecolor="white",
                    markeredgewidth=1.1, zorder=3)
        ax.set_xlabel(r"Non-dimensional probe spacing $\Delta x / L$")
        ax.set_title(title, loc="left", fontsize=10.5,
                     color=pstyle["title_color"], fontweight="bold")
        ax.grid(alpha=0.3)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(fontsize=8, loc="lower right", ncol=1, frameon=True)
    axes[0].set_ylabel(r"Incident $H_{m0}$ error [%]")
    fig_path = os.path.join(fig_dir, "spacing_sensitivity.png")
    fig.savefig(fig_path, dpi=300, bbox_inches="tight")
    print(f"Wrote {fig_path}\n")

    # ---- Two-probe sweep summary table (all noise levels) --------------
    print("Two-probe incident-Hm0 error vs dx/L (% of true Hi)")
    head = "  dx/L  " + "  ".join([f" n={p}%" for p in noise_levels_pct])
    print(head)
    for i in range(len(dx_over_L)):
        row = [f"{dx_over_L[i]:6.3f}"]
        for pct in noise_levels_pct:
            row.append(f"{two_runs[pct][i]['err_Hi']:6.1f}")
        print("  ".join(row))

    # ---- Three-probe sweep summary table (all noise levels) ------------
    print("\nThree-probe incident-Hm0 error vs dx/L (equal spacing)")
    print(head)
    for i in range(len(dx_over_L)):
        row = [f"{dx_over_L[i]:6.3f}"]
        for pct in noise_levels_pct:
            row.append(f"{three_runs[pct][i]['err_Hi']:6.1f}")
        print("  ".join(row))

    # ---- Three-probe scenario assessment (reviewer comment 4) -----------
    print("\n" + "=" * 72)
    print("Three-probe scenario assessment")
    print("=" * 72)
    scenarios = {
        "one pair admissible, others not": (0.0, 0.10, 0.60),
        "two pairs marginal, geometry OK": (0.0, 0.35, 0.70),
        "all pairs too closely spaced":    (0.0, 0.05, 0.10),
    }
    with redirect_stdout(io.StringIO()):
        sweep = spacing_sensitivity(gpos_sets=list(scenarios.values()))
    truth = sweep["truth"]
    for (label, gpos), res in zip(scenarios.items(), sweep["results"]):
        th = res["three_probe"]
        adm = sum(tp["goda_admissible"] for tp in res["two_probe"])
        print(f"\n  {label}")
        print(f"    gpos={gpos}  admissible pairs={adm}/3")
        print(f"    3-probe Hi err = {100*th['err_Hi']/truth['Hi']:+6.1f}%   "
              f"Hr err = {100*th['err_Hr']/truth['Hr']:+6.1f}%   "
              f"Kr err = {th['err_Kr']:+.3f}")
        print(f"    retained energy = {th['retained_energy_fraction']:.2f}   "
              f"-> {'RELIABLE' if th['retained_energy_fraction'] >= 0.8 else 'FLAGGED UNRELIABLE'}")


if __name__ == "__main__":
    main()
