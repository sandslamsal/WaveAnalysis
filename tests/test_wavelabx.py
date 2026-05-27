"""
Test suite for WaveLabX.

The reflection-analysis tests use known-truth synthetic gauge records
generated from linear wave theory (wavelabx.sensitivity), so the recovered
incident/reflected wave heights can be checked against an exact answer.
This locks both the two-probe and three-probe methods against silent
regressions.
"""

import json
import os
import shutil
import subprocess
import tempfile

import numpy as np
import pytest

from wavelabx import (
    GRAVITY,
    compute_wavelength,
    zero_crossing,
    two_probe_goda,
    three_probe_array,
    reflection_analysis,
)
from wavelabx.sensitivity import _synthetic_irregular_gauges

# Shared synthetic-case parameters.
FS = 100.0
DURATION = 200.0
H = 0.25
TPEAK = 1.33
HI = 0.035
KR = 0.15


# --------------------------------------------------------------------------
# core: dispersion relation
# --------------------------------------------------------------------------
def test_compute_wavelength_deep_water():
    """In deep water L approaches the deep-water limit g T^2 / (2 pi)."""
    T = 2.0
    L = compute_wavelength(h=1000.0, T=T)
    L_deep = GRAVITY * T ** 2 / (2.0 * np.pi)
    assert abs(L - L_deep) / L_deep < 1e-3


def test_compute_wavelength_shallow_water():
    """In shallow water L approaches the shallow-water limit T*sqrt(g h)."""
    T = 12.0
    h = 0.4
    L = compute_wavelength(h=h, T=T)
    L_shallow = T * np.sqrt(GRAVITY * h)
    assert abs(L - L_shallow) / L_shallow < 0.05


# --------------------------------------------------------------------------
# stats: zero-crossing
# --------------------------------------------------------------------------
def test_zero_crossing_monochromatic():
    """A monochromatic wave of amplitude A has height 2A and period T."""
    A, T = 0.05, 1.0
    t = np.arange(0.0, 120.0, 1.0 / FS)
    eta = A * np.sin(2.0 * np.pi * t / T)
    res, names = zero_crossing(eta, FS)
    assert abs(res["Hmean"] - 2.0 * A) / (2.0 * A) < 0.05
    assert abs(res["Tmean"] - T) / T < 0.05
    assert set(names).issubset(res.keys())


# --------------------------------------------------------------------------
# reflection analysis against known truth
# --------------------------------------------------------------------------
@pytest.fixture
def synthetic_array():
    """Well-spaced three-gauge synthetic record with known Hi, Hr, Kr."""
    eta, truth = _synthetic_irregular_gauges(
        fs=FS, duration=DURATION, h=H, gpos=(0.0, 0.35, 0.70),
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=42,
    )
    return eta, truth


def test_three_probe_recovers_truth(synthetic_array):
    eta, truth = synthetic_array
    out = three_probe_array(eta, fs=FS, h=H, gpos=truth.gpos)
    assert abs(out["Hi"] - truth.Hi) / truth.Hi < 0.10
    assert abs(out["Hr"] - truth.Hr) / truth.Hr < 0.20
    assert abs(out["Kr"] - truth.Kr) < 0.03
    assert out["retained_energy_fraction"] > 0.8


def test_two_probe_recovers_truth(synthetic_array):
    """A well-spaced probe pair recovers the incident height and Kr."""
    eta, truth = synthetic_array
    out = two_probe_goda(
        eta[:, [0, 2]], fs=FS, h=H, gpos=(truth.gpos[0], truth.gpos[2])
    )
    assert abs(out["Hi"] - truth.Hi) / truth.Hi < 0.12
    assert abs(out["Kr"] - truth.Kr) < 0.04
    # the recovered factor must not blow up: a sane Kr stays well below 1
    assert 0.0 < out["Kr"] < 0.5


def test_two_probe_probe_order_is_irrelevant(synthetic_array):
    """Swapping the two probes (and their positions) gives the same answer."""
    eta, truth = synthetic_array
    a = two_probe_goda(eta[:, [0, 2]], fs=FS, h=H,
                       gpos=(truth.gpos[0], truth.gpos[2]))
    b = two_probe_goda(eta[:, [2, 0]], fs=FS, h=H,
                       gpos=(truth.gpos[2], truth.gpos[0]))
    assert abs(a["Hi"] - b["Hi"]) < 1e-9
    assert abs(a["Hr"] - b["Hr"]) < 1e-9


