/*
 * api.ts: turns site/data/history.json into a read-only json api made of
 * plain files, so it works on any static host (vercel, github pages, a usb
 * stick) with no server:
 *
 *   api/index.json                 what is here, with counts
 *   api/eras.json                  the eleven parts
 *   api/eras/<slug>.json           one part with its events and people
 *   api/events.json                every dated event
 *   api/centuries/<n>.json         events by century (-31 is the 31st century bce)
 *   api/people.json                everyone, without the long text
 *   api/people/<slug>.json         one person, with their part and region
 *   api/regions/<slug>.json        one region with its events and people
 *   api/glossary.json              every term
 *   api/religions.json             the six religions
 *   api/religions/<slug>.json      one religion: timeline, people, glossary
 *
 * run with node 22.6 or newer, which runs typescript by removing the types:
 *
 *   node tools/api.ts site/data/history.json site/api
 *
 * it prints one tab separated line per kind of endpoint (path, how many
 * files, what it holds, one real example) for the builder to put on the api page.
 */

import * as fs from "node:fs";
import * as path from "node:path";

// ------------------------------------------------------------------ the data

interface Era {
	slug: string;
	number: number;
	title: string;
	starts: string;
	ends: string;
	summary: string;
}

interface Event {
	id: number;
	date: string;
	start: number;
	end: number;
	text: string;
	era: string;
	region: string;
	tags: string[];
}

interface Person {
	slug: string;
	name: string;
	dates: string;
	born: number | null;
	died: number | null;
	known: boolean;
	role: string;
	about: string;
	era: string;
	region: string;
}

interface Term {
	slug: string;
	term: string;
	definition: string;
	see: string[];
	used_in: string[];
}

interface Region {
	slug: string;
	name: string;
	description: string;
}

interface Religion {
	slug: string;
	name: string;
	summary: string;
	events: { id: number; kind: "tradition" | "history"; when: string; text: string; start: number | null; end: number | null }[];
	people: { slug: string; name: string; dates: string; kind: string; role: string; about: string }[];
	glossary: { slug: string; term: string; definition: string }[];
	[more: string]: unknown;
}

interface History {
	eras: Era[];
	events: Event[];
	people: Person[];
	glossary: Term[];
	regions: Region[];
	religions: Religion[];
}

interface Endpoint {
	path: string;
	files: number;
	about: string;
	example: string;
}

// ------------------------------------------------------------------ helpers

class ApiWriter {
	readonly endpoints: Endpoint[] = [];
	private written = 0;
	private readonly out: string;

	// (node runs typescript by stripping types, so no "private out" shorthand here)
	constructor(out: string) {
		this.out = out;
	}

	/** write one json file under the api folder; returns its path relative to the site */
	file(rel: string, data: unknown): string {
		const full = path.join(this.out, rel);
		fs.mkdirSync(path.dirname(full), { recursive: true });
		fs.writeFileSync(full, JSON.stringify(data, null, 1) + "\n", "utf8");
		this.written++;
		return "api/" + rel;
	}

	/** write a set of files that share a pattern, and remember it for the index */
	many<T>(pattern: string, about: string, items: T[], name: (item: T) => string, body: (item: T) => unknown): void {
		for (const item of items) {
			this.file(pattern.replace("{}", name(item)), body(item));
		}
		const example = items.length ? "api/" + pattern.replace("{}", name(items[0])) : "";
		this.endpoints.push({ path: "api/" + pattern, files: items.length, about, example });
	}

	one(rel: string, about: string, data: unknown): void {
		this.file(rel, data);
		this.endpoints.push({ path: "api/" + rel, files: 1, about, example: "api/" + rel });
	}

	get count(): number {
		return this.written;
	}
}

function groupBy<T, K>(items: T[], key: (item: T) => K): Map<K, T[]> {
	const map = new Map<K, T[]>();
	for (const item of items) {
		const k = key(item);
		const list = map.get(k);
		if (list) {
			list.push(item);
		} else {
			map.set(k, [item]);
		}
	}
	return map;
}

/** -3100 -> -31 (the 31st century bce), 1492 -> 15, the same rule as the database */
function century(year: number): number {
	const y = Math.trunc(year);
	return y <= 0 ? -(Math.floor((-y - 1) / 100) + 1) : Math.floor((y - 1) / 100) + 1;
}

