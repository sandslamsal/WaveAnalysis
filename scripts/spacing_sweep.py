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
  figures/spacing_sensitivity.png   two-probe Hi error vs dx/L (with noise)
  results/spacing_sweep.csv         the two-probe sweep, machine-readable
  (stdout)                          three-probe scenario table

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


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fig_dir = os.path.join(here, "figures")
    res_dir = os.path.join(here, "results")
    os.makedirs(fig_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    print(f"Peak wavelength Lp = {LP:.3f} m  (h={H} m, Tp={TPEAK} s)")
    print(f"True: Hi = {HI:.4f} m, Kr = {KR:.3f}\n")

    # ---- Two-probe dx/L sweep, clean and noisy --------------------------
    dx_over_L = np.linspace(0.02, 0.55, 45)
    clean = two_probe_sweep(dx_over_L, noise_std=0.0)
    noisy = two_probe_sweep(dx_over_L, noise_std=0.001)  # ~3% of Hi

    # Save machine-readable results
    csv_path = os.path.join(res_dir, "spacing_sweep.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["dx_over_L", "err_Hi_pct_clean", "err_Hi_pct_noisy",
                    "err_Kr_clean", "err_Kr_noisy", "cond_max_clean"])
        for c, n in zip(clean, noisy):
            w.writerow([f"{c['dx_over_L']:.4f}", f"{c['err_Hi']:.2f}",
                        f"{n['err_Hi']:.2f}", f"{c['err_Kr']:.4f}",
                        f"{n['err_Kr']:.4f}", f"{c['cond_max']:.3e}"])
    print(f"Wrote {csv_path}")

    # ---- Figure: two-probe Hi error vs dx/L ----------------------------
    r = [d["dx_over_L"] for d in clean]
    e_clean = [d["err_Hi"] for d in clean]
    e_noisy = [d["err_Hi"] for d in noisy]

    fig, ax = plt.subplots(figsize=(7.0, 4.0), constrained_layout=True)
    ax.axhspan(-5, 5, color="0.85", label="±5% band")
    ax.axvspan(GODA_LO, GODA_HI, color="#cfe8cf", alpha=0.5,
               label=f"Goda band {GODA_LO:g}-{GODA_HI:g}")
    ax.axhline(0.0, color="0.4", linewidth=0.8)
    ax.plot(r, e_clean, "-o", ms=3, color="#1f77b4", label="noise-free")
    ax.plot(r, e_noisy, "-s", ms=3, color="#d62728",
            label="with 0.001 m noise (~3% of Hi)")
    ax.set_xlabel(r"Non-dimensional probe spacing $\Delta x / L$")
    ax.set_ylabel(r"Incident $H_{m0}$ error [%]")
    ax.set_title("Two-probe spacing sensitivity (known-truth synthetic)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig_path = os.path.join(fig_dir, "spacing_sensitivity.png")
    fig.savefig(fig_path, dpi=300, bbox_inches="tight")
    print(f"Wrote {fig_path}\n")

    # ---- Two-probe sweep summary table ---------------------------------
    print("Two-probe incident-Hm0 error vs dx/L")
    print(f"{'dx/L':>6} {'err% clean':>11} {'err% noisy':>11} {'cond_max':>11}")
    for c, n in zip(clean, noisy):
        print(f"{c['dx_over_L']:6.3f} {c['err_Hi']:11.1f} "
              f"{n['err_Hi']:11.1f} {c['cond_max']:11.2e}")

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