def test_two_and_three_probe_consistent(synthetic_array):
    """The two methods agree closely on a clean, well-spaced array."""
    eta, truth = synthetic_array
    tp = two_probe_goda(eta[:, [0, 2]], fs=FS, h=H,
                        gpos=(truth.gpos[0], truth.gpos[2]))
    th = three_probe_array(eta, fs=FS, h=H, gpos=truth.gpos)
    assert abs(tp["Hi"] - th["Hi"]) / th["Hi"] < 0.12


def test_three_probe_flags_unreliable_geometry():
    """When all probes are too closely spaced the method flags low retained energy."""
    eta, truth = _synthetic_irregular_gauges(
        fs=FS, duration=DURATION, h=H, gpos=(0.0, 0.05, 0.10),
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=1,
    )
    out = three_probe_array(eta, fs=FS, h=H, gpos=(0.0, 0.05, 0.10))
    assert out["retained_energy_fraction"] < 0.8


def test_reflection_analysis_end_to_end(synthetic_array):
    """The high-level workflow runs and selects a method."""
    eta, truth = synthetic_array
    out = reflection_analysis(eta, fs=FS, h=H, gpos=truth.gpos)
    assert out["method_used"] in ("two_probe", "three_probe")
    assert np.isfinite(out["Hs"])
    assert np.isfinite(out["Lp"])
    assert "three_probe" in out


# --------------------------------------------------------------------------
# cross-implementation check: the browser port must match the Python reference
# --------------------------------------------------------------------------
_NODE = shutil.which("node")
_JS_RUNNER_3P = os.path.join(os.path.dirname(__file__), "js_three_probe_runner.js")
_JS_RUNNER_2P = os.path.join(os.path.dirname(__file__), "js_two_probe_runner.js")
_JS_RUNNER_REF = os.path.join(os.path.dirname(__file__), "js_reflection_runner.js")
_JS_RUNNER_PERIOD = os.path.join(os.path.dirname(__file__), "js_period_runner.js")


@pytest.mark.skipif(_NODE is None, reason="Node.js not available")
def test_python_js_three_probe_consistency():
    """web/spectral.js reproduces wavelabx.three_probe_array on identical data."""
    gpos = (0.0, 0.35, 0.70)
    eta, _ = _synthetic_irregular_gauges(
        fs=FS, duration=120.0, h=H, gpos=gpos,
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=7,
    )
    py = three_probe_array(eta, fs=FS, h=H, gpos=gpos)

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        json.dump({"eta": eta.tolist(), "fs": FS, "h": H, "pos": list(gpos)}, tmp)
        tmp.close()
        proc = subprocess.run(
            [_NODE, _JS_RUNNER_3P, tmp.name],
            capture_output=True, text=True, check=True,
        )
        js = json.loads(proc.stdout)
    finally:
        os.unlink(tmp.name)

    assert abs(js["Hi"] - py["Hi"]) / py["Hi"] < 1e-3
    assert abs(js["Hr"] - py["Hr"]) / py["Hr"] < 1e-3
    assert abs(js["Kr"] - py["Kr"]) < 1e-3


