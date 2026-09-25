# mikeity: the history of the world

a plain html website that tells the whole history of the world, from the big bang to the present, in eleven parts. it has a filterable timeline of 445 dated events, 138 people, a 123-term glossary, a history-by-region page, full-text search, and a statistics page built from its own sqlite database.

the finished site is in `site/`. open `site/index.html` in any browser. no server is needed.

## building

you need python 3.9 or newer. node, gcc, and perl are optional; the build scripts skip the steps that need them if they are missing.

```sh
sh build.sh                        # mac, linux, git bash
powershell -file build.ps1         # windows
```

or just the site:

```sh
python -m builder                  # build site/
python -m builder check            # check the data without writing anything
python -m builder serve 8000       # serve site/ at http://localhost:8000
python -m builder query "select name, dates from people where region = 'africa'"
```

## how it is put together

| folder / file | language | what it is |
|---|---|---|
| `data/` | json | parts (`eras.json`), events (one file per part in `events/`), people, glossary, regions |
| `content/eras/` | plain text | the story of each part, in a small markup language (see `builder/markup.py`) |
| `content/about.txt` | plain text | the about page |
| `builder/` | python | the static site generator, with no dependencies outside the standard library |
| `builder/dates.py` | python | parses dates like `c. 3100 bce`, `66 mya`, `5th century bce`, `1914-1918`, `1945 to present` |
| `builder/markup.py` | python | the markup parser |
| `builder/templates.py` | python | a small template engine (`{{ }}`, `{% if %}`, `{% for %}`, filters, includes) |
| `builder/loader.py` | python | loads and cross-checks all data; the build fails on a broken link or bad date |
| `builder/database.py` | python + sql | builds `site/data/history.db` and runs the reports |
| `builder/validate.py` | python | checks the finished html: closed tags, no uppercase text, no empty pages |
| `templates/` | html | page templates |
| `sql/schema.sql` | sql | the database schema |
| `sql/reports.sql` | sql | named queries shown on the statistics page |
| `static/style.css` | css | the stylesheet, kept as small as possible |
| `static/js/` | javascript | table sorting, timeline filtering, search (plain es5, works from `file://`) |
| `tools/checklinks.js` | javascript (node) | checks every link and anchor on the built site |
| `tools/timeline.c` | c | a terminal timeline viewer that reads `site/data/events.tsv` |
| `tools/stats.pl` | perl | word counts, link counts, and reading ease for each part |
| `tests/` | python + javascript | unit tests for dates, markup, templates, and the browser date parser |
| `build.sh`, `build.ps1` | shell, powershell | run every step in order |

## the terminal timeline

```sh
gcc -std=c99 -O2 -o tools/timeline tools/timeline.c
tools/timeline --from "500 bce" --to 1500 --grep rome
tools/timeline --part 10
tools/timeline --region africa --count
tools/timeline --histogram
```

## adding to the history

- **an event**: add a line to the right file in `data/events/`. the part comes from the file name.
- **a person**: add them to `data/people.json`, then link to them in the text with `[[@their name]]`.
- **a glossary term**: add it to `data/glossary.json`, then link to it with `[[term]]` or `[[term|shown words]]`.
- **text**: edit `content/eras/`. headings are `== ` and `=== `, lists are `- `, tables are `| a | b |`.

then run the build. it stops and says exactly what is wrong if a date cannot be read, a link points nowhere, or any text on a page is not lowercase.
