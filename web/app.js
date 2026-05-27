/* =========================================================================
 * Wave Reflection Analysis — three-probe method
 *   Goda & Suzuki (1976); Kobayashi, Cox & Wurjanto (1990)
 * Pure client-side. No data leaves the browser.
 * ========================================================================= */

"use strict";

const G = 9.81;            // gravitational acceleration [m/s^2]
const DL_MIN = 0.05;       // valid spacing range  0.05 <= dl/L <= 0.45
const DL_MAX = 0.45;
// Displayed in the footer as "Last update". Update this string whenever a
// user-visible change is shipped to main (Vercel auto-deploys from main).
const LAST_UPDATE = "27 May 2026, 14:00 UTC";

/* ---------------------------------------------------------------------------
 * Linear dispersion relation  omega^2 = g k tanh(k d)  -> wave number k
 * ------------------------------------------------------------------------- */
function dispersion(freq, depth) {
  const omega = 2 * Math.PI * freq;
  const target = omega * omega;
  let k = target / G; // deep-water guess
  if (!isFinite(k) || k <= 0) return target / G;
  for (let it = 0; it < 100; it++) {
    const th = Math.tanh(k * depth);
    const F = G * k * th - target;
    const dF = G * th + G * k * depth * (1 - th * th);
    if (Math.abs(dF) < 1e-30) break;
    const kNew = k - F / dF;
    if (kNew <= 0) { k = k / 2; continue; }
    if (Math.abs(kNew - k) < 1e-12) { k = kNew; break; }
    k = kNew;
  }
  return k;
}
const wavelength = (freq, depth) => (2 * Math.PI) / dispersion(freq, depth);

/* ---------------------------------------------------------------------------
 * Hann window of length N (cached).
 * ------------------------------------------------------------------------- */
const _hannCache = {};
function hann(N) {
  if (_hannCache[N]) return _hannCache[N];
  const w = new Float64Array(N);
  let s = 0;
  for (let n = 0; n < N; n++) {
    w[n] = 0.5 * (1 - Math.cos((2 * Math.PI * n) / (N - 1)));
    s += w[n];
  }
  w.sum = s;
  _hannCache[N] = w;
  return w;
}

/* Per-column mean (DC offset). */
function colMean(col) {
  let m = 0;
  for (let n = 0; n < col.length; n++) m += col[n];
  return m / col.length;
}

/* ---------------------------------------------------------------------------
 * Detect the dominant wave frequency from a signal, within [fmin,fmax].
 * Uses the gauge with the largest variance; band-limited DFT magnitude scan
 * with a twiddle-factor recurrence for speed.
 * ------------------------------------------------------------------------- */
function detectFrequency(columns, fs, fmin, fmax) {
  // pick the strongest gauge
  let sig = columns[0], bestVar = -1;
  for (const c of columns) {
    const m = colMean(c);
    let v = 0;
    for (let n = 0; n < c.length; n++) v += (c[n] - m) * (c[n] - m);
    if (v > bestVar) { bestVar = v; sig = c; }
  }
  const N = sig.length;
  const mean = colMean(sig);
  const w = hann(N);
  const df = fs / N;
  const iLo = Math.max(1, Math.floor(fmin / df));
  const iHi = Math.min(Math.floor(N / 2), Math.ceil(fmax / df));
  if (iHi <= iLo) return null;

  let bestMag = -1, bestIdx = iLo;
  for (let idx = iLo; idx <= iHi; idx++) {
    const ang = (-2 * Math.PI * idx) / N;
    const cs = Math.cos(ang), sn = Math.sin(ang);
    let tr = 1, ti = 0;        // twiddle^n
    let re = 0, im = 0;
    for (let n = 0; n < N; n++) {
      const v = (sig[n] - mean) * w[n];
      re += v * tr;
      im += v * ti;
      const ntr = tr * cs - ti * sn;
      ti = tr * sn + ti * cs;
      tr = ntr;
    }
    const mag = re * re + im * im;
    if (mag > bestMag) { bestMag = mag; bestIdx = idx; }
  }
  return bestIdx * df;
}

/* ---------------------------------------------------------------------------
 * Note: the in-page single-frequency three-probe routine that used to live
 * here has been removed. Both Regular and Irregular modes now route through
 * WaveLabXSpectral.reflectionAnalysis (see web/spectral.js), which mirrors
 * Python's wavelabx.analysis.reflection_analysis: a redundant three-probe
 * with automatic fallback to the best admissible two-probe pair when the
 * three-probe retained-energy falls below 80%.
 * ------------------------------------------------------------------------- */

/* ---------------------------------------------------------------------------
 * CSV parsing — accept 2, 3 or 6 numeric columns, optional header row.
 * The number of columns determines the analysis layout:
 *   2 columns  -> one probe pair (two-probe Goda-Suzuki)
 *   3 columns  -> one three-probe array (reflectionAnalysis with auto fallback)
 *   6 columns  -> two three-probe arrays (current default)
 * Records with other column counts are clipped to the nearest supported layout.
 * ------------------------------------------------------------------------- */
function parseCSV(text) {
  const lines = text.split(/\r?\n/);
  let nCols = null;
  const cols = [];
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li].trim();
    if (!line) continue;
    const parts = line.split(/[,;\t]/);
    if (parts.length < 2) continue;
    const vals = parts.map((p) => parseFloat(p));
    if (vals.some((v) => Number.isNaN(v))) continue;   // header / junk row
    if (nCols === null) {
      // Determine layout from the first numeric row.
      const n = vals.length;
      nCols = n >= 6 ? 6 : n >= 3 ? 3 : n >= 2 ? 2 : 0;
      if (!nCols) return null;
      for (let c = 0; c < nCols; c++) cols.push([]);
    }
    for (let c = 0; c < nCols; c++) cols[c].push(vals[c]);
  }
  return cols.length ? cols : null;
}

/* Water depth from file name (frequency is detected from the signal). */
function parseDepth(name) {
  const d = name.match(/Depth\s*=\s*([0-9]*\.?[0-9]+)/i);
  return d ? parseFloat(d[1]) : null;
}

/* =========================================================================
 * APPLICATION
 * ========================================================================= */
const state = { records: [] };
let nextId = 1;
const $ = (id) => document.getElementById(id);

function getSettings() {
  const fs = parseFloat($("fs").value) || 100;
  const fmin = parseFloat($("fmin").value) || 0.1;
  const fmax = parseFloat($("fmax").value) || 2.0;
  const depth = parseFloat($("depth").value) || 0.25;
  // Each array is defined by two spacings (X12, X23); gauge positions
  // are 0, X12, X12+X23. For 2-probe data only the first spacing is used.
  const spacings = (cls) => {
    const s = [...document.querySelectorAll(cls)]
      .sort((a, b) => a.dataset.i - b.dataset.i)
      .map((el) => parseFloat(el.value) || 0);
    return [0, s[0], s[0] + s[1]];
  };
  const pos1 = spacings(".sp1");
  const pos2 = spacings(".sp2");
  const skipWaves = Math.max(0, parseInt($("skipWaves").value, 10) || 0);
  const numWaves = Math.max(0, parseInt($("numWaves").value, 10) || 0);
  // Method override (Tier 2): "auto" | "3p_only" | "2p_best" |
  //   "2p_1_2" | "2p_1_3" | "2p_2_3"
  const methSel = $("methodOverride");
  const method = methSel && methSel.value ? methSel.value : "auto";
  // Period & wavelength display: "Tp" (spectral peak, default) or "Tm"
  // (zero-crossing mean). Switches the f/T/L columns and CSV.
  const pdSel = $("periodDisplay");
  const periodMode = pdSel && pdSel.value === "Tm" ? "Tm" : "Tp";
  return { fs, fmin, fmax, depth, skipWaves, numWaves, pos1, pos2, method, periodMode };
}

