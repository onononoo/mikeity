/*
 * reads years typed by a person, like "500 bce", "1492", "66 mya" or
 * "5th century bc", and turns them into numbers. years before the common
 * era become negative. this matches the python code in builder/dates.py.
 */
var history_dates = (function () {
	var present = 1950;
	var units = [
		["billion years ago", 1e9], ["bya", 1e9],
		["million years ago", 1e6], ["mya", 1e6],
		["thousand years ago", 1e3], ["kya", 1e3],
		["years ago", 1]
	];

	function clean(text) {
		return String(text).toLowerCase().replace(/,/g, "").replace(/\s+/g, " ")
			.replace(/^\s+|\s+$/g, "")
			.replace(/^(c\.|ca\.|circa|about|around|~)\s*/, "");
	}

	function parse(text) {
		var s = clean(text), m, i, n;
		if (s === "") { return null; }

		// a bare number, maybe negative
		if (/^-?\d+(\.\d+)?$/.test(s)) { return parseFloat(s); }

		// deep time: "66 million years ago", "4.5 bya"
		for (i = 0; i < units.length; i++) {
			m = s.match(new RegExp("^(\\d+(?:\\.\\d+)?)\\s*" + units[i][0] + "$"));
			if (m) { return present - parseFloat(m[1]) * units[i][1]; }
		}

		// centuries: "5th century bce" means the start of that century
		m = s.match(/^(\d+)(st|nd|rd|th) century( bce| bc| ce| ad)?$/);
		if (m) {
			n = parseInt(m[1], 10);
			return (m[3] && m[3].indexOf("b") === 1) ? -(n * 100) : (n - 1) * 100 + 1;
		}

		// decades: "1960s"
		m = s.match(/^(\d+0)s$/);
		if (m) { return parseInt(m[1], 10); }

		// years with an era: "500 bce", "476 ad"
		m = s.match(/^(\d+(?:\.\d+)?)\s*(bce|bc|b\.c\.|b\.c\.e\.|ce|ad|a\.d\.|c\.e\.)?$/);
		if (m) {
			n = parseFloat(m[1]);
			return (m[2] && m[2].charAt(0) === "b") ? -n : n;
		}
		return null;
	}

	function format(y) {
		var n;
		if (y < present - 100000) {
			n = present - y;
			if (n >= 1e9) { return +(n / 1e9).toFixed(2) + " billion years ago"; }
			if (n >= 1e6) { return +(n / 1e6).toFixed(2) + " million years ago"; }
			return Math.round(n / 1000) * 1000 + " years ago";
		}
		y = Math.round(y);
		if (y < 0) { return (-y) + " bce"; }
		if (y < 1000) { return y + " ce"; }
		return String(y);
	}

	return { parse: parse, format: format };
})();
