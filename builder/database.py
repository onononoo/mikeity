"""
builds a sqlite database of everything on the site, using sql/schema.sql,
then runs the named queries in sql/reports.sql. the results of those queries
are shown on the statistics page.

the database file (site/data/history.db) can also be opened with any sqlite
tool to ask your own questions, e.g. with python:

    python -m builder query "select name, dates from people where era = 'the classical world'"
"""

import os
import re
import sqlite3

from .util import read


def _century(year):
    """-3100 -> -31 (the 31st century bce), 1492 -> 15."""
    y = int(year)
    if y <= 0:
        return -((-y - 1) // 100 + 1) if y < 0 else -1
    return (y - 1) // 100 + 1


def life_known(p):
    """true when a person's dates give a real birth and death year, not a century or a guess range."""
    text = p["dates"]
    return (p.life.is_range and "century" not in text and "present" not in text
            and not p.life.deep and p.life.end - p.life.start < 130)


def century_label(c):
    c = int(c)
    n = abs(c)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix} century" + (" bce" if c < 0 else "")


def build(s, path):
    if os.path.exists(path):
        os.remove(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path)
    db.create_function("century_label", 1, century_label)
    db.executescript(read(os.path.join(s.root, "sql", "schema.sql")))

    db.executemany(
        "insert into regions (slug, name, description) values (?, ?, ?)",
        [(r.slug, r.name, r.get("description", "")) for r in s.regions],
    )
    db.executemany(
        "insert into eras (slug, number, title, starts, ends, start_year, end_year, summary, words)"
        " values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(e.slug, e.number, e.title, str(e.start_date), str(e.end_date),
          e.start_date.start, e.end_date.end, e.summary, e.doc.words) for e in s.eras],
    )
    for ev in s.events:
        deep = ev.when.deep
        db.execute(
            "insert into events (id, date_text, start_year, end_year, approx, deep, century,"
            " text, era, region) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ev.id, str(ev.when), ev.when.start, ev.when.end, int(ev.when.approx), int(deep),
             None if deep else _century(ev.when.start), ev.text, ev.era, ev.region_rec.slug),
        )
        db.executemany("insert into event_tags (event_id, tag) values (?, ?)",
                       [(ev.id, t) for t in ev.tags])
    db.executemany(
        "insert into people (slug, name, dates, born, died, life_known, role, about, era, region)"
        " values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(p.slug, p.name, str(p.life), p.life.start, p.life.end, int(life_known(p)), p.role,
          p.about, p.era, p.region_rec.slug) for p in s.people],
    )
    db.executemany(
        "insert into terms (slug, term, definition) values (?, ?, ?)",
        [(t.slug, t.term, t.definition) for t in s.terms],
    )
    db.executemany(
        "insert into term_usage (term, era) values (?, ?)",
        [(t.slug, e.slug) for t in s.terms for e in t.used_in],
    )
    db.commit()
    return db


_named = re.compile(r"^--\s*name:\s*([a-z0-9-]+)\s*$", re.M)


def reports(db, root):
    """run every '-- name:' query in sql/reports.sql and return the results."""
    source = read(os.path.join(root, "sql", "reports.sql"))
    chunks = _named.split(source)[1:]
    out = []
    for name, body in zip(chunks[0::2], chunks[1::2]):
        lines = body.strip().splitlines()
        about = " ".join(l[2:].strip() for l in lines if l.startswith("--"))
        sql = "\n".join(l for l in lines if not l.startswith("--")).strip()
        cur = db.execute(sql)
        cols = [c[0].replace("_", " ") for c in cur.description]
        out.append(dict(name=name, about=about, columns=cols, rows=cur.fetchall(), sql=sql))
    return out


def query(path, sql):
    db = sqlite3.connect(path)
    db.create_function("century_label", 1, century_label)
    cur = db.execute(sql)
    cols = [c[0] for c in cur.description or []]
    return cols, cur.fetchall()
