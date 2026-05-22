# Changelog

All notable changes to WaveLabX are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-05-22

### Added
- High-level `reflectionAnalysis()` in `web/spectral.js`, a JavaScript
  mirror of Python's `wavelabx.analysis.reflection_analysis`. It runs the
  redundant three-probe routine, evaluates the three two-probe pairs, and
  selects the three-probe result when its retained-energy fraction is at
  least 80%; otherwise it falls back to the best admissible two-probe pair.
  The browser UI and the Python package now follow the same method-selection
  pipeline.
- Cross-implementation parity test
  `test_python_js_reflection_analysis_consistency` verifying that the
  JavaScript and Python reflection-analysis pipelines pick the same method
  and agree on Hi, Hr and Kr.
- Explicit two-probe Goda–Suzuki routine in the browser core
  (`twoProbeGoda` in `web/spectral.js`), mirroring the Python
  `two_probe_goda` so both interfaces expose the same set of methods.
- Cross-implementation parity test `test_python_js_two_probe_consistency`
  verifying that the JavaScript and Python two-probe routines agree on
  identical inputs.
- Per-array method-used badge ("3P" or "2P") in the browser results table,
  with matching color-coded styling and a new `Method1` / `Method2` column
  in the CSV export.
- `scripts/multi_example_test.py` and `results/multi_example_results.csv`
  reproducing the three illustrative cases reported in the paper
  (synthetic regular, real regular, real JONSWAP irregular) with their
  per-case probe spacings and a summary CSV.
- `scripts/spacing_sweep.py` and `results/spacing_sweep.csv`, regenerating
  the two-probe spacing-sensitivity figure.
- New manuscript figures: a TikZ software-architecture diagram
  (`figures/wavelabx_architecture.tex`), a TikZ composite of the browser
  application (`figures/webapp_figure.tex`), and a wave-flume experimental
  setup figure (`figures/ExperimentalSetup.png`).
- `data/` folder containing the example datasets
  (`wavedata.csv`, `regular_example.csv`, `jonswap_example.csv`).

### Changed
- Authors expanded to: Sandesh Lamsal, Claudia Deveaux Garrido, Brian K.
  Haus and Landolf Rhode-Barbarigos.
- Per-case probe spacings are now documented in the paper, scripts and
  README: regular-wave runs use the spacings of the ExperimentalSetup
  figure (X12 = 0.60 m, X23 = 0.30 m), while the JONSWAP run uses the
  browser-application default spacings (X12 = 0.45 m, X23 = 0.30 m;
  X45 = 0.30 m, X56 = 0.45 m).
- Manuscript title shortened to "WaveLabX: A Python and web-based toolkit
  for wave statistics and incident–reflected decomposition".
- Manuscript prose softened throughout to remove implicitly first-of-kind
  and only-of-kind claims.

### Removed
- Optional energy-normalized Hann windowing in the Python package; the
  spectral analysis is consistent with the windowless browser
  implementation.

## [0.2.0] - 2026-05-15

### Added
- Three-probe redundant-array decomposition (`three_probe_array`).
- Retained-energy diagnostic and condition-number filtering.
- Browser application (`web/`) with three-probe analysis, interactive
  spectra/time-series plots and CSV export.
- Initial Zenodo archive (DOI 10.5281/zenodo.20217994).

### Changed
- Refactored Python package into `core`, `stats`, `two_probe`,
  `three_probe`, `analysis` and `sensitivity` submodules.

## [0.1.0] - 2026-03-01

### Added
- Initial public release of the Python package with the two-probe
  Goda–Suzuki method and zero-crossing wave statistics.
