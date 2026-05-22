"""
real_data_example.py

Runs WaveLabX on a real irregular-wave (JONSWAP) laboratory record and
generates the incident/reflected/composite spectra figure for the manuscript.

The record (`data/jonswap_example.csv`) holds six wave-gauge channels sampled at
100 Hz in a still-water depth of 0.50 m, forming two independent three-gauge
arrays. Running both arrays gives two independent reflection estimates of the
same wave field and demonstrates the toolkit on real, noisy measurements.

Outputs:
  figures/realdata_spectra.png
  (stdout) diagnostics for both arrays

Run from the repository root:
    python scripts/real_data_example.py
"""

from __future__ import annotations

import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wavelabx.stats import zero_crossing
from wavelabx.three_probe import three_probe_array

FS = 100.0   # sampling frequency [Hz]
H = 0.50     # still-water depth [m]
DATA = os.path.join("data", "jonswap_example.csv")

# Two independent three-gauge arrays. `cols` selects channels (0-indexed) in
# order of increasing position along the direction of wave propagation; `gpos`
# are the corresponding gauge positions [m].
ARRAYS = [
    ("Array 1 (gauges 1-3)", [0, 1, 2], (0.0, 0.45, 0.75)),
    ("Array 2 (gauges 4-6)", [5, 4, 3], (0.0, 0.45, 0.75)),
]

BLUE, RED = "#1f77b4", "#d62728"


def _band_average(x, n_per_band=7):
    """Block-average a 1-D array into frequency bands for a cleaner plot."""
    return np.asarray([np.mean(x[i:i + n_per_band])
                       for i in range(0, len(x), n_per_band)])


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    eta6 = np.loadtxt(os.path.join(here, DATA), delimiter=",", skiprows=1)
    fig_dir = os.path.join(here, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    print(f"Record: {DATA}  ({eta6.shape[0]} samples, "
          f"{eta6.shape[1]} gauges, "
          f"fs={FS:g} Hz, h={H:g} m)\n")

    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), constrained_layout=True)

    results = []
    for ax, (name, cols, gpos) in zip(axes, ARRAYS):
        eta = eta6[:, cols]
        zc, _ = zero_crossing(eta[:, 0], FS)
        r = three_probe_array(eta, fs=FS, h=H, gpos=gpos, plot=False)
        results.append(r)

        print(f"{name}")
        print(f"  zero-crossing Hs = {zc['Hs']:.4f} m, Tmean = {zc['Tmean']:.2f} s")
        print(f"  Hi = {r['Hi']:.4f} m, Hr = {r['Hr']:.4f} m, Kr = {r['Kr']:.3f}")
        print(f"  retained energy = {r['retained_energy_fraction']:.2f}, "
              f"max condition number = {np.nanmax(r['cond_pair']):.1e}\n")

        # Band-average the spectra (display only; diagnostics use raw bins).
        fb = _band_average(r["f"])
        ax.plot(fb, _band_average(r["Si"]), color=BLUE, lw=1.4,
                label="Incident")
        ax.plot(fb, _band_average(r["Sr"]), color=RED, lw=1.4, ls="--",
                label="Reflected")
        ax.plot(fb, _band_average(r["Ssum"]), color="0.45", lw=1.0,
                label="Composite")
        ax.set_xlim(0, 2.0)
        ax.set_xlabel("Frequency [Hz]")
        ax.set_ylabel(r"$S(f)$ [m$^2$/Hz]")
        ax.set_title(name)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        ax.text(0.96, 0.94,
                f"$K_r$ = {r['Kr']:.2f}\nretained {r['retained_energy_fraction']:.0%}",
                transform=ax.transAxes, ha="right", va="top", fontsize=7.5,
                bbox=dict(boxstyle="round", fc="white", ec="0.7"))
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    path = os.path.join(fig_dir, "realdata_spectra.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")

    h1, h2 = results[0]["Hi"], results[1]["Hi"]
    print(f"\nIncident-height agreement between the two arrays: "
          f"{abs(h1 - h2) / max(h1, h2) * 100:.1f}%")


if __name__ == "__main__":
    main()
