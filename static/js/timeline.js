/*
 * filters the big timeline table by words, part, region, and a range of years.
 * the filter settings are kept in the address bar (after the #) so a filtered
 * view can be bookmarked or shared, e.g. timeline.html#from=500 bce&to=1500
 */
(function () {
	var form = document.getElementById("filters");
	var table = document.getElementById("timeline");
	if (!form || !table || typeof history_dates === "undefined") { return; }

	// every box is optional. a <select id="f-x"> keeps the rows whose data-x matches it
	var box = {};
	var names = ["text", "era", "region", "kind", "from", "to"];
	var selects = [];
	for (var n = 0; n < names.length; n++) {
		var el = document.getElementById("f-" + names[n]);
		if (!el) { continue; }
		box[names[n]] = el;
		if (el.tagName.toLowerCase() === "select") { selects.push(names[n]); }
	}
	var count = document.getElementById("f-count");
	var rows = [];
	for (var i = 1; i < table.rows.length; i++) { rows.push(table.rows[i]); }

	form.className = form.className.replace(/\bhidden\b/, "");

	function read_hash() {
		var h = window.location.hash.replace(/^#/, "");
		if (h.indexOf("=") < 0) { return false; }
		var parts = h.split("&");
		for (var i = 0; i < parts.length; i++) {
			var kv = parts[i].split("=");
			var key = decodeURIComponent(kv[0]);
			if (box[key]) { box[key].value = decodeURIComponent(kv[1] || ""); }
		}
		return true;
	}

	function write_hash() {
		var out = [];
		for (var key in box) {
			if (box.hasOwnProperty(key) && box[key].value) {
				out.push(key + "=" + encodeURIComponent(box[key].value));
			}
		}
		var h = out.join("&");
		if (window.history && window.history.replaceState) {
			window.history.replaceState(null, "", h ? "#" + h : window.location.pathname);
		}
	}

	function mark_bad(input, bad) {
		input.style.backgroundColor = bad ? "#ffdddd" : "";
	}

	function apply() {
		var words = box.text ? box.text.value.toLowerCase().split(/\s+/) : [];
		var lo = box.from && box.from.value ? history_dates.parse(box.from.value) : null;
		var hi = box.to && box.to.value ? history_dates.parse(box.to.value) : null;
		if (box.from) { mark_bad(box.from, box.from.value && lo === null); }
		if (box.to) { mark_bad(box.to, box.to.value && hi === null); }
		var ranged = lo !== null || hi !== null;
		if (lo === null) { lo = -Infinity; }
		if (hi === null) { hi = Infinity; }

		var shown = 0;
		for (var i = 0; i < rows.length; i++) {
			var r = rows[i];
			var ok = true;
			for (var k = 0; k < selects.length; k++) {
				var want = box[selects[k]].value;
				if (want && r.getAttribute("data-" + selects[k]) !== want) { ok = false; }
			}
			if (ok && ranged) {
				// keep events that overlap the range at all; undated ones only when no range is set
				var start = parseFloat(r.getAttribute("data-start"));
				var end = parseFloat(r.getAttribute("data-end"));
				if (isNaN(start) || end < lo || start > hi) { ok = false; }
			}
			if (ok) {
				var text = r.textContent.toLowerCase();
				for (var w = 0; w < words.length; w++) {
					if (words[w] && text.indexOf(words[w]) < 0) { ok = false; break; }
				}
			}
			r.style.display = ok ? "" : "none";
			if (ok) { shown++; }
		}
		count.innerHTML = "showing " + shown + " of " + rows.length + " events";
		write_hash();
	}

	var timer = null;
	function soon() {
		clearTimeout(timer);
		timer = setTimeout(apply, 150);
	}

	for (var key in box) {
		if (box.hasOwnProperty(key)) {
			box[key].onkeyup = soon;
			box[key].onchange = apply;
		}
	}
	document.getElementById("f-reset").onclick = function () {
		for (var key in box) { if (box.hasOwnProperty(key)) { box[key].value = ""; } }
		apply();
	};

	// a link like timeline.html#event-12 highlights that one event
	var target = window.location.hash.match(/^#event-(\d+)$/);
	if (target) {
		var row = document.getElementById("event-" + target[1]);
		if (row) { row.className += " hit"; }
		count.innerHTML = "showing " + rows.length + " of " + rows.length + " events";
	} else {
		read_hash();
		apply();
	}
})();
