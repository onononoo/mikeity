/*
 * searches the index in search-index.js (made by the builder).
 *
 * each entry looks like { k: kind, t: title, d: date or label, x: text, u: url, y: year }.
 * every word typed must appear somewhere in an entry for it to match. matches
 * in the title count for more than matches in the text. if the search looks
 * like a year ("1066", "500 bce"), events close to that year are shown too.
 */
(function () {
	if (typeof search_index === "undefined") { return; }

	var input = document.getElementById("q");
	var results = document.getElementById("results");
	var kinds = ["part", "topic", "section", "event", "person", "term"];
	var names = { part: "parts", topic: "topics", section: "sections", event: "events", person: "people", term: "glossary" };
	var limit = 30;

	function esc(s) {
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	}

	function words_of(q) {
		var raw = q.toLowerCase().replace(/[^\w\s'À-ɏ-]/g, " ").split(/\s+/);
		var out = [];
		for (var i = 0; i < raw.length; i++) { if (raw[i]) { out.push(raw[i]); } }
		return out;
	}

	function highlight(text, words) {
		var s = esc(text);
		for (var i = 0; i < words.length; i++) {
			var w = words[i].replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
			if (w.length > 1) { s = s.replace(new RegExp("(" + w + ")", "gi"), "<b>$1</b>"); }
		}
		return s;
	}

	function snippet(text, words) {
		// show the part of a long text around the first match
		var lower = text.toLowerCase();
		var at = -1;
		for (var i = 0; i < words.length && at < 0; i++) { at = lower.indexOf(words[i]); }
		if (text.length <= 220) { return text; }
		var start = Math.max(0, at - 80);
		return (start > 0 ? "… " : "") + text.substr(start, 220) + " …";
	}

	function score(item, words) {
		var t = item.t.toLowerCase(), d = (item.d || "").toLowerCase(), x = (item.x || "").toLowerCase();
		var total = 0;
		for (var i = 0; i < words.length; i++) {
			var w = words[i], s = 0;
			if (t === w) { s += 20; }
			if (t.indexOf(w) === 0) { s += 6; }
			if (t.indexOf(w) >= 0) { s += 5; }
			if (d.indexOf(w) >= 0) { s += 3; }
			if (x.indexOf(w) >= 0) { s += 1; }
			if (s === 0) { return 0; }
			total += s;
		}
		// whole parts and people are usually what someone means
		if (item.k === "part" || item.k === "topic" || item.k === "person") { total += 2; }
		return total;
	}

	function near_year(y) {
		var hits = [];
		for (var i = 0; i < search_index.length; i++) {
			var it = search_index[i];
			if (it.k === "event" && typeof it.y === "number") {
				hits.push({ item: it, gap: Math.abs(it.y - y) });
			}
		}
		hits.sort(function (a, b) { return a.gap - b.gap; });
		return hits.slice(0, 10);
	}

	function render_item(it, words) {
		return "<li><a href=\"" + esc(it.u) + "\">" + highlight(it.t, words) + "</a>" +
			(it.d ? " <span class=\"small\">(" + esc(it.d) + ")</span>" : "") +
			(it.x && it.k !== "event" ? "<br><span class=\"small\">" + highlight(snippet(it.x, words), words) + "</span>" : "") +
			"</li>";
	}

	function run(q) {
		var words = words_of(q);
		if (!words.length) { results.innerHTML = ""; return; }

		var groups = {}, total = 0, i, k;
		for (i = 0; i < kinds.length; i++) { groups[kinds[i]] = []; }
		for (i = 0; i < search_index.length; i++) {
			var s = score(search_index[i], words);
			if (s > 0) { groups[search_index[i].k].push({ item: search_index[i], s: s }); total++; }
		}

		var html = ["<p>" + total + " result" + (total === 1 ? "" : "s") + " for <b>" + esc(q.toLowerCase()) + "</b>.</p>"];

		var year = typeof history_dates !== "undefined" ? history_dates.parse(q) : null;
		if (year !== null && /\d/.test(q)) {
			var near = near_year(year);
			html.push("<h2>events closest to " + esc(history_dates.format(year)) + "</h2><ul>");
			for (i = 0; i < near.length; i++) { html.push(render_item(near[i].item, [])); }
			html.push("</ul>");
		}

		for (i = 0; i < kinds.length; i++) {
			k = kinds[i];
			var list = groups[k];
			if (!list.length) { continue; }
			list.sort(function (a, b) { return b.s - a.s; });
			html.push("<h2>" + names[k] + " (" + list.length + ")</h2><ul>");
			for (var j = 0; j < list.length && j < limit; j++) { html.push(render_item(list[j].item, words)); }
			if (list.length > limit) { html.push("<li class=\"small\">and " + (list.length - limit) + " more…</li>"); }
			html.push("</ul>");
		}
		if (total === 0 && year === null) { html.push("<p>nothing found. try fewer or shorter words.</p>"); }
		results.innerHTML = html.join("\n");
	}

	function query_from_url() {
		var m = window.location.search.match(/[?&]q=([^&]*)/);
		return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
	}

	var q = query_from_url();
	input.value = q;
	run(q);

	var timer = null;
	input.onkeyup = function () {
		clearTimeout(timer);
		timer = setTimeout(function () { run(input.value); }, 200);
	};
	input.focus();
})();
