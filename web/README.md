# Wave Reflection Analysis &mdash; browser application

**Live demo: [wave-lab-x.vercel.app](https://wave-lab-x.vercel.app)**

A client-side browser tool for incident&ndash;reflected wave-probe
analysis. Drop one or more CSV files; the tool returns incident and
reflected wave heights, the reflection coefficient, the retained-energy
diagnostic and (when applicable) the transmission coefficient.

This is a faithful port of the WaveLabX Python package. The numerical
core in `spectral.js` mirrors `wavelabx.two_probe_goda`,
`wavelabx.three_probe_array` and `wavelabx.analysis.reflection_analysis`;
an automated JavaScript&harr;Python cross-check confirms that all three
routines agree on identical inputs.

## Input formats

The number of channels is auto-detected from the CSV (optional header
row):

| Columns | Routine called | What it produces |
|---|---|---|
| **2** | `twoProbeGoda` | One probe pair, two-probe Goda&ndash;Suzuki |
| **3** | `reflectionAnalysis` | Single three-probe array with automatic two-probe fallback |
| **6** | two `reflectionAnalysis` calls | Two arrays (channels 1&ndash;3 seaward; 4&ndash;6 shoreward) |

A small layout tag next to each file name in the results table
(`2-probe` / `3-probe`) makes the detected layout explicit when a
record is single-array.

Water depth is read from the file name if it contains
`Depth=<value>`; otherwise the global depth in the Settings panel is
used (and may be overridden per file).

## What it computes

For every record:

| Quantity | Meaning |
|---|---|
| `Hi`, `Hr` | Spectral significant wave heights, <i>H<sub>m0</sub></i> = 4&radic;m<sub>0</sub>, of the incident and reflected components |
| `Kr` | Reflection coefficient `Hr / Hi` |
| `Kt` | Transmission coefficient `Hi2 / Hi1` (only for 6-channel records) |
| `f`, `T` | Auto-detected dominant frequency (editable in the table) and period |
| `L` | Local wavelength from the linear dispersion relation |
| Retained energy | Fraction of measured spectral energy that survived the Goda spacing band and the 2&times;2 conditioning test |
| Method badge | `3P` (three-probe redundant) or `2P` (two-probe Goda&ndash;Suzuki) per array |

## Analysis-method override

The **Analysis method** dropdown in the Settings panel forces a specific
routine, overriding the default automatic selection:

- **Auto** &mdash; three-probe with automatic two-probe fallback when
  retained-energy &lt; 80 %.
- **Three-probe only** &mdash; no fallback; rows flag a low retained
  energy if appropriate.
- **Two-probe (best pair)** &mdash; skip three-probe entirely; report
  the best admissible two-probe pair.
- **Two-probe (gauges 1&ndash;2 / 1&ndash;3 / 2&ndash;3)** &mdash; force
  that specific pair. Intended for cross-checking a published result
  with a different method.

For 2-channel CSVs the override is ignored: only two-probe
Goda&ndash;Suzuki is meaningful.

## Method

The spectral formulation is identical to the Python package
(<a href="https://github.com/sandslamsal/WaveLabX">WaveLabX</a>):
real-input DFT (Bluestein algorithm), wave number from the linear
dispersion relation &omega;&sup2; = <i>gk</i> tanh(<i>kd</i>) solved by
Newton&ndash;Raphson from a Fenton&ndash;McKee seed, per-frequency
Goda&ndash;Suzuki solve of the 2&times;2 system on every probe pair,
masking of frequencies that fall outside the Goda band
0.05 &le; &Delta;<i>x</i>/<i>L</i> &le; 0.45 or that are ill-conditioned,
pair-averaging for the three-probe case, and spectral integration to
<i>H<sub>m0</sub></i>.

Following:

> Lamsal, S., Haus, B. K. &amp; Rhode-Barbarigos, L. (2026).
> *An experimental study on wave transmission over submerged SEAHIVE&reg; breakwaters.*
> Coastal Engineering Journal.
> [doi:10.1080/21664250.2026.2661171](https://doi.org/10.1080/21664250.2026.2661171)

## Features

- **Drag-and-drop batch processing** of multiple files.
- **CSV column-count auto-detect** (2 / 3 / 6) with a per-row layout
  tag.
- **Method-override dropdown** for explicit two-probe / three-probe
  analysis and paper validation.
- **Auto-detected dominant frequency**, editable per row.
- **Skip first N waves / analyse N waves** record window.
- **Per-array 3P / 2P method badge** in the results table and in the
  exported CSV (`Method1`, `Method2` columns).
- **Global water depth** with one-click apply-to-all and per-file
  override.
- **Configurable gauge spacings** for both probe arrays.
- **Interactive visualisation** &mdash; time-series, decomposed
  incident/reflected and raw per-probe spectrum plots with zoom, pan and
  per-point readout.
- Runs **entirely client-side**; no data leaves the browser.

## Running locally

No build step. Open `index.html` directly, or serve the folder:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

## Deployment

Static site; deploys on Vercel with no configuration.