@pytest.mark.skipif(_NODE is None, reason="Node.js not available")
def test_python_js_two_probe_consistency():
    """web/spectral.js twoProbeGoda reproduces wavelabx.two_probe_goda."""
    gpos = (0.0, 0.35, 0.70)
    eta, _ = _synthetic_irregular_gauges(
        fs=FS, duration=120.0, h=H, gpos=gpos,
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=11,
    )
    # use probes 1 and 3 (gpos[0] and gpos[2]) for the two-probe pair
    eta2 = eta[:, [0, 2]]
    pos2 = (gpos[0], gpos[2])
    py = two_probe_goda(eta2, fs=FS, h=H, gpos=pos2)

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        json.dump({"eta": eta2.tolist(), "fs": FS, "h": H,
                   "pos": list(pos2)}, tmp)
        tmp.close()
        proc = subprocess.run(
            [_NODE, _JS_RUNNER_2P, tmp.name],
            capture_output=True, text=True, check=True,
        )
        js = json.loads(proc.stdout)
    finally:
        os.unlink(tmp.name)

    # Tolerances are slightly looser than the three-probe test because the
    # browser DFT (Bluestein) and numpy.fft.fft sum bins in different orders,
    # producing small floating-point differences that are well below the
    # measurement uncertainty of a wave-flume experiment.
    assert abs(js["Hi"] - py["Hi"]) / py["Hi"] < 5e-3
    assert abs(js["Hr"] - py["Hr"]) / py["Hr"] < 5e-3
    assert abs(js["Kr"] - py["Kr"]) < 5e-3


@pytest.mark.skipif(_NODE is None, reason="Node.js not available")
def test_python_js_reflection_analysis_consistency():
    """web/spectral.js reflectionAnalysis reproduces wavelabx.reflection_analysis."""
    gpos = (0.0, 0.35, 0.70)
    eta, _ = _synthetic_irregular_gauges(
        fs=FS, duration=120.0, h=H, gpos=gpos,
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=13,
    )
    py = reflection_analysis(eta, fs=FS, h=H, gpos=gpos)
    py_method = py["method_used"]
    py_pick = py["three_probe"] if py_method == "three_probe" else py["two_probe_best"]

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        json.dump({"eta": eta.tolist(), "fs": FS, "h": H, "pos": list(gpos)}, tmp)
        tmp.close()
        proc = subprocess.run(
            [_NODE, _JS_RUNNER_REF, tmp.name],
            capture_output=True, text=True, check=True,
        )
        js = json.loads(proc.stdout)
    finally:
        os.unlink(tmp.name)

    # Same method selected on both sides.
    assert js["method_used"] == py_method, (
        f"Method mismatch: js={js['method_used']}, py={py_method}")
    # Numeric agreement on whichever method was selected.
    assert abs(js["Hi"] - py_pick["Hi"]) / py_pick["Hi"] < 5e-3
    assert abs(js["Hr"] - py_pick["Hr"]) / py_pick["Hr"] < 5e-3
    assert abs(js["Kr"] - py_pick["Kr"]) < 5e-3


@pytest.mark.skipif(_NODE is None, reason="Node.js not available")
def test_python_js_period_consistency():
    """JS reports the same Tm (zero-crossing) and Tp (spectral peak) as Python
    on the same record. This locks the new period-display toggle: switching
    between Tp and Tm in the web app must produce numerically identical
    period/wavelength values to the Python pipeline.
    """
    gpos = (0.0, 0.35, 0.70)
    eta, _ = _synthetic_irregular_gauges(
        fs=FS, duration=120.0, h=H, gpos=gpos,
        Tpeak=TPEAK, Hi=HI, Kr=KR, seed=23,
    )
    py_zc, _ = zero_crossing(eta[:, 0], FS)
    py_th = three_probe_array(eta, fs=FS, h=H, gpos=gpos)

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        json.dump({"eta": eta.tolist(), "fs": FS, "h": H, "pos": list(gpos)}, tmp)
        tmp.close()
        proc = subprocess.run(
            [_NODE, _JS_RUNNER_PERIOD, tmp.name],
            capture_output=True, text=True, check=True,
        )
        js = json.loads(proc.stdout)
    finally:
        os.unlink(tmp.name)

    # Zero-crossing mean period agrees to <0.5% (faithful port).
    assert abs(js["Tm"] - py_zc["Tmean"]) / py_zc["Tmean"] < 5e-3
    # Spectral peak Tp agrees within one FFT bin (Bluestein-vs-numpy
    # ordering can shift the peak by at most one bin on borderline cases).
    py_Tp = py_th["Tp"]
    if py_Tp == py_Tp and py_Tp > 0:
        df = FS / eta.shape[0]
        tol = max(1.0 / (py_Tp - df) - 1.0 / py_Tp,
                  1.0 / py_Tp - 1.0 / (py_Tp + df))
        assert abs(js["Tp"] - py_Tp) <= 2 * tol
