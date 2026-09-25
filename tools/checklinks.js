#!/usr/bin/env node
/*
 * checks every link on the built site.
 *
 *   node tools/checklinks.js [site-folder]
 *
 * for every html page it collects the ids it defines and the links it makes
 * (href and src). a local link must point at a file that exists, and if it
 * has a #fragment, that id must exist on the target page. the urls inside the
 * search index (js/search-index.js) are checked the same way.
 *
 * exits with code 1 if anything is broken, so build scripts can stop.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const site = path.resolve(process.argv[2] || path.join(__dirname, "..", "site"));

if (!fs.existsSync(site)) {
	console.error(`no site folder at ${site}. build the site first.`);
	process.exit(2);
}

// ------------------------------------------------------------ reading pages

function walk(dir) {
	let out = [];
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		out = entry.isDirectory() ? out.concat(walk(full)) : out.concat(full);
	}
	return out;
}

function decode(s) {
	return s.replace(/&amp;/g, "&").replace(/&quot;/g, "\"").replace(/&#39;/g, "'")
		.replace(/&lt;/g, "<").replace(/&gt;/g, ">");
}

const files = walk(site);
const pages = files.filter((f) => f.endsWith(".html"));
const ids = new Map();     // page path -> set of ids
const links = [];          // { from, url, line }

for (const page of pages) {
	const html = fs.readFileSync(page, "utf8");
	const set = new Set();
	// anchors are any id, plus the old-style <a name="...">
	const anchors = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])
		.concat([...html.matchAll(/<a\s[^>]*?\bname="([^"]+)"/g)].map((m) => m[1]));
	for (const a of anchors) {
		if (set.has(a)) {
			links.push({ from: page, url: null, problem: `duplicate id "${a}"` });
		}
		set.add(a);
	}
	ids.set(page, set);

	const lines = html.split("\n");
	lines.forEach((text, i) => {
		for (const m of text.matchAll(/\s(?:href|src)="([^"]*)"/g)) {
			links.push({ from: page, url: decode(m[1]), line: i + 1 });
		}
	});
}

// the search index holds urls too
const indexFile = path.join(site, "js", "search-index.js");
let indexEntries = 0;
if (fs.existsSync(indexFile)) {
	const text = fs.readFileSync(indexFile, "utf8");
	const json = text.slice(text.indexOf("=") + 1, text.lastIndexOf(";"));
	const entries = JSON.parse(json);
	indexEntries = entries.length;
	const searchPage = path.join(site, "search.html");
	for (const e of entries) {
		links.push({ from: searchPage, url: e.u, line: `index: ${e.t.slice(0, 40)}` });
	}
}

// ------------------------------------------------------------ checking

const problems = [];
let checked = 0;
let external = 0;

for (const link of links) {
	const where = `${path.relative(site, link.from)}${link.line ? ":" + link.line : ""}`;
	if (link.problem) {
		problems.push(`${where}: ${link.problem}`);
		continue;
	}
	const url = link.url;
	if (/^(https?:|mailto:|javascript:|data:)/i.test(url)) {
		external++;
		continue;
	}
	checked++;

	const [beforeHash, frag] = url.split("#");
	const target = beforeHash.split("?")[0];
	const file = target === "" ? link.from : path.resolve(path.dirname(link.from), target);

	if (!file.startsWith(site)) {
		problems.push(`${where}: link leaves the site: ${url}`);
		continue;
	}
	if (!fs.existsSync(file)) {
		problems.push(`${where}: missing file: ${url}`);
		continue;
	}
	// fragments made of key=value pairs are timeline filter settings, not ids
	if (frag && !frag.includes("=") && file.endsWith(".html")) {
		const targetIds = ids.get(file);
		if (!targetIds || !targetIds.has(decodeURIComponent(frag))) {
			problems.push(`${where}: missing anchor #${frag} in ${path.relative(site, file)}`);
		}
	}
}

console.log(`checked ${checked} links on ${pages.length} pages (${indexEntries} from the search index), skipped ${external} external`);
if (problems.length) {
	console.log(`${problems.length} problem(s):`);
	for (const p of problems.slice(0, 100)) console.log(`  - ${p}`);
	process.exit(1);
}
console.log("all links ok");
