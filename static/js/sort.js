/*
 * makes any table with class "sortable" sortable by clicking its headings.
 * a heading with data-sort="number" sorts by the data-value of its cells
 * (so "500 bce" sorts before "1492"). other columns sort as text.
 */
(function () {
	function cell_value(row, col, numeric) {
		var cell = row.cells[col];
		if (!cell) { return numeric ? 0 : ""; }
		if (numeric) {
			var v = cell.getAttribute("data-value");
			v = parseFloat(v === null ? cell.textContent.replace(/[^\d.-]/g, "") : v);
			return isNaN(v) ? 0 : v;
		}
		return cell.textContent.toLowerCase();
	}

	function sort_table(table, col, numeric, th) {
		var head = table.rows[0];
		var body = head.parentNode;
		var rows = [];
		var i;
		for (i = 1; i < table.rows.length; i++) { rows.push(table.rows[i]); }

		// clicking the same heading again flips the order
		var dir = th.getAttribute("data-dir") === "up" ? "down" : "up";
		for (i = 0; i < head.cells.length; i++) {
			head.cells[i].removeAttribute("data-dir");
			head.cells[i].innerHTML = head.cells[i].innerHTML.replace(/ [▲▼]$/, "");
		}
		th.setAttribute("data-dir", dir);
		th.innerHTML += dir === "up" ? " ▲" : " ▼";

		// remember the old position so ties keep their order (a stable sort)
		for (i = 0; i < rows.length; i++) { rows[i].__pos = i; }
		rows.sort(function (a, b) {
			var x = cell_value(a, col, numeric), y = cell_value(b, col, numeric);
			var r = x < y ? -1 : x > y ? 1 : a.__pos - b.__pos;
			return dir === "up" ? r : -r;
		});
		for (i = 0; i < rows.length; i++) { body.appendChild(rows[i]); }
	}

	function setup(table) {
		var head = table.rows[0];
		if (!head) { return; }
		table.className += " sorting";
		for (var i = 0; i < head.cells.length; i++) {
			(function (col, th) {
				var numeric = th.getAttribute("data-sort") === "number";
				th.title = "click to sort";
				th.onclick = function () { sort_table(table, col, numeric, th); };
			})(i, head.cells[i]);
		}
	}

	var tables = document.getElementsByTagName("table");
	for (var i = 0; i < tables.length; i++) {
		if (/\bsortable\b/.test(tables[i].className)) { setup(tables[i]); }
	}
})();
