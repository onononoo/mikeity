# another way to build, for anyone who has make. "make" does the same as
# build.sh; the other targets run one part at a time.
#
#   make            tests, site, link check, and the command line tools
#   make site       just the site (python also runs the c++, awk and c# steps)
#   make test       python and javascript tests
#   make tools      the c timeline viewer
#   make clean      remove compiled tools

PYTHON ?= python3
CC     ?= cc
CFLAGS ?= -std=c99 -O2 -Wall -Wextra

.PHONY: all site test check links stats tools clean

all: test site links tools stats

site:
	$(PYTHON) -X utf8 -m builder

check:
	$(PYTHON) -X utf8 -m builder check

test:
	$(PYTHON) -X utf8 -m unittest discover -s tests -t . -q
	-command -v node >/dev/null && node tests/test_dates.js

links: site
	-command -v node >/dev/null && node tools/checklinks.js

stats:
	-command -v perl >/dev/null && perl tools/stats.pl

tools: tools/timeline

tools/timeline: tools/timeline.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -rf tools/timeline tools/timeline.exe tools/bin
