"""
reads everything in data/ and content/ into one site object, and checks
that it all fits together (dates parse, links point at real things, etc).
"""

import json
import os

from . import dates, markup
from .util import read, slugify


# ids the era page template uses itself (see templates/era.html)
era_page_ids = ("top", "part-timeline", "part-people", "part-terms")


class load_error(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


class record(dict):
    """a dict whose keys can also be read as attributes (handy in templates)."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    # attributes are stored as keys too, so templates see them
    __setattr__ = dict.__setitem__

    # records point at each other (era.next, event.era_rec...), so compare by identity
    __eq__ = object.__eq__
    __ne__ = object.__ne__
    __hash__ = object.__hash__


class site:
    def __init__(self, root):
        self.root = root
        self.eras = []
        self.era_by_slug = {}
        self.events = []
        self.people = []
        self.person_by_slug = {}
        self.terms = []
        self.term_by_slug = {}
        self.regions = []
        self.region_by_slug = {}
        self.problems = []

    def problem(self, where, what):
        self.problems.append(f"{where}: {what}")


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _date(s, where, raw):
    try:
        return dates.parse(raw)
    except dates.date_error as e:
        s.problem(where, str(e))
        return None


def load(root):
    s = site(root)
    data = os.path.join(root, "data")

    # ---------------------------------------------------------- regions
    for r in _json(os.path.join(data, "regions.json")):
        r = record(r, slug=slugify(r["name"]))
        r.events, r.people = [], []
        s.regions.append(r)
        s.region_by_slug[r.slug] = r

    # ---------------------------------------------------------- eras
    for i, e in enumerate(_json(os.path.join(data, "eras.json")), 1):
        e = record(e, number=i)
        where = f"eras.json ({e['slug']})"
        e.start_date = _date(s, where, e["start"])
        e.end_date = _date(s, where, e["end"])
        path = os.path.join(root, "content", "eras", f"{i:02d}-{e['slug']}.txt")
        if not os.path.exists(path):
            s.problem(where, f"missing text file {os.path.relpath(path, root)}")
            e.doc = markup.parse("")
        else:
            e.doc = markup.parse(read(path), reserved=era_page_ids)
        e.events, e.people, e.terms = [], [], []
        s.eras.append(e)
        s.era_by_slug[e.slug] = e

    for a, b in zip(s.eras, s.eras[1:]):
        a.next, b.prev = b, a
    if s.eras:
        s.eras[0].prev = None
        s.eras[-1].next = None

    # ---------------------------------------------------------- events
    # one file per era, named like "04-the-first-civilizations.json". the era
    # comes from the file name unless an event names a different one.
    raw_events = []
    folder = os.path.join(data, "events")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        era_slug = name[3:-5] if name[:2].isdigit() else None
        for i, ev in enumerate(_json(os.path.join(folder, name)), 1):
            ev.setdefault("era", era_slug)
            raw_events.append((f"events/{name} #{i}", ev))

    for n, (where, ev) in enumerate(raw_events, 1):
        ev = record(ev, id=n)
        ev.when = _date(s, where, ev["date"])
        if ev.when is None:
            continue
        ev.era_rec = s.era_by_slug.get(ev["era"])
        ev.region_rec = s.region_by_slug.get(slugify(ev["region"]))
        if not ev.era_rec:
            s.problem(where, f"unknown era {ev['era']!r}")
            continue
        if not ev.region_rec:
            s.problem(where, f"unknown region {ev['region']!r}")
            continue
        ev.tags = ev.get("tags", [])
        s.events.append(ev)
        ev.era_rec.events.append(ev)
        ev.region_rec.events.append(ev)

    s.events.sort(key=lambda ev: (ev.when.start, ev.when.end))
    for e in s.eras:
        e.events.sort(key=lambda ev: ev.when.start)
    for r in s.regions:
        r.events.sort(key=lambda ev: ev.when.start)

    # ---------------------------------------------------------- people
    for p in _json(os.path.join(data, "people.json")):
        p = record(p, slug=slugify(p["name"]))
        where = f"people.json ({p['name']})"
        p.life = _date(s, where, p["dates"])
        p.era_rec = s.era_by_slug.get(p["era"])
        p.region_rec = s.region_by_slug.get(slugify(p["region"]))
        if p.slug in s.person_by_slug:
            s.problem(where, "listed twice")
            continue
        if not p.era_rec:
            s.problem(where, f"unknown era {p['era']!r}")
            continue
        if not p.region_rec:
            s.problem(where, f"unknown region {p['region']!r}")
            continue
        s.people.append(p)
        s.person_by_slug[p.slug] = p
        p.era_rec.people.append(p)
        p.region_rec.people.append(p)

    s.people.sort(key=lambda p: (p.life.start if p.life else 0, p.name))
    for e in s.eras:
        e.people.sort(key=lambda p: p.life.start if p.life else 0)

    # ---------------------------------------------------------- glossary
    for t in _json(os.path.join(data, "glossary.json")):
        t = record(t, slug=slugify(t["term"]))
        if t.slug in s.term_by_slug:
            s.problem(f"glossary.json ({t['term']})", "listed twice")
            continue
        t.used_in = []
        s.terms.append(t)
        s.term_by_slug[t.slug] = t
    s.terms.sort(key=lambda t: t.term)

    for t in s.terms:
        for other in t.get("see", []):
            if slugify(other) not in s.term_by_slug:
                s.problem(f"glossary.json ({t.term})", f"'see' points at missing term {other!r}")

    # ---------------------------------------------------------- cross links in text
    for e in s.eras:
        where = f"content/eras/{e.number:02d}-{e.slug}.txt"
        for slug in sorted(e.doc.people):
            if slug not in s.person_by_slug:
                s.problem(where, f"links to unknown person {slug!r}")
        for slug in sorted(e.doc.terms):
            t = s.term_by_slug.get(slug)
            if not t:
                s.problem(where, f"links to unknown glossary term {slug!r}")
            else:
                e.terms.append(t)
                t.used_in.append(e)
        for slug in sorted(e.doc.parts):
            if slug not in s.era_by_slug:
                s.problem(where, f"links to unknown part {slug!r}")
        e.terms.sort(key=lambda t: t.term)

    if s.problems:
        raise load_error(s.problems)
    return s
