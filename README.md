# WaveLabX

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20347447.svg)](https://doi.org/10.5281/zenodo.20347447)
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

The browser UI (`web/index.html`) routes every uploaded file through the
same routine, with the same settings (auto-detected dominant frequency `f`,
editable in the table; an optional skip-N-waves / analyse-N-waves record
window in the Settings panel). Use the **Analysis method** dropdown in
Settings to override the automatic method selection ("Auto", "Three-probe
only", or "Two-probe (best pair / 1-2 / 1-3 / 2-3)"). Each row in the
results table carries a small "3P" or "2P" badge per array, indicating
whether the row used the three-probe redundant average or a two-probe
result. The badge is also written to the exported CSV (`Method1`,
`Method2` columns). The JS↔Python parity tests in the suite cross-check
`twoProbeGoda`, `threeProbeArray` and `reflectionAnalysis` against their
Python counterparts.

## Validation cookbook

The Python package and the browser application expose the same primitives.
Use these snippets to verify our results, or to run the same analysis on
your own data.

**1. You only have two-probe data.**

```python
import numpy as np
from wavelabx import two_probe_goda

eta12 = np.loadtxt("my_two_probe_record.csv", delimiter=",", skiprows=1)
r = two_probe_goda(eta12, fs=100.0, h=0.50, gpos=(0.0, 0.45))
print(r["Hi"], r["Hr"], r["Kr"], r["retained_energy_fraction"])
```

The same record (2-column CSV) can be dropped into
[the browser application](https://wave-lab-x.vercel.app) directly — the
two-probe routine is detected automatically from the column count, and the
"2P" badge in the results table confirms it.

**2. You have a three-probe array.**

```python
from wavelabx import reflection_analysis

eta = np.loadtxt("my_three_probe.csv", delimiter=",", skiprows=1)
out = reflection_analysis(eta, fs=100.0, h=0.50, gpos=(0.0, 0.45, 0.75))
print(out["method_used"], out[out["method_used"]]["Kr"])
```

`reflection_analysis` runs the three-probe routine, evaluates all
two-probe pairs and selects three-probe when its retained-energy
fraction is at least 80%; otherwise it falls back to the best admissible
two-probe pair. Drop the same 3-column CSV in the browser tool: same
logic, same numbers, with a "3P" or "2P" badge showing which method was
chosen.

**3. You have a six-channel record (two three-probe arrays).**

```python
from wavelabx import three_probe_array

eta = np.loadtxt("data/jonswap_example.csv", delimiter=",", skiprows=1)
seaward  = three_probe_array(eta[:, 0:3], fs=100.0, h=0.50, gpos=(0.0, 0.45, 0.75))
shoreward = three_probe_array(eta[:, 3:6], fs=100.0, h=0.50, gpos=(0.0, 0.30, 0.75))
print(seaward["Hi"], seaward["Hr"], seaward["Kr"])
```

Drop the same 6-column CSV in the browser tool with matching spacings
to reproduce the values in Table&nbsp;2 of the manuscript.

**4. You want to force two-probe on a specific pair (e.g., to cross-check
the paper with a different method).**

In Python:

```python
from wavelabx import two_probe_goda
eta = np.loadtxt("data/jonswap_example.csv", delimiter=",", skiprows=1)
# Force two-probe Goda-Suzuki using gauges 1 and 3 only.
r = two_probe_goda(eta[:, [0, 2]], fs=100.0, h=0.50, gpos=(0.0, 0.75))
print(r["Hi"], r["Hr"], r["Kr"])
```

In the browser, select **Analysis method &rarr; Two-probe (gauges 1-3)**
from the settings dropdown and drop the same file. Both produce the
same numbers.

## Browser tool

**Live demo:** [wave-lab-x.vercel.app](https://wave-lab-x.vercel.app)

`web/` contains a self-contained browser application. Drop one or more
six-channel wave-gauge CSV files to get a table of incident/reflected wave
heights and reflection coefficients for both probe arrays, plus interactive
visualization (time-series, decomposed incident/reflected and raw per-probe spectrum plots with
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
> (2026). *WaveLabX* (v0.3.1) [Software]. Zenodo.
> [https://doi.org/10.5281/zenodo.20347447](https://doi.org/10.5281/zenodo.20347447)

BibTeX:

```bibtex
@software{wavelabx,
  author    = {Lamsal, Sandesh and Deveaux Garrido, Claudia and
               Haus, Brian K. and Rhode-Barbarigos, Landolf},
  title     = {WaveLabX},
  version   = {0.3.1},
  year      = {2026},
  doi       = {10.5281/zenodo.20347447},
  url       = {https://github.com/sandslamsal/WaveLabX},
  publisher = {Zenodo}
}
```

Citation metadata is also provided in `CITATION.cff`.
