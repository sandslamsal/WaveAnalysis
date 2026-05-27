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

from wavelabx.core import compute_wavelength
from wavelabx.stats import zero_crossing
from wavelabx.three_probe import three_probe_array

FS = 100.0   # sampling frequency [Hz]
H = 0.50     # still-water depth [m]
DATA = os.path.join("data", "jonswap_example.csv")

# Two independent three-gauge arrays. `cols` selects channels (0-indexed) in
# order of increasing position along the direction of wave propagation; `gpos`
# are the corresponding gauge positions [m].
ARRAYS = [
    # Channels are read in natural CSV order to match the browser application
    # (web/app.js); positions follow the browser-application defaults. Only
    # the seaward array is plotted in the manuscript figure.
    ("Seaward array (gauges 1-3)", [0, 1, 2], (0.0, 0.45, 0.75)),
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

    plt.rcParams.update({
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
    })
    nax = len(ARRAYS)
    fig, axes = plt.subplots(1, nax, figsize=(5.6 * nax, 3.6),
                             constrained_layout=True, squeeze=False)
    axes = axes.flatten()

    results = []
    for ax, (name, cols, gpos) in zip(axes, ARRAYS):
        eta = eta6[:, cols]
        zc, _ = zero_crossing(eta[:, 0], FS)
        r = three_probe_array(eta, fs=FS, h=H, gpos=gpos, plot=False)
        results.append(r)

        Lp = compute_wavelength(H, zc["Tmean"])
        print(f"{name}")
        print(f"  zero-crossing Hs = {zc['Hs']:.4f} m, Tmean = {zc['Tmean']:.2f} s, "
              f"Lp = {Lp:.3f} m")
        print(f"  Hi = {r['Hi']:.4f} m, Hr = {r['Hr']:.4f} m, Kr = {r['Kr']:.3f}")
        print(f"  retained energy = {r['retained_energy_fraction']:.2f}, "
              f"max condition number = {np.nanmax(r['cond_pair']):.1e}\n")

        # Band-average the spectra (display only; diagnostics use raw bins).
        fb = _band_average(r["f"])
        Si = _band_average(r["Si"])
        Sr = _band_average(r["Sr"])
        Ss = _band_average(r["Ssum"])
        ax.fill_between(fb, 0, Si, color=BLUE, alpha=0.12)
        ax.plot(fb, Ss, color="0.55", lw=1.0, label="Composite")
        ax.plot(fb, Si, color=BLUE, lw=1.8, label=r"Incident $S_i(f)$")
        ax.plot(fb, Sr, color=RED,  lw=1.6, ls="--", label=r"Reflected $S_r(f)$")

        # Annotate the spectral peak
        ipk = int(np.nanargmax(Si))
        fpk = fb[ipk]
        ax.axvline(fpk, color="0.65", lw=0.7, ls=":")
        ax.annotate(f"$f_p={fpk:.2f}$ Hz",
                    xy=(fpk, Si[ipk]),
                    xytext=(8, -2), textcoords="offset points",
                    fontsize=8.5, color="0.30")

        ax.set_xlim(0, 2.0)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Frequency $f$ [Hz]")
        ax.set_ylabel(r"Spectral density $S(f)$ [m$^{2}$/Hz]")
        ax.grid(alpha=0.25, lw=0.5)
        ax.legend(loc="upper right", frameon=False)

        # Result panel in the upper-left of the axes
        info = (
            f"$H_i = {r['Hi']*100:.2f}$ cm\n"
            f"$H_r = {r['Hr']*100:.2f}$ cm\n"
            f"$K_r = {r['Kr']:.3f}$\n"
            f"retained energy: {r['retained_energy_fraction']*100:.0f}%"
        )
        ax.text(0.02, 0.97, info,
                transform=ax.transAxes, ha="left", va="top", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.7"))
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    path = os.path.join(fig_dir, "realdata_spectra.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")

    # Note: the script now plots only the seaward array (channels 1-3),
    # which matches the figure used in the manuscript.


if __name__ == "__main__":
    main()