/* Analyse one record. redetect = re-run frequency detection. */
function analyzeRecord(rec, redetect) {
  rec.error = null;
  const s = getSettings();

  if (!rec.cols || rec.cols[0].length < 16) {
    rec.error = "Not a valid time series (need >= 16 samples)";
    rec.result = null;
    return;
  }

  // Layout: "single2" (2 probes), "single3" (1 array of 3), "dual6" (2 arrays).
  const nCols = rec.cols.length;
  rec.layout = nCols === 2 ? "single2" : nCols === 3 ? "single3" : "dual6";

  if (!(rec.depth > 0)) {
    rec.error = "Set water depth";
    rec.result = null;
    return;
  }
  const SP = typeof WaveLabXSpectral !== "undefined" ? WaveLabXSpectral
    : typeof window !== "undefined" ? window.WaveLabXSpectral : null;
  if (!SP) {
    rec.error = "Spectral module not loaded";
    rec.result = null;
    return;
  }

  // Helper: run the chosen method on one array (returns same shape as
  // reflectionAnalysis: { Hi, Hr, Kr, retained, method_used, ... }).
  const runArray = (cols3, pos3) => {
    const meth = s.method;
    if (meth === "3p_only") {
      const r = SP.threeProbeArray(cols3, s.fs, rec.depth, pos3);
      r.method_used = "three_probe";
      return r;
    }
    if (meth === "2p_best") {
      const r = SP.reflectionAnalysis(cols3, s.fs, rec.depth, pos3,
                                      { preferThreeProbe: false });
      return r;
    }
    if (meth === "2p_1_2" || meth === "2p_1_3" || meth === "2p_2_3") {
      const map = { "2p_1_2": [0, 1], "2p_1_3": [0, 2], "2p_2_3": [1, 2] };
      const [i, j] = map[meth];
      const r = SP.twoProbeGoda(cols3[i], cols3[j], s.fs, rec.depth, pos3[i], pos3[j]);
      r.method_used = "two_probe";
      r.pair = [i + 1, j + 1];
      return r;
    }
    // "auto" (default)
    return SP.reflectionAnalysis(cols3, s.fs, rec.depth, pos3);
  };

  // Regular mode supports an optional analysis window (skip-N-waves /
  // use-N-waves), which slices the record before the spectral routine runs.
  // The window needs an approximate wave period; we use the auto-detected
  // peak frequency.
  let cols = rec.cols;
  rec.windowInfo = null;
  if (redetect && !rec.freqManual) {
    const f = detectFrequency(rec.cols.slice(0, Math.min(3, rec.cols.length)),
                              s.fs, s.fmin, s.fmax);
    if (f) rec.freq = f;
  }
  if ((s.skipWaves > 0 || s.numWaves > 0) && rec.freq > 0) {
    const N = rec.cols[0].length;
    const spw = s.fs / rec.freq;                 // samples per wave
    let start = Math.round(s.skipWaves * spw);
    let len = s.numWaves > 0 ? Math.round(s.numWaves * spw) : N - start;
    start = Math.min(Math.max(start, 0), N);
    len = Math.min(Math.max(len, 0), N - start);
    if (len < 16) {
      rec.error = "Analysis window too short - reduce skip or increase waves";
      rec.result = null;
      return;
    }
    cols = rec.cols.map((c) => c.slice(start, start + len));
    rec.windowInfo = { start, len, waves: len / spw };
  }

  try {
    // Dispatch by record layout. Single-array records (2 or 3 columns) are
    // analysed once; the dual-array case (6 columns) is analysed twice with
    // the same routine. All branches use the Python-parity routines exposed
    // by web/spectral.js.
    let a1, a2;
    if (rec.layout === "single2") {
      // Two-probe Goda-Suzuki on the (only) pair. Method override is ignored
      // here because only twoProbeGoda makes sense for two-channel data.
      a1 = SP.twoProbeGoda(cols[0], cols[1], s.fs, rec.depth,
                           s.pos1[0], s.pos1[1]);
      a1.method_used = "two_probe";
      a2 = null;
    } else if (rec.layout === "single3") {
      a1 = runArray(cols, s.pos1);
      a2 = null;
    } else {
      // dual6 (default)
      a1 = runArray(cols.slice(0, 3), s.pos1);
      a2 = runArray(cols.slice(3, 6), s.pos2);
    }

    // Peak frequency / period (from the incident spectrum): prefer the
    // spectral peak from the analysis when the user has not manually edited
    // f; fall back to the detected frequency otherwise.
    if (!rec.freqManual && a1 && a1.fp) rec.freq = a1.fp;
    const Tp = (a1 && a1.Tp != null && Number.isFinite(a1.Tp)) ? a1.Tp
      : (rec.freq > 0 ? 1 / rec.freq : NaN);
    const fp = Number.isFinite(Tp) && Tp > 0 ? 1 / Tp : NaN;
    const Lp = Number.isFinite(fp) && fp > 0
      ? wavelength(fp, rec.depth) : NaN;

    // Zero-crossing mean period (Tm) on probe 1. Always computed so the
    // user can switch the display via the Period & wavelength toggle
    // without re-running the analysis.
    let Tm = NaN, fm = NaN, Lm = NaN;
    try {
      const zc = SP.zeroCrossing(cols[0], s.fs);
      if (zc && Number.isFinite(zc.Tmean) && zc.Tmean > 0) {
        Tm = zc.Tmean;
        fm = 1 / Tm;
        Lm = wavelength(fm, rec.depth);
      }
    } catch (_) { /* zero-crossing failure: leave NaN */ }

    // Goda spacing diagnostic: compute against both Lp and Lm so the
    // out-of-band display can follow the toggle.
    const pairsOf = (pos, labels) => {
      const out = [];
      for (let i = 0; i < pos.length; i++)
        for (let j = i + 1; j < pos.length; j++)
          out.push({ i, j, dx: Math.abs(pos[j] - pos[i]),
                     label: `(${labels[i]}-${labels[j]})` });
      return out;
    };
    const godaAt = (pairs, Lref) => {
      const fails = [];
      if (!(Number.isFinite(Lref) && Lref > 0)) return fails;
      for (const p of pairs) {
        const r = p.dx / Lref;
        if (r < DL_MIN) fails.push({ label: p.label, ratio: r, reason: "low" });
        else if (r > DL_MAX) fails.push({ label: p.label, ratio: r, reason: "high" });
      }
      return fails;
    };
    const labels1 = rec.layout === "single2" ? [1, 2] : [1, 2, 3];
    const labels2 = [4, 5, 6];
    const pos1 = rec.layout === "single2" ? s.pos1.slice(0, 2) : s.pos1;
    const pp1 = pairsOf(pos1, labels1);
    const pp2 = a2 ? pairsOf(s.pos2, labels2) : [];
    const outOfBand1_p = godaAt(pp1, Lp);
    const outOfBand2_p = godaAt(pp2, Lp);
    const outOfBand1_m = godaAt(pp1, Lm);
    const outOfBand2_m = godaAt(pp2, Lm);

    // Whether a two-probe fallback was selected for either array.
    const fallback1 = a1 && a1.method_used === "two_probe";
    const fallback2 = a2 && a2.method_used === "two_probe";
    const r1 = (a1 && Number.isFinite(a1.retained)) ? a1.retained : NaN;
    const r2 = (a2 && Number.isFinite(a2.retained)) ? a2.retained : NaN;
    const ret = a2 ? Math.min(r1, r2) : r1;

    rec.result = {
      layout: rec.layout,
      Hi1: a1 ? a1.Hi : null, Hr1: a1 ? a1.Hr : null, Kr1: a1 ? a1.Kr : null,
      Hi2: a2 ? a2.Hi : null, Hr2: a2 ? a2.Hr : null, Kr2: a2 ? a2.Kr : null,
      Kt: (a1 && a2 && a1.Hi > 0) ? a2.Hi / a1.Hi : null,
      // Period / frequency / wavelength in both flavours; renderTable and
      // exportCSV pick one set based on the periodMode toggle.
      Tp, fp, Lp, Tm, fm, Lm,
      // Backward-compatible aliases (period/L still used by older render
      // paths and any external consumers that read rec.result directly).
      period: Tp, L: Lp,
      method1: a1 ? a1.method_used : null,
      method2: a2 ? a2.method_used : null,
      fallback: fallback1 || fallback2,
      outOfBand1_p, outOfBand2_p, outOfBand1_m, outOfBand2_m,
      // Default-mode aliases for legacy callers; renderTable/CSV will use
      // the mode-specific arrays directly via getDisplayPeriod().
      outOfBand1: outOfBand1_p, outOfBand2: outOfBand2_p,
      ratioWarn: outOfBand1_p.length > 0 || outOfBand2_p.length > 0
              || outOfBand1_m.length > 0 || outOfBand2_m.length > 0,
      retained: ret, retainedWarn: Number.isFinite(ret) && !(ret >= 0.8),
      spectral: true,
    };
  } catch (e) {
    rec.error = "Computation failed: " + e.message;
    rec.result = null;
  }
}

