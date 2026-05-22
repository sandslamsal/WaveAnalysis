/* ---------------------------------------------------------------------------
 * js_three_probe_runner.js
 *
 * Test helper. Reads a JSON file {eta, fs, h, pos} describing a three-gauge
 * record, runs the browser implementation of the three-probe array method
 * (web/spectral.js), and prints {Hi, Hr, Kr, retained} as JSON on stdout.
 *
 * Used by tests/test_wavelabx.py to verify that the JavaScript browser port
 * agrees with the Python reference implementation.
 *
 *   node tests/js_three_probe_runner.js <input.json>
 * ------------------------------------------------------------------------- */
"use strict";

const fs = require("fs");
const path = require("path");
const { threeProbeArray } = require(
  path.join(__dirname, "..", "web", "spectral.js"));

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const eta = input.eta; // N x 3 array of probe elevations

const N = eta.length;
const cols = [[], [], []];
for (let i = 0; i < N; i++) {
  cols[0].push(eta[i][0]);
  cols[1].push(eta[i][1]);
  cols[2].push(eta[i][2]);
}

const r = threeProbeArray(cols, input.fs, input.h, input.pos);
process.stdout.write(JSON.stringify({
  Hi: r.Hi, Hr: r.Hr, Kr: r.Kr, retained: r.retained,
}));
