"""
core.py

Shared constants and core wave-mechanics utilities for WaveLabX.
"""

import numpy as np

GRAVITY = 9.81


def compute_wavelength(h: float, T: float, tol: float = 1e-10,
                       max_iter: int = 100) -> float:
    """Linear wavelength L for water depth h and wave period T.

    Solves the linear dispersion relation

        omega**2 = g k tanh(k h),   omega = 2 pi / T,   k = 2 pi / L

    for the wavenumber k using Newton-Raphson iteration, started from the
    explicit Fenton & McKee (1990) approximation. Unlike the plain
    fixed-point iteration L = L0 tanh(k h), Newton-Raphson converges
    reliably across the full depth range, from deep to shallow water.

    Parameters
    ----------
    h : float
        Still-water depth [m].
    T : float
        Wave period [s].
    tol : float, optional
        Relative convergence tolerance on the wavenumber k.
    max_iter : int, optional
        Maximum number of Newton iterations.

    Returns
    -------
    L : float
        Linear wavelength [m].
    """
    g = GRAVITY
    if T <= 0.0 or h <= 0.0:
        raise ValueError("Water depth h and period T must both be positive.")

    omega = 2.0 * np.pi / T

    # Fenton & McKee (1990) explicit initial estimate of the wavelength.
    L_deep = g * T ** 2 / (2.0 * np.pi)
    L_fm = L_deep * np.tanh((omega ** 2 * h / g) ** 0.75) ** (2.0 / 3.0)
    k = 2.0 * np.pi / L_fm

    # Newton-Raphson on f(k) = g k tanh(k h) - omega**2.
    for _ in range(max_iter):
        th = np.tanh(k * h)
        f = g * k * th - omega ** 2
        dfdk = g * th + g * k * h * (1.0 - th ** 2)
        dk = f / dfdk
        k -= dk
        if abs(dk) <= tol * k:
            break

    return float(2.0 * np.pi / k)