function analyzeAll(redetect) {
  state.records.forEach((r) => analyzeRecord(r, redetect));
  renderTable();
}

/* ---------------------------------------------------------------------------
 * Rendering
 * ------------------------------------------------------------------------- */
const fmt = (x, p = 4) =>
  x == null || Number.isNaN(x) ? "&mdash;" : Number(x).toFixed(p);

function renderTable() {
  const body = $("resultsBody");
  body.innerHTML = "";
  let anyFallback = false, anyRetained = false;

  const s = getSettings();
  const mode = s.periodMode;            // "Tp" or "Tm"
  // Update column headers to match the toggle.
  const sub = mode === "Tm" ? "m" : "p";
  const thF = $("th-f"); if (thF) thF.innerHTML = `<i>f</i><sub>${sub}</sub> (Hz)`;
  const thT = $("th-T"); if (thT) thT.innerHTML = `<i>T</i><sub>${sub}</sub> (s)`;
  const thL = $("th-L"); if (thL) thL.innerHTML = `<i>L</i><sub>${sub}</sub> (m)`;

  state.records.forEach((rec) => {
    const tr = document.createElement("tr");
    const r = rec.result;
    if (r && r.fallback) anyFallback = true;
    if (r && r.retainedWarn) anyRetained = true;

    const depthCell = `<td class="editable">
        <input type="number" step="0.01" min="0" value="${rec.depth ?? ""}"
               data-id="${rec.id}" data-field="depth" /></td>`;
    // f cell: editable spectral-peak input in Tp mode (drives windowing).
    // In Tm mode it shows the zero-crossing-derived fm read-only.
    let freqCell;
    if (mode === "Tm") {
      const fmVal = r && Number.isFinite(r.fm) ? r.fm.toFixed(3) : "";
      freqCell = `<td title="zero-crossing mean frequency (read-only)">${fmVal || "&mdash;"}</td>`;
    } else {
      const freqVal = rec.freq != null ? rec.freq.toFixed(3) : "";
      freqCell = `<td class="editable">
          <input type="number" step="0.001" min="0" value="${freqVal}"
                 data-id="${rec.id}" data-field="freq" /></td>`;
    }

    if (rec.error) {
      tr.innerHTML = `
        <td title="${rec.name}">${rec.name}</td>
        ${depthCell}${freqCell}
        <td colspan="9" class="badge-err">${rec.error}</td>
        <td><button class="row-del" data-del="${rec.id}">&times;</button></td>`;
    } else {
      // ratioWarn now combines both Tp and Tm Goda checks; recompute for the
      // active mode so the row warning matches what's visible on screen.
      const oob1 = mode === "Tm" ? r.outOfBand1_m : r.outOfBand1_p;
      const oob2 = mode === "Tm" ? r.outOfBand2_m : r.outOfBand2_p;
      const ratioWarnMode = (oob1 && oob1.length > 0) || (oob2 && oob2.length > 0);
      const warnRow = r.fallback || ratioWarnMode || r.retainedWarn;
      const cls = warnRow ? ' class="fallback"' : "";
      const flag = warnRow ? " &#9888;" : "";
      const badge = (m) => {
        if (m == null) return "";
        return m === "two_probe"
          ? '<span class="meth-2p" title="Two-probe Goda-Suzuki">2P</span>'
          : '<span class="meth-3p" title="Three-probe redundant array">3P</span>';
      };
      const m1 = badge(r.method1);
      const m2 = badge(r.method2);
      const layoutTag = r.layout === "single2" ? ' <span class="lay-tag">2-probe</span>'
        : r.layout === "single3" ? ' <span class="lay-tag">3-probe</span>'
        : "";
      const Tshow = mode === "Tm" ? r.Tm : r.Tp;
      const Lshow = mode === "Tm" ? r.Lm : r.Lp;
      tr.innerHTML = `
        <td title="${rec.name}">${rec.name}${flag}${layoutTag}</td>
        ${depthCell}${freqCell}
        <td>${fmt(Tshow, 3)}</td>
        <td>${fmt(Lshow, 3)}</td>
        <td${cls}>${fmt(r.Hi1)} ${m1}</td>
        <td${cls}>${fmt(r.Hr1)}</td>
        <td${cls}>${fmt(r.Kr1, 3)}</td>
        <td${cls}>${fmt(r.Hi2)} ${m2}</td>
        <td${cls}>${fmt(r.Hr2)}</td>
        <td${cls}>${fmt(r.Kr2, 3)}</td>
        <td>${fmt(r.Kt, 3)}</td>
        <td><button class="row-del" data-del="${rec.id}">&times;</button></td>`;
    }
    body.appendChild(tr);
  });

  $("rowCount").innerHTML =
    state.records.length ? `&middot; ${state.records.length} file(s)` : "";
  $("resultsCard").hidden = state.records.length === 0;

  const warn = $("warnNote");
  const msgs = [];
  if (anyFallback)
    msgs.push("&#9888; A two-gauge fallback was used where the three-gauge " +
      "system was ill-conditioned (spacing near a multiple of L/2).");

  // Build a per-row, per-pair Goda-spacing report listing exactly which
  // probe pair fell outside 0.05 <= dx/L <= 0.45. The diagnostic uses
  // whichever wavelength (Lp or Lm) matches the active toggle.
  const ratioRows = [];
  state.records.forEach((rec) => {
    const r = rec.result;
    if (!r) return;
    const oob1 = mode === "Tm" ? (r.outOfBand1_m || []) : (r.outOfBand1_p || []);
    const oob2 = mode === "Tm" ? (r.outOfBand2_m || []) : (r.outOfBand2_p || []);
    const fails = [
      ...oob1.map((f) => ({ ...f, arr: r.layout === "dual6" ? " (Array 1)" : "" })),
      ...oob2.map((f) => ({ ...f, arr: " (Array 2)" })),
    ];
    if (!fails.length) return;
    const parts = fails.map((f) => {
      const side = f.reason === "low" ? "&lt; 0.05" : "&gt; 0.45";
      return `pair ${f.label}${f.arr} &Delta;x/L = ${f.ratio.toFixed(3)} (${side})`;
    });
    ratioRows.push(`<i>${rec.name}</i>: ${parts.join("; ")}`);
  });
  if (ratioRows.length) {
    const Lref = mode === "Tm" ? "L<sub>m</sub>" : "L<sub>p</sub>";
    msgs.push("&#9888; Gauge spacing outside 0.05 &le; &Delta;x/" + Lref + " &le; 0.45 at the "
      + (mode === "Tm" ? "zero-crossing mean" : "spectral peak") + " frequency:"
      + "<br>&nbsp;&nbsp;&nbsp;"
      + ratioRows.join("<br>&nbsp;&nbsp;&nbsp;"));
  }

  if (anyRetained)
    msgs.push("&#9888; Some rows retained less than 80% of spectral energy " +
      "within the valid frequency band; interpret those with caution.");
  if (msgs.length) { warn.hidden = false; warn.innerHTML = msgs.join("<br>"); }
  else warn.hidden = true;

  body.querySelectorAll("input[data-field]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const rec = state.records.find((x) => x.id === +inp.dataset.id);
      if (!rec) return;
      const val = parseFloat(inp.value);
      rec[inp.dataset.field] = Number.isNaN(val) ? null : val;
      if (inp.dataset.field === "freq") rec.freqManual = true;
      analyzeRecord(rec, false);
      renderTable();
    });
  });
  body.querySelectorAll("[data-del]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.records = state.records.filter((x) => x.id !== +btn.dataset.del);
      renderTable();
    });
  });

  refreshVizFiles();
}

