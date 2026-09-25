#!/usr/bin/env sh
# builds and checks the whole site. run from anywhere: sh build.sh
# steps that need a tool you do not have (node, gcc, perl) are skipped.

set -e
cd "$(dirname "$0")"

# use the first python that actually runs (on windows "python3" can be a
# store shortcut that exists but does nothing)
python=
for p in python3 python py; do
	if $p -c "import sys; sys.exit(sys.version_info < (3, 9))" >/dev/null 2>&1; then
		python=$p
		break
	fi
done
[ -n "$python" ] || { echo "python 3.9 or newer is needed"; exit 1; }

step() { printf '\n== %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

step "python tests"
$python -X utf8 -m unittest discover -s tests -t . -q

if have node; then
	step "javascript tests"
	node tests/test_dates.js
fi

step "build"
$python -X utf8 -m builder

if have node; then
	step "link check"
	node tools/checklinks.js
else
	step "link check skipped (no node)"
fi

if have gcc; then
	step "c timeline tool"
	gcc -std=c99 -O2 -Wall -Wextra -Werror -o tools/timeline tools/timeline.c
	./tools/timeline --histogram
else
	step "c timeline tool skipped (no gcc)"
fi

if have perl; then
	step "content statistics"
	perl tools/stats.pl
else
	step "content statistics skipped (no perl)"
fi

printf '\nall done. open site/index.html, or run: %s -m builder serve\n' "$python"
