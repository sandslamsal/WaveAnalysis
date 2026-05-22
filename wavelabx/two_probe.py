"""
two_probe.py

Two-probe incident-reflected wave decomposition (Goda & Suzuki, 1976).

The decomposition uses the same per-pair spectral formulation as the
three-probe array method (see ``three_probe.py``), applied to a single
probe pair. At every frequency the 2x2 system is solved for the incident
and reflected Fourier coefficients; a frequency is retained only where

  * the pair satisfies the Goda spacing guideline 0.05 <= dx/L <= 0.45, and
  * the 2x2 inversion is acceptably conditioned.

All other frequencies are discarded. Sharing one formulation between the
two-probe and three-probe routines guarantees the two methods are mutually
consistent.
"""

from __future__ import annotations

import os

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import detrend

from .core import compute_wavelength

# Goda (1976) admissible non-dimensional probe spacing dx / L.
GODA_MIN = 0.05
GODA_MAX = 0.45


def two_probe_goda(
    eta12: np.ndarray,
    fs: float,
    h: float,
    gpos: tuple[float, float],
    plot: bool = False,
    cond_warn: float = 1e3,
    cond_max: float = 1e6,
    figures_dir: str = "figures",
    save_prefix: str = "twoprobe",
) -> dict:
    """Two-probe incident-reflected decomposition (Goda & Suzuki method).

    Parameters
    ----------
    eta12 : np.ndarray
        (N x 2) free-surface elevations [m]; column 0 = probe 1, 1 = probe 2.
    fs : float
        Sampling frequency [Hz].
    h : float
        Mean water depth [m].
    gpos : tuple of float
        (x1, x2) probe positions [m] along the flume. Order is irrelevant;
        the probes are sorted internally so the spacing is positive.
    plot : bool, optional
        If True, save an incident/reflected spectra figure to ``figures_dir``.
    cond_warn : float, optional
        Print a warning if any retained frequency exceeds this condition number.
    cond_max : float, optional
        Discard frequencies whose 2x2 inversion exceeds this condition number.
    figures_dir, save_prefix : str, optional
        Output directory and filename prefix used when ``plot`` is True.

    Returns
    -------
    dict
        Keys: ``Kr``, ``Hi``, ``Hr`` (reflection coefficient and incident /
        reflected spectral wave heights Hm0 [m]); ``Si``, ``Sr``, ``f``
        (incident / reflected spectra [m^2/Hz] and frequency [Hz]); ``cond``,
        ``bad_cond``, ``valid`` (per-frequency diagnostics);
        ``retained_energy_fraction`` and ``valid_index_range``.
    """
    eta12 = np.asarray(eta12, dtype=float)
    if eta12.ndim != 2 or eta12.shape[1] != 2:
        raise ValueError("eta12 must be a 2D array with shape (N, 2).")

    x1, x2 = float(gpos[0]), float(gpos[1])
    z = detrend(eta12, axis=0, type="constant")

    # Order probes by position so dx > 0 and the algebra is unambiguous.
    if x1 > x2:
        x1, x2 = x2, x1
        z = z[:, ::-1]
    dx = abs(x2 - x1)

    N = int(z.shape[0])
    fs = float(fs)
    dt = 1.0 / fs
    nfft = N
    df = 1.0 / (nfft * dt)
    half = nfft // 2
    if half < 2:
        raise ValueError("Time series too short for spectral decomposition.")

    # Cosine/sine Fourier coefficients and one-sided auto-spectrum per probe.
    An = np.zeros((half - 1, 2))
    Bn = np.zeros((half - 1, 2))
    Sn = np.zeros((half - 1, 2))
    for j in range(2):
        fn = np.fft.fft(z[:, j], nfft)
        An[:, j] = 2.0 * np.real(fn[1:half]) / nfft
        Bn[:, j] = -2.0 * np.imag(fn[1:half]) / nfft
        Sn[:, j] = dt * np.real(2.0 * (fn * np.conj(fn))[1:half]) / nfft

    f = df * np.arange(1, half)

    # Wavenumber from the linear dispersion relation.
    k = np.zeros_like(f)
    for i, fi in enumerate(f):
        if fi > 0.0:
            k[i] = 2.0 * np.pi / compute_wavelength(h, 1.0 / fi)

    # Conditioning of the 2x2 complex inversion matrix at each frequency.
    cond = np.full_like(f, np.nan)
    for i in range(len(f)):
        if k[i] <= 0.0:
            continue
        M = np.array(
            [[np.exp(-1j * k[i] * x1), np.exp(1j * k[i] * x1)],
             [np.exp(-1j * k[i] * x2), np.exp(1j * k[i] * x2)]],
            dtype=complex,
        )
        try:
            cond[i] = np.linalg.cond(M)
        except Exception:
            cond[i] = np.inf
    bad_cond = cond > cond_max

    # Per-pair incident/reflected Fourier coefficients.
    # This is the identical algebra used per pair in three_probe.py, which
    # keeps the two-probe and three-probe results mutually consistent.
    A1, A2 = An[:, 0], An[:, 1]
    B1, B2 = Bn[:, 0], Bn[:, 1]
    s1, c1 = np.sin(k * x1), np.cos(k * x1)
    s2, c2 = np.sin(k * x2), np.cos(k * x2)
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = 2.0 * np.sin(k * dx)
        Ainc = (-A2 * s1 + A1 * s2 + B2 * c1 - B1 * c2) / denom
        Binc = (A2 * c1 - A1 * c2 + B2 * s1 - B1 * s2) / denom
        Aref = (-A2 * s1 + A1 * s2 - B2 * c1 + B1 * c2) / denom
        Bref = (A2 * c1 - A1 * c2 - B2 * s1 + B1 * s2) / denom

    # Retain only frequencies inside the Goda spacing band and well conditioned.
    # The spacing factor 1/(2 sin(k dx)) is unbounded near k dx = n*pi; the
    # Goda band keeps it bounded (|sin(k dx)| >= ~0.3), so no clamping is used.
    with np.errstate(divide="ignore", invalid="ignore"):
        dx_over_L = k * dx / (2.0 * np.pi)
    valid = (
        (dx_over_L >= GODA_MIN) & (dx_over_L <= GODA_MAX)
        & (~bad_cond) & (k > 0.0)
    )
    for arr in (Ainc, Binc, Aref, Bref):
        arr[~valid] = np.nan

    if np.any(valid & (cond > cond_warn)):
        worst = np.nanmax(cond[valid]) if np.any(valid) else np.nan
        print(
            f"[WaveLabX] Warning: two-probe inversion is ill-conditioned at "
            f"some retained frequencies (max cond ~ {worst:.2e})."
        )

    # Incident / reflected spectra and integrated spectral wave heights.
    Si = (Ainc ** 2 + Binc ** 2) / (2.0 * df)
    Sr = (Aref ** 2 + Bref ** 2) / (2.0 * df)
    Ei = np.nansum(Si) * df
    Er = np.nansum(Sr) * df
    Hi = 4.0 * np.sqrt(Ei) if Ei > 0 else 0.0
    Hr = 4.0 * np.sqrt(Er) if Er > 0 else 0.0
    Kr = Hr / Hi if Hi > 0 else np.nan

    # Retained-energy diagnostic (probe-1 auto-spectrum).
    total_energy = np.nansum(Sn[:, 0]) * df
    retained_energy = np.nansum(Sn[valid, 0]) * df if total_energy > 0 else 0.0
    retained_energy_fraction = (
        retained_energy / total_energy if total_energy > 0 else np.nan
    )

    valid_idx = np.where(valid)[0]
    valid_index_range = (
        (int(valid_idx[0]), int(valid_idx[-1])) if valid_idx.size else (0, 0)
    )

    if plot:
        os.makedirs(figures_dir, exist_ok=True)
        fig, ax = plt.subplots(figsize=(7.0, 3.2), constrained_layout=True)
        ax.plot(f, Si, color="#1f77b4", linewidth=1.2, label="Incident spectrum")
        ax.plot(f, Sr, color="#d62728", linewidth=1.2, linestyle="--",
                label="Reflected spectrum")
        ax.set_xlabel("Frequency [Hz]")
        ax.set_ylabel(r"$S(f)$ [m$^2$/Hz]")
        ax.set_title("Two-probe Goda reflection spectra")
        ax.grid(alpha=0.3)
        ax.legend()
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        fig.savefig(os.path.join(figures_dir, f"{save_prefix}_spectra.png"),
                    dpi=300, bbox_inches="tight")
        plt.close(fig)

    return {
        "Kr": Kr,
        "Hi": Hi,
        "Hr": Hr,
        "Si": Si,
        "Sr": Sr,
        "f": f,
        "cond": cond,
        "bad_cond": bad_cond,
        "valid": valid,
        "retained_energy_fraction": retained_energy_fraction,
        "valid_index_range": valid_index_range,
    }