/* ===========================================================================
 * VISUALIZATION — time-series and energy-spectrum plots (canvas)
 * ========================================================================= */
const VIZ_COLORS = ["#1f5fa6", "#c0392b", "#1f7a4d", "#b9591a", "#6a4ca8", "#0e8a8a"];
const VIZ_SPEC = { inc: "#1f5fa6", ref: "#c0392b", tra: "#1f7a4d" };

let vizView = null;   // visible x-window {x0,x1}; null = full range
let vizYView = null;  // visible y-window {y0,y1}; null = autoscale
let vizMode = "none"; // active drag tool: "none" | "box" | "pan"
let vizDrag = null;   // in-progress drag state
let vizGeom = null;   // geometry of the last draw, for pixel<->data inversion
let vizSpecCache = null; // { key, a1, a2 } — cached three-probe spectral analysis
let vizPowCache = null;  // { key, spectra } — cached per-probe power spectra
let vizPlot = null;      // current plot object (series), for snap lookups
let vizHoverPt = null;   // snapped point under the cursor {px,py,color}
let vizPins = [];        // clicked/pinned points [{type,x,y,color,label}]

const vizType = () => ($("vizType") ? $("vizType").value : "series");

/* NaN-aware centred moving average over `win` samples (spectral smoothing). */
function movAvg(y, win) {
  win = Math.max(1, Math.floor(win));
  if (win <= 1) return y;
  const n = y.length;
  const out = new Float64Array(n);
  const half = win >> 1;
  for (let i = 0; i < n; i++) {
    let s = 0, c = 0;
    for (let k = -half; k <= half; k++) {
      const j = i + k;
      if (j < 0 || j >= n) continue;
      const v = y[j];
      if (Number.isNaN(v)) continue;
      s += v; c++;
    }
    out[i] = c ? s / c : NaN;
  }
  return out;
}

/* Compact number format for the hover readout. */
function fmtRead(v) {
  const a = Math.abs(v);
  if (a === 0) return "0";
  if (a >= 1e4 || a < 1e-3) return v.toExponential(2);
  if (a >= 100) return v.toFixed(1);
  if (a >= 1) return v.toFixed(2);
  return v.toFixed(3);
}

/* Current spectral-smoothing window (samples). */
const vizSmoothWin = () =>
  ($("vizSmooth") ? parseInt($("vizSmooth").value, 10) || 1 : 1);

/* Nearest index in an ascending numeric array (binary search). */
function nearestIndex(xs, xv) {
  let lo = 0, hi = xs.length - 1;
  if (hi <= 0 || xv <= xs[0]) return 0;
  if (xv >= xs[hi]) return hi;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < xv) lo = mid; else hi = mid;
  }
  return xv - xs[lo] <= xs[hi] - xv ? lo : hi;
}

/* Find the data point nearest a pixel position, across the visible series. */
function vizSnap(px, py) {
  if (!vizGeom || !vizPlot) return null;
  const g = vizGeom;
  const xOf = (x) => g.mL + ((x - g.vx0) / (g.vx1 - g.vx0)) * g.pW;
  const yOf = (v) => g.mT + g.pH - ((v - g.vy0) / (g.vy1 - g.vy0)) * g.pH;
  const cursorX = g.vx0 + ((px - g.mL) / g.pW) * (g.vx1 - g.vx0);
  let best = null, bestD = Infinity;
  for (const ser of vizPlot.series) {
    const c = nearestIndex(ser.x, cursorX);
    for (let i = Math.max(0, c - 3); i <= Math.min(ser.y.length - 1, c + 3); i++) {
      const yv = ser.y[i];
      if (Number.isNaN(yv)) continue;
      const sx = xOf(ser.x[i]), sy = yOf(yv);
      const d = (sx - px) ** 2 + (sy - py) ** 2;
      if (d < bestD) {
        bestD = d;
        best = { x: ser.x[i], y: yv, px: sx, py: sy,
                 color: ser.color, label: ser.label };
      }
    }
  }
  return best;
}

/* Repopulate the file selector from the current records (selection kept). */
function refreshVizFiles() {
  const sel = $("vizFile");
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = "";
  state.records.forEach((rec) => {
    if (!rec.cols) return;
    const o = document.createElement("option");
    o.value = String(rec.id);
    o.textContent = rec.name;
    sel.appendChild(o);
  });
  if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  if ($("vizBox") && $("vizBox").open) drawViz();
}

/* Adaptive numeric format for an axis, given the range it spans. */
function fmtAxis(range) {
  const a = Math.abs(range);
  if (a >= 200) return (v) => v.toFixed(0);
  if (a >= 20) return (v) => v.toFixed(1);
  if (a >= 2) return (v) => v.toFixed(2);
  if (a >= 0.2) return (v) => v.toFixed(3);
  if (a >= 0.002) return (v) => v.toFixed(5);
  return (v) => v.toExponential(1);
}

/* Build a time-series plot object for the time-series mode. */
function buildSeriesPlot(rec) {
  const probes = [...document.querySelectorAll(".viz-probe")]
    .filter((c) => c.checked)
    .map((c) => +c.value);
  if (!probes.length) return { empty: "Select at least one probe to plot." };

  const fs = parseFloat($("fs").value) || 100;
  const N = rec.cols[0].length;
  const dt = 1 / fs;
  const x = new Float64Array(N);
  for (let i = 0; i < N; i++) x[i] = i * dt;

  const series = probes.map((p) => ({
    label: "Probe " + (p + 1),
    color: VIZ_COLORS[p % VIZ_COLORS.length],
    x,
    y: rec.cols[p],
  }));
  // explicit display unit (m / cm / mm) — no automatic ×10^k scaling
  const unit = $("vizUnit") ? $("vizUnit").value : "cm";
  const yMul = unit === "mm" ? 1000 : unit === "cm" ? 100 : 1;
  return {
    xLabel: "Time (s)",
    yLabel: "Surface elevation",
    yUnit: unit,
    yMul,
    yFixed: true,
    xMin: 0,
    xMax: (N - 1) * dt,
    series,
    info: `${rec.name} — ${N} samples, ${((N - 1) * dt).toFixed(1)} s at ${fs} Hz`,
  };
}

/* Build an energy-spectrum plot object: incident/reflected from probes
 * 1-3, transmitted from probes 4-6, via the WaveLabX spectral method. */
function buildSpectrumPlot(rec) {
  const SP = typeof WaveLabXSpectral !== "undefined" ? WaveLabXSpectral
    : typeof window !== "undefined" ? window.WaveLabXSpectral : null;
  if (!SP) return { empty: "Spectral module not loaded." };
  if (!(rec.depth > 0)) return { empty: "Set a water depth for this file first." };

  const fs = parseFloat($("fs").value) || 100;
  const s = getSettings();
  const key = [rec.id, fs, rec.depth, s.pos1.join(","), s.pos2.join(",")].join("|");
  if (!vizSpecCache || vizSpecCache.key !== key) {
    vizSpecCache = {
      key,
      a1: SP.threeProbeArray(rec.cols.slice(0, 3), fs, rec.depth, s.pos1),
      a2: SP.threeProbeArray(rec.cols.slice(3, 6), fs, rec.depth, s.pos2),
    };
  }
  const { a1, a2 } = vizSpecCache;

  const want = [...document.querySelectorAll(".viz-curve")]
    .filter((c) => c.checked)
    .map((c) => c.value);
  if (!want.length) return { empty: "Select at least one spectrum to plot." };

  const win = vizSmoothWin();
  const series = [];
  if (want.includes("inc"))
    series.push({ label: "Incident", color: VIZ_SPEC.inc,
      x: a1.spectra.f, y: movAvg(a1.spectra.Si, win) });
  if (want.includes("ref"))
    series.push({ label: "Reflected", color: VIZ_SPEC.ref,
      x: a1.spectra.f, y: movAvg(a1.spectra.Sr, win) });
  if (want.includes("tra"))
    series.push({ label: "Transmitted", color: VIZ_SPEC.tra,
      x: a2.spectra.f, y: movAvg(a2.spectra.Si, win) });

  let xMin = Infinity, xMax = -Infinity;
  for (const ser of series)
    for (const xv of ser.x) { if (xv < xMin) xMin = xv; if (xv > xMax) xMax = xv; }
  if (!isFinite(xMin)) return { empty: "No spectral data in the valid frequency band." };

  return {
    xLabel: "Frequency (Hz)",
    yLabel: "Spectral density S(f)",
    yUnit: "m²·s",
    xMin, xMax, series,
    info: `${rec.name} — incident/reflected from probes 1–3, ` +
      `transmitted from probes 4–6`,
  };
}

