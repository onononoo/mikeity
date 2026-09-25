#!/usr/bin/awk -f
#
# gaps.awk: finds the quiet stretches and the busy years on the timeline.
#
#   awk -f tools/gaps.awk site/data/events.tsv
#
# reads the tab separated timeline the builder writes, which is already in
# order of start year, and prints two kinds of tab separated lines:
#
#   gap   years   date before   event before   date after   event after
#   year  year    events        date   what happened that year (joined with " / ")
#
# a gap is the time between the end of everything that has happened so far
# and the start of the next event. only written history is looked at (from
# 3000 bce), since deep time is nearly all gaps. a busy year is a single,
# exact year (not "c." and not a range) with more than one event.
#
# plain posix awk: no gawk extras, so mawk and the bsd awk on a mac work too.

BEGIN {
	FS = "\t"
	OFS = "\t"
	from = -3000
	keep = 10          # how many gaps to print
	have = 0           # events seen so far (from 3000 bce on)
	ngap = 0
}

# the header and any comments
/^#/ { next }

NF < 6 {
	print "gaps.awk: line " NR " has " NF " columns" > "/dev/stderr"
	bad = 1
	exit 1
}

$1 + 0 >= from {
	start = $1 + 0
	end = $2 + 0

	if (have && start > reach) {
		add_gap(start - reach, reach_date, reach_text, $3, $6)
	}
	if (!have || end > reach) {
		reach = end
		reach_date = $3
		reach_text = $6
	}
	have = 1

	# busy years: exact single years only
	if (start == end && $3 !~ /^c\./ && $3 !~ /century|years ago|mya|bya/) {
		n[start]++
		when[start] = $3
		what[start] = (start in what) ? what[start] " / " $6 : $6
	}
}

# keep the biggest gaps in a small array sorted from big to small
# (insertion sort: there are only ever "keep" of them)
function add_gap(years, d1, t1, d2, t2,    i) {
	if (ngap == keep && years <= g_years[ngap]) {
		return
	}
	if (ngap < keep) {
		ngap++
	}
	for (i = ngap; i > 1 && g_years[i - 1] < years; i--) {
		g_years[i] = g_years[i - 1]
		g_line[i] = g_line[i - 1]
	}
	g_years[i] = years
	g_line[i] = d1 OFS t1 OFS d2 OFS t2
}

END {
	if (bad) {
		exit 1
	}
	for (i = 1; i <= ngap; i++) {
		print "gap", g_years[i], g_line[i]
	}
	for (y in n) {
		if (n[y] > 1) {
			print "year", y, n[y], when[y], what[y]
		}
	}
}
