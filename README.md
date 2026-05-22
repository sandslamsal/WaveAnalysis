# WaveLabX

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20217994.svg)](https://doi.org/10.5281/zenodo.20217994)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

WaveLabX is an open-source toolkit for laboratory wave-probe analysis. It
provides reproducible wave statistics and incident–reflected decomposition
through a Python package and a zero-install, client-side browser application,
both built on the same per-frequency Goda–Suzuki spectral formulation.

- Zero-crossing wave statistics from single-probe records
- Two-probe Goda–Suzuki frequency-domain decomposition
- Three-probe redundant-array decomposition with validity filtering
- Per-frequency probe-spacing checks, condition-number monitoring and a
  retained-energy diagnostic
- Identical numerical core in Python and JavaScript; an automated cross-check
  in the test suite confirms agreement on identical inputs

![WaveLabX workflow and architecture](figures/wavelabx_architecture.pdf)

## Installation

Recommended: use a Python virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Minimal usage

```python
import numpy as np
from wavelabx import reflection_analysis

# eta: (N, 3) array of probe elevations [m]
eta = np.loadtxt("data/wavedata.csv", delimiter=",", skiprows=1)

out = reflection_analysis(eta, fs=100.0, h=0.25, gpos=(0.0, 0.35, 0.70))
tp = out["three_probe"]
print(out["method_used"], tp["Kr"], tp["retained_energy_fraction"])
```

See `run_wavelabx_example.ipynb` for a step-by-step walkthrough and
`scripts/` for the figure/table generators that accompany the paper.

## Methods: two-probe and three-probe

Both methods share one per-frequency spectral formulation, so the two-probe
result is exactly a single-pair version of the three-probe averaged result.

Python entry points (`wavelabx` package):

- `two_probe_goda(eta12, fs, h, gpos)` — explicit two-probe Goda–Suzuki on a
  single co-linear pair.
- `three_probe_array(eta123, fs, h, gpos)` — redundant three-probe array;
  averages the three valid probe pairs at each frequency.
- `reflection_analysis(eta, fs, h, gpos)` — high-level wrapper that runs the
  three-probe routine, evaluates all three two-probe pairs, and selects the
  three-probe result when it retains at least 80% of the spectral energy;
  otherwise it falls back to the best admissible two-probe pair.

JavaScript entry points (`web/spectral.js`):

- `twoProbeGoda(col1, col2, fs, h, pos1, pos2)` — mirror of `two_probe_goda`.
- `threeProbeArray(cols, fs, h, pos)` — mirror of `three_probe_array`.
- `reflectionAnalysis(cols, fs, h, pos)` — mirror of `reflection_analysis`;
  same method-selection logic, same numbers.

The browser UI (`web/index.html`) routes both Regular and Irregular wave
modes through `reflectionAnalysis`. The toggle now controls only the UI
(peak-frequency display, skip/use-waves window) — the analysis path itself is
identical in both modes and matches the Python pipeline. Each row in the
results table carries a small "3P" or "2P" badge per array, indicating
whether the row used the three-probe redundant average or the best
two-probe fallback. The badge is also written to the exported CSV
(`Method1`, `Method2` columns). The JS↔Python parity tests in the suite
cross-check `twoProbeGoda`, `threeProbeArray` and `reflectionAnalysis`
against their Python counterparts.

## Browser tool

**Live demo:** [wave-lab-x.vercel.app](https://wave-lab-x.vercel.app)

`web/` contains a self-contained browser application. Drop one or more
six-channel wave-gauge CSV files to get a table of incident/reflected wave
heights and reflection coefficients for both probe arrays, plus interactive
visualization (time-series, energy-spectrum and power-spectrum plots with
zoom, pan and per-point readouts). It runs entirely client-side; no
installation, no server, no data upload.

To run locally, open `web/index.html` or serve the folder:

```bash
cd web && python3 -m http.server 8000
```

## Repository layout

- `wavelabx/` — Python package source (API in docstrings)
- `web/` — browser-based analysis and visualization tool
- `data/` — example datasets (`wavedata.csv`, `regular_example.csv`,
  `jonswap_example.csv`)
- `scripts/` — reproducible scripts that regenerate the paper figures and
  tables (`make_figures.py`, `spacing_sweep.py`, `real_data_example.py`,
  `multi_example_test.py`)
- `tests/` — pytest suite, including JS↔Python cross-checks for the two- and
  three-probe routines (requires Node.js for the cross-checks)
- `figures/` — paper figures and the source `*.tex` for the TikZ diagrams
- `results/` — machine-readable outputs of the scripts
- `run_wavelabx_example.ipynb` — annotated example notebook
- `paper_submission.tex` — manuscript source

## Running the test suite

```bash
pip install -e .
pip install pytest
pytest tests/
```

The JS↔Python parity tests are auto-skipped if Node.js is not available.

## License

WaveLabX is released under the MIT License (see `LICENSE`).

## How to cite

If you use WaveLabX in your research, please cite the archived software
release:

> Lamsal, S., Deveaux Garrido, C., Haus, B. K., & Rhode-Barbarigos, L.
> (2026). *WaveLabX* (v0.3.0) [Software]. Zenodo.
> [https://doi.org/10.5281/zenodo.20217994](https://doi.org/10.5281/zenodo.20217994)

BibTeX:

```bibtex
@software{wavelabx,
  author    = {Lamsal, Sandesh and Deveaux Garrido, Claudia and
               Haus, Brian K. and Rhode-Barbarigos, Landolf},
  title     = {WaveLabX},
  version   = {0.3.0},
  year      = {2026},
  doi       = {10.5281/zenodo.20217994},
  url       = {https://github.com/sandslamsal/WaveLabX},
  publisher = {Zenodo}
}
```

Citation metadata is also provided in `CITATION.cff`.