/* Build a power-spectrum plot: the auto-spectrum (power spectral
 * density) of each selected wave probe. */
function buildPowerPlot(rec) {
  const SP = typeof WaveLabXSpectral !== "undefined" ? WaveLabXSpectral
    : typeof window !== "undefined" ? window.WaveLabXSpectral : null;
  if (!SP) return { empty: "Spectral module not loaded." };

  const probes = [...document.querySelectorAll(".viz-probe")]
    .filter((c) => c.checked)
    .map((c) => +c.value);
  if (!probes.length) return { empty: "Select at least one probe to plot." };

  const fs = parseFloat($("fs").value) || 100;
  const key = `${rec.id}|${fs}`;
  if (!vizPowCache || vizPowCache.key !== key) {
    vizPowCache = { key, spectra: rec.cols.map((c) => SP.autoSpectrum(c, fs)) };
  }
  const spectra = vizPowCache.spectra;

  // peak frequency across the selected probes — used to frame the
  // energetic band so the default view is not mostly flat noise
  let fPeak = 0;
  for (const p of probes) {
    const sp = spectra[p];
    let pk = -1, pkF = 0;
    for (let i = 0; i < sp.S.length; i++)
      if (sp.S[i] > pk) { pk = sp.S[i]; pkF = sp.f[i]; }
    if (pkF > fPeak) fPeak = pkF;
  }
  const fCap = Math.min(fs / 2, Math.max(2, fPeak * 8));

  const win = vizSmoothWin();
  const series = probes.map((p) => {
    const sp = spectra[p];
    let hi = sp.f.length - 1;
    while (hi > 0 && sp.f[hi] > fCap) hi--;
    return {
      label: "Probe " + (p + 1),
      color: VIZ_COLORS[p % VIZ_COLORS.length],
      x: sp.f.subarray(0, hi + 1),
      y: movAvg(sp.S.subarray(0, hi + 1), win),
    };
  });
  return {
    xLabel: "Frequency (Hz)",
    yLabel: "Spectral density S(f)",
    yUnit: "m²·s",
    xMin: 0, xMax: fCap, series,
    info: `${rec.name} — power spectral density per probe`,
  };
}

/* Draw the active plot (time series, energy spectrum, or power spectrum). */
function drawViz() {
  const canvas = $("vizCanvas");
  if (!canvas) return;
  const hint = $("vizHint");
  const rec = state.records.find((r) => String(r.id) === $("vizFile").value);

  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth || 1000;
  const cssH = 380;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  if (!rec || !rec.cols) {
    vizGeom = null; vizPlot = null;
    hint.textContent = "No file selected — load CSV files first.";
    drawOverlay();
    return;
  }
  let plot;
  try {
    const t = vizType();
    plot = t === "spectrum" ? buildSpectrumPlot(rec)
      : t === "power" ? buildPowerPlot(rec)
        : buildSeriesPlot(rec);
  } catch (e) {
    vizGeom = null; vizPlot = null;
    hint.textContent = "Plot failed: " + e.message;
    drawOverlay();
    return;
  }
  if (!plot || plot.empty || !plot.series || !plot.series.length) {
    vizGeom = null; vizPlot = null;
    hint.textContent = plot && plot.empty ? plot.empty : "Nothing to plot.";
    drawOverlay();
    return;
  }
  vizPlot = plot;
  renderPlot(ctx, cssW, cssH, plot);
  drawOverlay();
}