function check(history: History): void {
	const problems: string[] = [];
	const eras = new Set(history.eras.map((e) => e.slug));
	const regions = new Set(history.regions.map((r) => r.slug));
	for (const ev of history.events) {
		if (!eras.has(ev.era)) problems.push(`event ${ev.id}: unknown era ${ev.era}`);
		if (!regions.has(ev.region)) problems.push(`event ${ev.id}: unknown region ${ev.region}`);
	}
	for (const p of history.people) {
		if (!eras.has(p.era)) problems.push(`${p.name}: unknown era ${p.era}`);
	}
	if (problems.length) {
		throw new Error("history.json does not fit together:\n  " + problems.join("\n  "));
	}
}

// ------------------------------------------------------------------ building

function build(history: History, out: string): ApiWriter {
	check(history);
	fs.rmSync(out, { recursive: true, force: true });
	const api = new ApiWriter(out);

	const summary = (p: Person) => ({ slug: p.slug, name: p.name, dates: p.dates, role: p.role, url: `api/people/${p.slug}.json` });
	const eventsByEra = groupBy(history.events, (e) => e.era);
	const peopleByEra = groupBy(history.people, (p) => p.era);
	const eventsByRegion = groupBy(history.events, (e) => e.region);
	const peopleByRegion = groupBy(history.people, (p) => p.region);
	const eraBySlug = new Map(history.eras.map((e) => [e.slug, e] as const));
	const regionBySlug = new Map(history.regions.map((r) => [r.slug, r] as const));

	api.one("eras.json", "the eleven parts of the story, in order",
		history.eras.map((e) => ({ ...e, url: `api/eras/${e.slug}.json`, page: `${e.slug}.html` })));

	api.many("eras/{}.json", "one part, with its events and people", history.eras, (e) => e.slug, (e) => ({
		...e,
		page: `${e.slug}.html`,
		events: eventsByEra.get(e.slug) ?? [],
		people: (peopleByEra.get(e.slug) ?? []).map(summary),
	}));

	api.one("events.json", "every dated event on the main timeline", history.events);

	// centuries only mean something for the last twelve thousand years or so
	const dated = history.events.filter((e) => e.start >= -10000);
	const centuries = [...groupBy(dated, (e) => century(e.start)).entries()].sort((a, b) => a[0] - b[0]);
	api.many("centuries/{}.json", "the events that began in one century, from 10,000 bce (-5 is the 5th century bce)", centuries,
		([c]) => String(c), ([c, events]) => ({ century: c, events }));

	api.one("people.json", "everyone on the people page, in short", history.people.map(summary));

	api.many("people/{}.json", "one person, with their part and region", history.people, (p) => p.slug, (p) => ({
		...p,
		page: `people.html#${p.slug}`,
		part: eraBySlug.get(p.era)?.title ?? null,
		region_name: regionBySlug.get(p.region)?.name ?? null,
	}));

	api.many("regions/{}.json", "one region, with its events and people", history.regions, (r) => r.slug, (r) => ({
		...r,
		page: `regions.html#${r.slug}`,
		events: eventsByRegion.get(r.slug) ?? [],
		people: (peopleByRegion.get(r.slug) ?? []).map(summary),
	}));

	api.one("glossary.json", "every term in the glossary", history.glossary);

	api.one("religions.json", "the six religions, in short", history.religions.map((r) => ({
		slug: r.slug, name: r.name, summary: r.summary,
		counts: { events: r.events.length, people: r.people.length, terms: r.glossary.length },
		url: `api/religions/${r.slug}.json`, page: `${r.slug}/index.html`,
	})));

	api.many("religions/{}.json", "one religion: facts, timeline, people, and glossary", history.religions, (r) => r.slug, (r) => {
		const { story: _story, ...rest } = r;
		return { ...rest, page: `${r.slug}/index.html` };
	});

	// the index is written last so it can list everything else
	const index = {
		about: "a read-only json api for the history of the world. every url is a plain file.",
		files: api.count + 1,
		endpoints: api.endpoints,
	};
	api.one("index.json", "this list", index);
	return api;
}

// ------------------------------------------------------------------ main

function main(argv: string[]): number {
	if (argv.length !== 2) {
		console.error("usage: node tools/api.ts history.json output-folder");
		return 2;
	}
	const [input, out] = argv;
	let history: History;
	try {
		history = JSON.parse(fs.readFileSync(input, "utf8")) as History;
	} catch (e) {
		console.error(`api.ts: cannot read ${input}: ${(e as Error).message}`);
		return 1;
	}
	try {
		const api = build(history, out);
		for (const ep of api.endpoints) {
			process.stdout.write(`${ep.path}\t${ep.files}\t${ep.about}\t${ep.example}\n`);
		}
	} catch (e) {
		console.error(`api.ts: ${(e as Error).message}`);
		return 1;
	}
	return 0;
}

process.exitCode = main(process.argv.slice(2));
