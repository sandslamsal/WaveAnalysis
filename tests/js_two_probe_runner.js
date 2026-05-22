/* ---------------------------------------------------------------------------
 * js_two_probe_runner.js
 *
 * Test helper. Reads a JSON file {eta, fs, h, pos} describing a two-gauge
 * record, runs the browser implementation of the two-probe Goda-Suzuki
 * method (web/spectral.js), and prints {Hi, Hr, Kr, retained} as JSON on
 * stdout.
 *
 * Used by tests/test_wavelabx.py to verify that the JavaScript browser port
 * of two_probe_goda agrees with the Python reference implementation.
 *
 *   node tests/js_two_probe_runner.js <input.json>
 * ------------------------------------------------------------------------- */
"use strict";

const fs = require("fs");
const path = require("path");
const { twoProbeGoda } = require(
  path.join(__dirname, "..", "web", "spectral.js"));

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const eta = input.eta; // N x 2 array of probe elevations

const N = eta.length;
const c1 = new Array(N), c2 = new Array(N);
for (let i = 0; i < N; i++) { c1[i] = eta[i][0]; c2[i] = eta[i][1]; }

const r = twoProbeGoda(c1, c2, input.fs, input.h, input.pos[0], input.pos[1]);
process.stdout.write(JSON.stringify({
  Hi: r.Hi, Hr: r.Hr, Kr: r.Kr, retained: r.retained,
}));