/* Shared renderer: axes, gridlines, line+dot series, legend, zoom window. */
function renderPlot(ctx, cssW, cssH, plot) {
  const mL = 62, mR = 14, mT = 26, mB = 34;
  const pW = cssW - mL - mR, pH = cssH - mT - mB;

  // visible x-window
  let x0 = plot.xMin, x1 = plot.xMax;
  if (x1 <= x0) x1 = x0 + 1;
  const xFull = x1 - x0;
  if (vizView) {
    x0 = Math.max(plot.xMin, Math.min(vizView.x0, plot.xMax));
    x1 = Math.min(plot.xMax, Math.max(vizView.x1, x0 + xFull * 1e-4));
  }

  // visible y-window: explicit if box-zoomed, else autoscale within x-window
  let yMin, yMax;
  if (vizYView) {
    yMin = vizYView.y0; yMax = vizYView.y1;
  } else {
    yMin = Infinity; yMax = -Infinity;
    for (const ser of plot.series) {
      const n = ser.y.length;
      for (let i = 0; i < n; i++) {
        const xv = ser.x[i];
        if (xv < x0 || xv > x1) continue;
        const yv = ser.y[i];
        if (Number.isNaN(yv)) continue;
        if (yv < yMin) yMin = yv;
        if (yv > yMax) yMax = yv;
      }
    }
    if (!isFinite(yMin)) { yMin = 0; yMax = 1; }
    if (yMin === yMax) { yMin -= 1; yMax += 1; }
    const pad = (yMax - yMin) * 0.06;
    yMin -= pad; yMax += pad;
  }

  const xOf = (t) => mL + ((t - x0) / (x1 - x0)) * pW;
  const yOf = (v) => mT + pH - ((v - yMin) / (yMax - yMin)) * pH;
  const xFmt = fmtAxis(x1 - x0);
  // y-axis display multiplier:
  //  - fixed-unit plots (time series) use an explicit m/cm/mm factor
  //  - other plots auto-factor into a "×10^k" label multiplier
  let yScaleExp = 0, yScale;
  if (plot.yFixed) {
    yScale = plot.yMul || 1;
  } else {
    const yMaxAbs = Math.max(Math.abs(yMin), Math.abs(yMax));
    if (yMaxAbs > 0) yScaleExp = -Math.floor(Math.log10(yMaxAbs));
    yScale = Math.pow(10, yScaleExp);
  }
  const yFmt = fmtAxis((yMax - yMin) * yScale);

  // grid + ticks
  ctx.strokeStyle = "#e2e7ee";
  ctx.lineWidth = 1;
  ctx.font = "11px -apple-system, BlinkMacSystemFont, sans-serif";
  ctx.fillStyle = "#6b7787";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 5; i++) {
    const v = yMin + (i / 5) * (yMax - yMin);
    const y = yOf(v);
    ctx.beginPath(); ctx.moveTo(mL, y); ctx.lineTo(mL + pW, y); ctx.stroke();
    ctx.fillText(yFmt(v * yScale), mL - 6, y);
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let i = 0; i <= 6; i++) {
    const t = x0 + (i / 6) * (x1 - x0);
    const x = xOf(t);
    ctx.beginPath(); ctx.moveTo(x, mT); ctx.lineTo(x, mT + pH); ctx.stroke();
    ctx.fillText(xFmt(t), x, mT + pH + 6);
  }

  // axis titles
  ctx.fillStyle = "#1a2433";
  ctx.fillText(plot.xLabel, mL + pW / 2, cssH - 13);

  // rotated y-axis title, with a "×10^k" factor (k as a superscript)
  const baseFont = "11px -apple-system, BlinkMacSystemFont, sans-serif";
  const supFont = "8px -apple-system, BlinkMacSystemFont, sans-serif";
  const segs = [{ t: plot.yLabel, sup: false }];
  if (yScaleExp !== 0) {
    // axis reads value × 10^labelExp, so labelExp = -yScaleExp
    const labelExp = -yScaleExp;
    segs.push({ t: "  ×10", sup: false });
    segs.push({ t: (labelExp < 0 ? "−" : "") + Math.abs(labelExp), sup: true });
  }
  segs.push({ t: " (" + (plot.yUnit || "") + ")", sup: false });
  ctx.save();
  ctx.translate(13, mT + pH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  let segTotal = 0;
  for (const sg of segs) {
    ctx.font = sg.sup ? supFont : baseFont;
    segTotal += ctx.measureText(sg.t).width;
  }
  let segX = -segTotal / 2;
  for (const sg of segs) {
    ctx.font = sg.sup ? supFont : baseFont;
    ctx.fillText(sg.t, segX, sg.sup ? -4 : 0);
    segX += ctx.measureText(sg.t).width;
  }
  ctx.font = baseFont;
  ctx.restore();

  // series — line + dot at each plotted point, clipped to the plot area
  ctx.save();
  ctx.beginPath();
  ctx.rect(mL, mT, pW, pH);
  ctx.clip();
  for (const ser of plot.series) {
    const n = ser.y.length;
    let lo = 0, hi = n - 1;            // visible index range (x ascending)
    while (lo < n && ser.x[lo] < x0) lo++;
    while (hi >= 0 && ser.x[hi] > x1) hi--;
    lo = Math.max(0, lo - 1);
    hi = Math.min(n - 1, hi + 1);
    if (hi < lo) continue;
    const nVis = hi - lo + 1;
    const stride = Math.max(1, Math.floor(nVis / Math.max(800, pW)));
    const dotR = nVis / stride < pW / 6 ? 2.6 : 1.7;

    ctx.strokeStyle = ser.color;
    ctx.lineWidth = 0.9;
    ctx.beginPath();
    let first = true;
    for (let i = lo; i <= hi; i += stride) {
      const yv = ser.y[i];
      if (Number.isNaN(yv)) { first = true; continue; }
      const x = xOf(ser.x[i]), y = yOf(yv);
      if (first) { ctx.moveTo(x, y); first = false; }
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.fillStyle = ser.color;
    for (let i = lo; i <= hi; i += stride) {
      const yv = ser.y[i];
      if (Number.isNaN(yv)) continue;
      ctx.beginPath();
      ctx.arc(xOf(ser.x[i]), yOf(yv), dotR, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
  ctx.restore();

  // legend along the top
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  let lx = mL;
  for (const ser of plot.series) {
    ctx.fillStyle = ser.color;
    ctx.fillRect(lx, mT - 15, 14, 3);
    ctx.fillStyle = "#1a2433";
    ctx.fillText(ser.label, lx + 18, mT - 14);
    lx += ctx.measureText(ser.label).width + 32;
  }

  // geometry for the drag tools + hover readout
  const xm = /^(.*?)\s*\(([^)]*)\)\s*$/.exec(plot.xLabel) || [];
  vizGeom = { mL, mT, pW, pH, vx0: x0, vx1: x1, vy0: yMin, vy1: yMax,
              xMin: plot.xMin, xMax: plot.xMax,
              ro: { xName: xm[1] || plot.xLabel, xUnit: xm[2] || "",
                    yName: plot.yLabel, yUnit: plot.yUnit || "",
                    yMul: plot.yFixed ? (plot.yMul || 1) : 1 } };

  // rubber-band rectangle while box-zooming
  if (vizDrag && vizDrag.mode === "box") {
    const rx = Math.min(vizDrag.x0, vizDrag.x1);
    const ry = Math.min(vizDrag.y0, vizDrag.y1);
    const rw = Math.abs(vizDrag.x1 - vizDrag.x0);
    const rh = Math.abs(vizDrag.y1 - vizDrag.y0);
    ctx.fillStyle = "rgba(31,95,166,0.12)";
    ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeStyle = "rgba(31,95,166,0.85)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(rx, ry, rw, rh);
    ctx.setLineDash([]);
  }

  $("vizHint").textContent =
    plot.info + (vizView || vizYView ? "  ·  zoomed (Reset to clear)" : "");
}

/* ---- drag tools: box-zoom and pan -------------------------------------- */

/* Toggle a drag tool; clicking the active tool turns it off. */
function vizSetMode(mode) {
  vizMode = vizMode === mode ? "none" : mode;
  $("vizBoxZoom").classList.toggle("active", vizMode === "box");
  $("vizPan").classList.toggle("active", vizMode === "pan");
  const cv = $("vizCanvas");
  cv.classList.toggle("mode-box", vizMode === "box");
  cv.classList.toggle("mode-pan", vizMode === "pan");
}

function vizPointer(ev) {
  const r = $("vizCanvas").getBoundingClientRect();
  return { x: ev.clientX - r.left, y: ev.clientY - r.top };
}

/* Hover readout — snap to the nearest data point and show its values. */
function vizHover(ev) {
  const tip = $("vizTip");
  if (!tip) return;
  const clear = () => {
    tip.style.display = "none";
    if (vizHoverPt) { vizHoverPt = null; drawOverlay(); }
  };
  if (!vizGeom || !vizPlot || vizDrag) { clear(); return; }
  const g = vizGeom;
  const p = vizPointer(ev);
  if (p.x < g.mL || p.x > g.mL + g.pW || p.y < g.mT || p.y > g.mT + g.pH) {
    clear();
    return;
  }
  const snap = vizSnap(p.x, p.y);
  if (!snap) { clear(); return; }
  vizHoverPt = { px: snap.px, py: snap.py, color: snap.color };
  const dy = snap.y * g.ro.yMul;
  tip.innerHTML =
    `<b>${snap.label}</b>&nbsp; ` +
    `${g.ro.xName} ${fmtRead(snap.x)} ${g.ro.xUnit}` +
    ` &nbsp;·&nbsp; ${g.ro.yName} ${fmtRead(dy)} ${g.ro.yUnit}`;
  tip.style.display = "block";
  let tx = snap.px + 14, ty = snap.py + 14;
  if (tx + tip.offsetWidth > g.mL + g.pW) tx = snap.px - tip.offsetWidth - 14;
  if (ty + tip.offsetHeight > g.mT + g.pH) ty = snap.py - tip.offsetHeight - 14;
  tip.style.left = Math.max(0, tx) + "px";
  tip.style.top = Math.max(0, ty) + "px";
  drawOverlay();
}

/* Draw a hover ring (pinned=false) or a pin dot (pinned=true). */
function vizMarker(ctx, x, y, color, pinned) {
  ctx.beginPath();
  ctx.arc(x, y, pinned ? 4 : 5, 0, 2 * Math.PI);
  if (pinned) {
    ctx.fillStyle = color; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#fff"; ctx.stroke();
  } else {
    ctx.fillStyle = "rgba(255,255,255,0.55)"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = color; ctx.stroke();
  }
}

/* Redraw the marker overlay: pinned points + the current hover point. */
function drawOverlay() {
  const ov = $("vizOverlay");
  const main = $("vizCanvas");
  if (!ov || !main) return;
  const dpr = window.devicePixelRatio || 1;
  const cssW = main.clientWidth || 1000, cssH = 380;
  ov.width = Math.round(cssW * dpr);
  ov.height = Math.round(cssH * dpr);
  const ctx = ov.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  if (!vizGeom) return;
  const g = vizGeom;
  const xOf = (x) => g.mL + ((x - g.vx0) / (g.vx1 - g.vx0)) * g.pW;
  const yOf = (v) => g.mT + g.pH - ((v - g.vy0) / (g.vy1 - g.vy0)) * g.pH;

  ctx.save();
  ctx.beginPath();
  ctx.rect(g.mL, g.mT, g.pW, g.pH);
  ctx.clip();
  ctx.font = "10px -apple-system, BlinkMacSystemFont, sans-serif";

  for (const pin of vizPins) {
    if (pin.type !== vizType()) continue;
    const px = xOf(pin.x), py = yOf(pin.y);
    if (px < g.mL - 6 || px > g.mL + g.pW + 6) continue;
    vizMarker(ctx, px, py, pin.color, true);
    const txt = `${fmtRead(pin.x)} ${g.ro.xUnit}, ` +
      `${fmtRead(pin.y * g.ro.yMul)} ${g.ro.yUnit}`;
    const tw = ctx.measureText(txt).width;
    let lx = px + 8, ly = py - 8;
    if (lx + tw + 6 > g.mL + g.pW) lx = px - tw - 14;
    if (ly - 11 < g.mT) ly = py + 20;
    ctx.fillStyle = "rgba(255,255,255,0.92)";
    ctx.fillRect(lx - 3, ly - 11, tw + 6, 14);
    ctx.fillStyle = pin.color;
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ctx.fillText(txt, lx, ly - 4);
  }
  if (vizHoverPt) vizMarker(ctx, vizHoverPt.px, vizHoverPt.py, vizHoverPt.color, false);
  ctx.restore();
}

/* Click a point to pin / unpin its readout. */
function vizClick(ev) {
  if (vizMode !== "none" || !vizGeom || !vizPlot) return;
  const p = vizPointer(ev);
  const g = vizGeom;
  if (p.x < g.mL || p.x > g.mL + g.pW || p.y < g.mT || p.y > g.mT + g.pH) return;
  const snap = vizSnap(p.x, p.y);
  if (!snap) return;
  const ty = vizType();
  const at = vizPins.findIndex(
    (pn) => pn.type === ty && pn.x === snap.x && pn.y === snap.y);
  if (at >= 0) vizPins.splice(at, 1);
  else vizPins.push({ type: ty, x: snap.x, y: snap.y,
                      color: snap.color, label: snap.label });
  drawOverlay();
}

function vizOnDown(ev) {
  if (vizMode === "none" || !vizGeom) return;
  const p = vizPointer(ev);
  vizDrag = {
    mode: vizMode,
    x0: p.x, y0: p.y, x1: p.x, y1: p.y,
    g: { ...vizGeom },
    yStart: vizYView ? { ...vizYView } : null,
  };
  ev.preventDefault();
  window.addEventListener("mousemove", vizOnMove);
  window.addEventListener("mouseup", vizOnUp);
}

function vizOnMove(ev) {
  if (!vizDrag) return;
  const p = vizPointer(ev);
  vizDrag.x1 = p.x;
  vizDrag.y1 = p.y;
  if (vizDrag.mode === "pan") {
    const g = vizDrag.g;
    const span = g.vx1 - g.vx0;
    const full = g.xMax - g.xMin;
    let a = g.vx0 - ((p.x - vizDrag.x0) / g.pW) * span;
    let b = a + span;
    if (a < g.xMin) { b += g.xMin - a; a = g.xMin; }
    if (b > g.xMax) { a -= b - g.xMax; b = g.xMax; }
    a = Math.max(g.xMin, a);
    vizView = b - a >= full - 1e-9 ? null : { x0: a, x1: b };
    if (vizDrag.yStart) {
      const shift = ((p.y - vizDrag.y0) / g.pH) * (g.vy1 - g.vy0);
      vizYView = { y0: vizDrag.yStart.y0 + shift, y1: vizDrag.yStart.y1 + shift };
    }
  }
  drawViz();
}

function vizOnUp() {
  window.removeEventListener("mousemove", vizOnMove);
  window.removeEventListener("mouseup", vizOnUp);
  if (!vizDrag) return;
  if (vizDrag.mode === "box") {
    const g = vizDrag.g;
    const xa = Math.max(g.mL, Math.min(vizDrag.x0, vizDrag.x1));
    const xb = Math.min(g.mL + g.pW, Math.max(vizDrag.x0, vizDrag.x1));
    const ya = Math.max(g.mT, Math.min(vizDrag.y0, vizDrag.y1));
    const yb = Math.min(g.mT + g.pH, Math.max(vizDrag.y0, vizDrag.y1));
    if (xb - xa > 6 && yb - ya > 6) {       // ignore tiny accidental drags
      vizView = {
        x0: g.vx0 + ((xa - g.mL) / g.pW) * (g.vx1 - g.vx0),
        x1: g.vx0 + ((xb - g.mL) / g.pW) * (g.vx1 - g.vx0),
      };
      // screen y is inverted: the top edge (ya) maps to the larger value
      vizYView = {
        y0: g.vy0 + ((g.mT + g.pH - yb) / g.pH) * (g.vy1 - g.vy0),
        y1: g.vy0 + ((g.mT + g.pH - ya) / g.pH) * (g.vy1 - g.vy0),
      };
    }
  }
  vizDrag = null;
  drawViz();
}

/* Zoom the visualization x-axis by a factor about the window centre. */
function vizZoom(factor) {
  if (!vizGeom) return;
  const g = vizGeom;
  const full = g.xMax - g.xMin;
  let a = vizView ? vizView.x0 : g.xMin;
  let b = vizView ? vizView.x1 : g.xMax;
  const c = (a + b) / 2;
  let span = (b - a) * factor;
  span = Math.min(span, full);
  span = Math.max(span, full * 0.002);
  a = c - span / 2;
  b = c + span / 2;
  if (a < g.xMin) { b += g.xMin - a; a = g.xMin; }
  if (b > g.xMax) { a -= b - g.xMax; b = g.xMax; }
  a = Math.max(g.xMin, a);
  vizView = b - a >= full - 1e-9 ? null : { x0: a, x1: b };
  drawViz();
}

/* ---------------------------------------------------------------------------
 * File ingestion
 * ------------------------------------------------------------------------- */
function readFiles(fileList) {
  const files = [...fileList].filter((f) => /\.csv$/i.test(f.name));
  if (!files.length) return;
  const s = getSettings();
  let pending = files.length;

  files.forEach((file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const cols = parseCSV(e.target.result);
      const rec = {
        id: nextId++,
        name: file.name,
        depth: parseDepth(file.name) ?? s.depth,
        freq: null,
        freqManual: false,
        cols,
        result: null,
        error: null,
      };
      analyzeRecord(rec, true); // detect frequency on load
      state.records.push(rec);
      if (--pending === 0) {
        state.records.sort((a, b) => a.name.localeCompare(b.name));
        renderTable();
      }
    };
    reader.onerror = () => {
      state.records.push({
        id: nextId++, name: file.name, depth: null, freq: null,
        freqManual: false, cols: null, result: null, error: "Could not read file",
      });
      if (--pending === 0) renderTable();
    };
    reader.readAsText(file);
  });
}

/* ---------------------------------------------------------------------------
 * Export
 * ------------------------------------------------------------------------- */
function exportCSV() {
  const s = getSettings();
  const mode = s.periodMode;            // "Tp" or "Tm"
  const sub = mode === "Tm" ? "m" : "p";
  const fLabel = `Frequency f${sub} (Hz)`;
  const tLabel = `Period T${sub} (s)`;
  const lLabel = `Wavelength L${sub} (m)`;
  const head = [
    "File",
    "Water depth (m)",
    fLabel, tLabel, lLabel,
    "Hi - Array 1 (m)",
    "Hr - Array 1 (m)",
    "Kr - Array 1",
    "Method - Array 1",
    "Hi - Array 2 (m)",
    "Hr - Array 2 (m)",
    "Kr - Array 2",
    "Method - Array 2",
    "Kt (transmission)",
    "Two-probe fallback used",
    "Out-of-band pairs",
  ].map((h) => `"${h}"`);

  const rows = [head.join(",")];
  const prettyMethod = (m) =>
    m === "three_probe" ? "Three-probe"
    : m === "two_probe" ? "Two-probe"
    : "";
  const prettyOOB = (r) => {
    const oob1 = mode === "Tm" ? (r.outOfBand1_m || []) : (r.outOfBand1_p || []);
    const oob2 = mode === "Tm" ? (r.outOfBand2_m || []) : (r.outOfBand2_p || []);
    const all = [
      ...oob1.map((f) => ({ ...f, arr: r.layout === "dual6" ? " Array 1" : "" })),
      ...oob2.map((f) => ({ ...f, arr: " Array 2" })),
    ];
    if (!all.length) return "";
    return all.map((f) => {
      const side = f.reason === "low" ? "<0.05" : ">0.45";
      return `pair ${f.label}${f.arr} dx/L=${f.ratio.toFixed(3)} (${side})`;
    }).join("; ");
  };

  state.records.forEach((rec) => {
    const r = rec.result;
    if (!r) {
      // 16-column row: File, depth, f, T, L, Hi1, Hr1, Kr1, Method1,
      // Hi2, Hr2, Kr2, Method2, Kt, fallback, OOB (error goes here).
      // 3 columns already filled (name, depth, freq) + 12 empty between
      // T/L through fallback + 1 error message = 16 fields.
      const empties = Array(12).fill("");
      rows.push([
        `"${rec.name}"`, rec.depth ?? "", rec.freq ?? "",
        ...empties,
        `"${(rec.error || "error").replace(/"/g, "'")}"`,
      ].join(","));
      return;
    }
    const g = (x, p) => (x == null || Number.isNaN(x) ? "" : Number(x).toFixed(p));
    const oob = prettyOOB(r);
    const fOut = mode === "Tm" ? r.fm : r.fp;
    const TOut = mode === "Tm" ? r.Tm : r.Tp;
    const LOut = mode === "Tm" ? r.Lm : r.Lp;
    rows.push([
      `"${rec.name}"`,
      g(rec.depth, 4), g(fOut, 5), g(TOut, 4), g(LOut, 4),
      g(r.Hi1, 6), g(r.Hr1, 6), g(r.Kr1, 4),
      `"${prettyMethod(r.method1)}"`,
      g(r.Hi2, 6), g(r.Hr2, 6), g(r.Kr2, 4),
      `"${prettyMethod(r.method2)}"`,
      g(r.Kt, 4),
      r.fallback ? "yes" : "no",
      oob ? `"${oob}"` : "",
    ].join(","));
  });

  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "reflection_analysis_results.csv";
  a.click();
  URL.revokeObjectURL(url);
}

/* ---------------------------------------------------------------------------
 * Wiring
 * ------------------------------------------------------------------------- */
function init() {
  // Footer: last-update stamp (manual constant updated per release).
  const lu = $("lastUpdate");
  if (lu) lu.textContent = LAST_UPDATE;

  const dz = $("dropzone");
  const fileInput = $("fileInput");

  dz.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    readFiles(e.target.files);
    fileInput.value = "";
  });
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); })
  );
  dz.addEventListener("drop", (e) => {
    if (e.dataTransfer?.files) readFiles(e.dataTransfer.files);
  });

  $("recomputeBtn").addEventListener("click", () => analyzeAll(true));
  $("exportBtn").addEventListener("click", exportCSV);
  $("clearBtn").addEventListener("click", () => {
    state.records = [];
    renderTable();
  });
  $("applyDepth").addEventListener("click", () => {
    const d = parseFloat($("depth").value);
    if (!(d > 0)) return;
    state.records.forEach((r) => { r.depth = d; });
    analyzeAll(false);
  });

  // gauge layout / sampling changes -> recompute (no re-detect needed)
  document.querySelectorAll("#fs, #skipWaves, #numWaves, .sp1, .sp2").forEach((el) =>
    el.addEventListener("change", () => {
      if (state.records.length) analyzeAll(false);
    })
  );
  // detection-band changes -> recompute WITH re-detection
  document.querySelectorAll("#fmin, #fmax").forEach((el) =>
    el.addEventListener("change", () => {
      if (state.records.length) analyzeAll(true);
    })
  );
  // Period & wavelength toggle -> just re-render the table; both Tp and Tm
  // are precomputed during analyzeRecord(), no re-analysis needed.
  const pdEl = $("periodDisplay");
  if (pdEl) pdEl.addEventListener("change", () => {
    try { localStorage.setItem("wlx_periodMode", pdEl.value); } catch (_) { /* ignore */ }
    if (state.records.length) renderTable();
  });
  // Restore previous selection on load.
  try {
    const saved = localStorage.getItem("wlx_periodMode");
    if (saved === "Tm" || saved === "Tp") {
      const el = $("periodDisplay");
      if (el) el.value = saved;
    }
  } catch (_) { /* ignore */ }

  // visualization controls
  $("vizFile").addEventListener("change", () => {
    vizView = null; vizYView = null; vizPins = []; vizHoverPt = null;
    drawViz();
  });
  $("vizType").addEventListener("change", () => {
    vizView = null; vizYView = null; vizPins = []; vizHoverPt = null;
    applyVizType();
    drawViz();
  });
  $("vizUnit").addEventListener("change", drawViz);
  $("vizSmooth").addEventListener("input", () => {
    const w = vizSmoothWin();
    $("vizSmoothVal").textContent = w <= 1 ? "off" : w + " bins";
    drawViz();
  });
  $("vizCanvas").addEventListener("mousemove", vizHover);
  $("vizCanvas").addEventListener("click", vizClick);
  $("vizCanvas").addEventListener("mouseleave", () => {
    const tip = $("vizTip");
    if (tip) tip.style.display = "none";
    if (vizHoverPt) { vizHoverPt = null; drawOverlay(); }
  });
  $("vizZoomIn").addEventListener("click", () => vizZoom(0.6));
  $("vizZoomOut").addEventListener("click", () => vizZoom(1 / 0.6));
  $("vizBoxZoom").addEventListener("click", () => vizSetMode("box"));
  $("vizPan").addEventListener("click", () => vizSetMode("pan"));
  $("vizCanvas").addEventListener("mousedown", vizOnDown);
  $("vizReset").addEventListener("click", () => {
    vizView = null; vizYView = null; drawViz();
  });
  document.querySelectorAll(".viz-probe").forEach((cb) =>
    cb.addEventListener("change", () => {
      $("vizAll").checked =
        [...document.querySelectorAll(".viz-probe")].every((c) => c.checked);
      drawViz();
    })
  );
  $("vizAll").addEventListener("change", () => {
    const on = $("vizAll").checked;
    document.querySelectorAll(".viz-probe").forEach((c) => { c.checked = on; });
    drawViz();
  });
  document.querySelectorAll(".viz-curve").forEach((cb) =>
    cb.addEventListener("change", () => {
      $("vizCurveAll").checked =
        [...document.querySelectorAll(".viz-curve")].every((c) => c.checked);
      drawViz();
    })
  );
  $("vizCurveAll").addEventListener("change", () => {
    const on = $("vizCurveAll").checked;
    document.querySelectorAll(".viz-curve").forEach((c) => { c.checked = on; });
    drawViz();
  });
  $("vizBox").addEventListener("toggle", () => {
    if ($("vizBox").open) drawViz();
  });
  window.addEventListener("resize", () => {
    if ($("vizBox").open) drawViz();
  });

  applyVizType();
}

