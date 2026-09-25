/*
 * tests for static/js/dates.js, the browser version of the date parser.
 * the answers must match builder/dates.py, so the timeline filter agrees
 * with the dates printed on the page.
 *
 *   node tests/test_dates.js
 */
"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "..", "static", "js", "dates.js"), "utf8");
const context = {};
vm.createContext(context);
vm.runInContext(source + "\nthis.history_dates = history_dates;", context);
const { parse, format } = context.history_dates;

const cases = [
	["1492", 1492],
	["-500", -500],
	["500 bce", -500],
	["500 bc", -500],
	["476 ce", 476],
	["476 ad", 476],
	["c. 3100 bce", -3100],
	["10,000 bce", -10000],
	["66 mya", 1950 - 66e6],
	["66 million years ago", 1950 - 66e6],
	["4.5 bya", 1950 - 4.5e9],
	["5th century bce", -500],
	["15th century", 1401],
	["1960s", 1960],
	["", null],
	["banana", null],
];

let passed = 0;
for (const [input, expected] of cases) {
	assert.strictEqual(parse(input), expected, `parse(${JSON.stringify(input)})`);
	passed++;
}

const formats = [
	[-3100, "3100 bce"],
	[79, "79 ce"],
	[1492, "1492"],
	[1950 - 66e6, "66 million years ago"],
	[1950 - 13.8e9, "13.8 billion years ago"],
];
for (const [input, expected] of formats) {
	assert.strictEqual(format(input), expected, `format(${input})`);
	passed++;
}

console.log(`dates.js: ${passed} checks passed`);
