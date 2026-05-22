/* ---------------------------------------------------------------------------
 * js_reflection_runner.js
 *
 * Test helper for tests/test_wavelabx.py. Reads a JSON file describing a
 * three-gauge record, runs the browser implementation of the high-level
 * reflectionAnalysis() (web/spectral.js), and prints
 * {Hi, Hr, Kr, retained, method_used} as JSON on stdout.
 *
 *   node tests/js_reflection_runner.js <input.json>
 * ------------------------------------------------------------------------- */
"use strict";

const fs = require("fs");
const path = require("path");
const { reflectionAnalysis } = require(
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

const r = reflectionAnalysis(cols, input.fs, input.h, input.pos);
process.stdout.write(JSON.stringify({
  Hi: r.Hi, Hr: r.Hr, Kr: r.Kr,
  retained: r.retained,
  method_used: r.method_used,
}));