/* Show the probe checkboxes for the time-series plot, or the
 * spectrum-curve checkboxes for the energy-spectrum plot — never both.
 * (display is set inline because the .viz-probes class would otherwise
 * override the [hidden] attribute.) */
function applyVizType() {
  const t = vizType();
  const spec = t === "spectrum";
  if ($("vizProbes")) $("vizProbes").style.display = spec ? "none" : "flex";
  if ($("vizCurves")) $("vizCurves").style.display = spec ? "flex" : "none";
  // the m/cm/mm unit selector applies only to the time-series plot
  if ($("vizUnitWrap"))
    $("vizUnitWrap").style.display = t === "series" ? "inline-flex" : "none";
  // spectral smoothing applies only to the spectrum plots
  if ($("vizSmoothWrap"))
    $("vizSmoothWrap").style.display =
      t === "spectrum" || t === "power" ? "flex" : "none";
}

/* Wave-type mode toggle removed in v0.3.0 -- the application now uses a
 * single set of settings (f detection band, skip-N-waves window, editable
 * f column) for every record. The previous applyMode() helper, the
 * getMode() function and the radio-button event listener are all gone. */

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", init);
}

/* expose core functions for Node-based testing */
if (typeof module !== "undefined" && module.exports) {
  module.exports = { dispersion, wavelength, detectFrequency, parseCSV, parseDepth };
}
