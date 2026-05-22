"""
multi_example_test.py

Three contrasting tests of the WaveLabX three-probe method:
  (1) a synthetic regular wave with a prescribed reflection coefficient
      (controlled, known truth);
  (2) a real regular-wave laboratory record;
  (3) a real irregular-wave (JONSWAP) laboratory record.

Gauge spacings used:
  - Regular-wave run (synthetic + real regular): the wave-flume layout shown
    in figure ExperimentalSetup, X12=0.60 m, X23=0.30 m for the seaward
    array; the shoreward array has X45=0.30 m, X56=0.60 m.
  - JONSWAP irregular-wave run: the WaveLabX browser-application default
    spacings, X12=0.45 m, X23=0.30 m for the seaward array; X45=0.30 m,
    X56=0.45 m for the shoreward array.

Outputs a per-case statistics table on stdout and as CSV in results/.
"""

from __future__ import annotations

import csv
import io
import os
from contextlib import redirect_stdout

import numpy as np

from wavelabx.core import compute_wavelength
from wavelabx.three_probe import three_probe_array

FS = 100.0                       # sampling rate [Hz] (lab standard)

# Regular-wave (real + synthetic) gauge positions: ExperimentalSetup figure.
ARR1_REG = (0.0, 0.60, 0.90)     # seaward array, X12=0.60, X23=0.30
ARR2_REG = (0.0, 0.60, 0.90)     # shoreward array (P6,P5,P4 reorder): X56=0.60, X45=0.30

# JONSWAP irregular-wave gauge positions: browser-app default spacings.
ARR1_JON = (0.0, 0.45, 0.75)     # seaward array, X12=0.45, X23=0.30
ARR2_JON = (0.0, 0.45, 0.75)     # shoreward array (P6,P5,P4 reorder): X56=0.45, X45=0.30


def synthetic_regular(fs, duration, h, gpos, Tp, a_i, a_r, seed=11):
    """Generate a 3-gauge monochromatic record: incident + reflected at Tp."""
    rng = np.random.default_rng(seed)
    N = int(round(duration * fs))
    t = np.arange(N) / fs
    L = compute_wavelength(h, Tp)
    k = 2.0 * np.pi / L
    omega = 2.0 * np.pi / Tp
    phi_i, phi_r = rng.uniform(0, 2 * np.pi, size=2)
    eta = np.zeros((N, 3))
    for j, x in enumerate(gpos):
        eta[:, j] = (a_i * np.cos(omega * t - k * x + phi_i)
                     + a_r * np.cos(omega * t + k * x + phi_r))
    # For a monochromatic component of amplitude a: variance = a^2/2, so
    # m0 = a^2/2 and Hm0 = 4*sqrt(m0) = 2*sqrt(2)*a.
    Hi_true = 2.0 * np.sqrt(2.0) * a_i
    Hr_true = 2.0 * np.sqrt(2.0) * a_r
    return eta, Hi_true, Hr_true, a_r / a_i


def run(eta, h, gpos):
    with redirect_stdout(io.StringIO()):
        return three_probe_array(eta, fs=FS, h=h, gpos=gpos, plot=False)


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(here, "results")
    os.makedirs(out_dir, exist_ok=True)
    rows = []

    # ---- Case 1: Synthetic regular + known reflection ----------------------
    # Spacings as in figure ExperimentalSetup (X12=0.60, X23=0.30).
    eta, Hi_t, Hr_t, Kr_t = synthetic_regular(
        fs=FS, duration=120.0, h=0.50, gpos=ARR1_REG,
        Tp=1.25, a_i=0.040, a_r=0.012,  # true Kr = 0.300
    )
    r = run(eta, 0.50, ARR1_REG)
    rows.append({
        "case": "Synthetic regular",
        "wave": "regular", "array": "synthetic 3-gauge",
        "Hi": r["Hi"], "Hr": r["Hr"], "Kr": r["Kr"],
        "retained": r["retained_energy_fraction"],
        "Hi_true": Hi_t, "Hr_true": Hr_t, "Kr_true": Kr_t,
    })

    # ---- Case 2: Real regular-wave laboratory record -----------------------
    # Same probe spacings as figure ExperimentalSetup.
    eta6 = np.loadtxt(os.path.join(here, "data", "regular_example.csv"),
                      delimiter=",", skiprows=1)
    h_reg = 0.35
    for name, cols, gpos, side in [
        ("Regular wave -- array 1", [0, 1, 2], ARR1_REG, "seaward"),
        ("Regular wave -- array 2", [5, 4, 3], ARR2_REG, "shoreward"),
    ]:
        r = run(eta6[:, cols], h_reg, gpos)
        rows.append({
            "case": name, "wave": "regular", "array": side,
            "Hi": r["Hi"], "Hr": r["Hr"], "Kr": r["Kr"],
            "retained": r["retained_energy_fraction"],
            "Hi_true": "", "Hr_true": "", "Kr_true": "",
        })

    # ---- Case 3: Real irregular-wave (JONSWAP) record ---------------------
    # Browser-app default spacings.
    eta6 = np.loadtxt(os.path.join(here, "data", "jonswap_example.csv"),
                      delimiter=",", skiprows=1)
    h_jon = 0.50
    for name, cols, gpos, side in [
        ("JONSWAP -- array 1", [0, 1, 2], ARR1_JON, "seaward"),
        ("JONSWAP -- array 2", [5, 4, 3], ARR2_JON, "shoreward"),
    ]:
        r = run(eta6[:, cols], h_jon, gpos)
        rows.append({
            "case": name, "wave": "irregular", "array": side,
            "Hi": r["Hi"], "Hr": r["Hr"], "Kr": r["Kr"],
            "retained": r["retained_energy_fraction"],
            "Hi_true": "", "Hr_true": "", "Kr_true": "",
        })

    # ---- Print + save ------------------------------------------------------
    header = f"{'Case':28} {'Type':10} {'Hi':>7} {'Hr':>7} {'Kr':>6} {'ret.':>5}  true Kr  Kr error"
    print(header)
    print("-" * len(header))
    for row in rows:
        if row["Kr_true"] != "":
            tkr = f"{row['Kr_true']:.3f}"
            kerr = f"{(row['Kr']-row['Kr_true'])/row['Kr_true']*100:+5.1f}%"
        else:
            tkr, kerr = "  --  ", "   --  "
        print(f"{row['case']:28} {row['wave']:10} "
              f"{row['Hi']:7.4f} {row['Hr']:7.4f} {row['Kr']:6.3f} "
              f"{row['retained']:5.2f}  {tkr}  {kerr}")

    csv_path = os.path.join(out_dir, "multi_example_results.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "wave", "array", "Hi_m", "Hr_m", "Kr",
                    "retained_energy", "Hi_true_m", "Hr_true_m", "Kr_true"])
        for r in rows:
            w.writerow([r["case"], r["wave"], r["array"],
                        f"{r['Hi']:.4f}", f"{r['Hr']:.4f}", f"{r['Kr']:.3f}",
                        f"{r['retained']:.2f}",
                        f"{r['Hi_true']:.4f}" if r["Hi_true"] != "" else "",
                        f"{r['Hr_true']:.4f}" if r["Hr_true"] != "" else "",
                        f"{r['Kr_true']:.3f}" if r["Kr_true"] != "" else ""])
    print(f"\nSaved -> {csv_path}")


if __name__ == "__main__":
    main()
