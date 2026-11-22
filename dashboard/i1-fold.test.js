// node --test dashboard/i1-fold.test.js : the summary tidy step of ./i1-fold.js (ChipInFold.humanKeys)
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const el = () => ({ appendChild() {}, setAttribute() {}, style: {} });
const win = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "i1-fold.js"), "utf8"), {
  window: win, document: { createElement: el, head: el() }, console
});
const tidy = win.ChipInFold.humanKeys;

const CASES = [
  ["validation 0.912/0.897", "validation 91.2%/89.7%"],
  ["sensitivity 0.912", "sensitivity 91.2%"],
  ["specificity of 0.9", "specificity of 90%"],
  ["test 0.874", "test 87.4%"],
  ["accuracy: 0.95", "accuracy: 95%"],
  ["sensitivity/specificity validation 0.912/0.897 next to 95.2%", "sensitivity/specificity validation 91.2%/89.7% next to 95.2%"],
  ["Validation 0.9/0.85", "Validation 90%/85%"],
  ["pooled sensitivity 0.714.", "pooled sensitivity 71.4%."],
  ["validation sensitivity 100% and held\u2011out 0.714, but", "validation sensitivity 100% and held\u2011out 71.4%, but"],
  // must stay unchanged
  ["threshold 0.98", "threshold 0.98"],
  ["0.25 s hop", "0.25 s hop"],
  ["6.67 false alarms per hour", "6.67 false alarms per hour"],
  ["412 gates at $0.31", "412 gates at $0.31"],
  ["test 1 of 3 passed", "test 1 of 3 passed"],
  ["sensitivity 95.2%", "sensitivity 95.2%"],
  ["validation 0.5/h", "validation 0.5/h"]
];
for (const [inp, want] of CASES) test(JSON.stringify(inp), () => assert.strictEqual(tidy(inp), want));
