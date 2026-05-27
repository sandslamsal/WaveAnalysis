/* ---------------------------------------------------------------------------
 * js_period_runner.js
 *
 * Test helper. Reads {eta, fs, h, pos} for a three-gauge record, runs the
 * browser implementation of both zero_crossing (probe 1) and the three-probe
 * spectral routine, and prints { Tm, Tp, fm, fp } as JSON on stdout. Used by
 * tests/test_wavelabx.py to verify Python parity for the period statistics
 * displayed in the results table.
 *
 *   node tests/js_period_runner.js <input.json>
 * ------------------------------------------------------------------------- */
"use strict";

const fs = require("fs");
const path = require("path");
const { threeProbeArray, zeroCrossing } = require(
  path.join(__dirname, "..", "web", "spectral.js"));

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const eta = input.eta;
const N = eta.length;
const cols = [[], [], []];
for (let i = 0; i < N; i++) {
  cols[0].push(eta[i][0]);
  cols[1].push(eta[i][1]);
  cols[2].push(eta[i][2]);
}

const r = threeProbeArray(cols, input.fs, input.h, input.pos);
const zc = zeroCrossing(cols[0], input.fs);

process.stdout.write(JSON.stringify({
  Tm: zc.Tmean,
  Tp: r.Tp,
  fm: zc.Tmean > 0 ? 1 / zc.Tmean : null,
  fp: r.fp,
}));
