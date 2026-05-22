# Changelog

All notable changes to WaveLabX are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.3.1] - 2026-05-22

### Added
- High-level `reflectionAnalysis()` in `web/spectral.js`, mirroring
  Python's `wavelabx.analysis.reflection_analysis`. Both modes of the
  browser application now use this unified routine, and a JS<->Python
  parity test cross-checks it against the Python reference.
- Automatic detection of the CSV column count in the browser application
  (2 / 3 / 6); the corresponding routine is selected automatically. A
  per-record layout tag ("2-probe" or "3-probe") is shown next to the
  file name when single-array data is detected.
- "Analysis method" override dropdown in the Settings panel: Auto,
  Three-probe only, Two-probe (best pair), Two-probe (gauges 1-2 / 1-3 /
  2-3). Lets users force a specific method, intended for paper
  validation.
- Per-array method-used badge in the results table ("3P" or "2P"), with
  matching color-coded styling. Also written to the exported CSV.
- Per-pair Goda spacing diagnostic: the browser's warning panel and the
  Python `three_probe_array` warning both identify the specific probe
  pair(s) outside the band 0.05 <= dx/L <= 0.45 (including the Δx/L
  value and whether each pair was below 0.05 or above 0.45), instead of
  a single aggregate "some rows" warning.
- "Validation cookbook" section in `README.md` with copy-pasteable
  Python and browser snippets for the four most common cases: 2-probe
  data, 3-probe data, 6-channel dual-array data, and forced-pair
  two-probe cross-checks.

### Changed
- The Regular / Irregular wave-type toggle in the browser application
  has been removed. The same spectral routine runs for every uploaded
  file; the previous Regular-mode affordances (auto-detected dominant
  frequency, editable f cell, optional skip-N-waves window) are now
  always available.
- CSV export rewritten with human-readable column titles ("Water depth
  (m)", "Hi - Array 1 (m)", "Method - Array 1", ...). Method values are
  exported as "Three-probe" / "Two-probe" (no HTML/badge token). A new
  "Out-of-band pairs" column carries the same per-pair Goda diagnostic
  shown on screen.
- `scripts/multi_example_test.py` and `scripts/real_data_example.py` now
  use the natural CSV channel order for the shoreward array
  (`cols=[3,4,5]`), matching the browser-application convention.
- In-page introduction in `web/index.html` and `web/README.md`
  rewritten to describe the unified spectral routine, the column-count
  auto-detect and the Analysis-method dropdown; the previous
  Hann-windowed single-frequency description is removed.
- Removed the redundant per-array X12/X23 description hints and the
  "Gauge positions from gauge N: ..." readout below each array's
  spacing inputs.

### Removed
- `paper.md` (JOSS source) and the figures it referenced
  (`figures/probessetup.png`, `figures/incident_reflected_timeseries.png`).
  `paper.bib` is no longer tracked in the repository.
- In-page single-frequency `threeProbe()` routine in `web/app.js` and
  its dead helpers (`gaugeAmplitudes`, `condHermitian2`, `cConj`,
  `COND_LIMIT`); both modes now route through
  `WaveLabXSpectral.reflectionAnalysis`.

### Fixed
- Mode-note text under the (now-removed) Regular toggle previously
  claimed "single-frequency method", which became inaccurate after the
  Regular/Irregular paths were unified.
- Channel-order convention mismatch between the Python scripts and the
  browser application that produced Hi/Hr labels swapped on the
  shoreward array.

## [0.3.0] - 2026-05-22

### Removed
- Regular / Irregular wave-type toggle in the browser application. With
  both modes now routing through the same `reflectionAnalysis` routine,
  the toggle controlled only display labels and the visibility of the
  skip-/use-N-waves window. The toggle has been removed and the
  Regular-style settings (auto-detected dominant frequency, editable
  f cell, record window) are now always available. The `getMode`,
  `applyMode` and "wavemode" radio listener have been deleted from
  `web/app.js`.

### Added
- The browser application now auto-detects the number of channels in each
  uploaded CSV and dispatches to the appropriate routine:
  2-column files run two-probe Goda-Suzuki on the single pair, 3-column
  files run the single-array three-probe routine with automatic two-probe
  fallback, and 6-column files keep the existing dual-array behaviour.
  A per-record layout tag (2-probe / 3-probe) appears next to the file
  name in the results table.
- An "Analysis method" dropdown in the Settings panel lets users override
  the automatic method selection: "Auto", "Three-probe only",
  "Two-probe (best admissible pair)" or one of "Two-probe (gauges 1-2 /
  1-3 / 2-3)" to force a specific pair. Intended for explicit two-probe
  validation against the manuscript results.
- A "Validation cookbook" section in `README.md` showing equivalent
  Python and browser snippets for the four most common cases (2-probe,
  3-probe, 6-channel, and forced-pair two-probe).
- A small info-tip next to the "Wave type" toggle clarifying that the
  Regular / Irregular toggle is display-only -- both modes call the same
  spectral routine.

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
