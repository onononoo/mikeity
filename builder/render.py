"""
turns the loaded site into html pages using the templates folder.
"""

import os
from collections import Counter

from . import dates, markup
from .loader import record
from .templates import environment
from .util import plural, read, write

site_name = "the history of the world"


def _nav(s):
    return [
        ("index.html", "home"),
        ("timeline.html", "timeline"),
        ("topics.html", "topics"),
        ("religions.html", "religions"),
        ("regions.html", "regions"),
        ("people.html", "people"),
        ("glossary.html", "glossary"),
        ("search.html", "search"),
        ("statistics.html", "statistics"),
        ("about.html", "about"),
    ]


def _toc(headings):
    """nest (level, id, text) headings into a list of sections with subsections."""
    out = []
    for level, hid, text in headings:
        if level == 2 or not out:
            out.append({"id": hid, "text": text, "subs": []})
        else:
            out[-1]["subs"].append({"id": hid, "text": text})
    return out


def _words(s):
    return sum(e.doc.words for e in s.eras) + sum(t.doc.words for t in s.topics)


def _bar(n, biggest, width=40):
    """a text bar chart made of characters, like an old web page would have."""
    if biggest == 0:
        return ""
    k = max(1, round(width * n / biggest)) if n else 0
    return "#" * k


class renderer:
    def __init__(self, s, out):
        self.s = s
        self.out = out
        self.env = environment(os.path.join(s.root, "templates"))
        self.written = []
        self.reports = []
        # what the steps in other languages found (see extras.py); empty until the builder sets it
        self.extras = None

    # --------------------------------------------------------------- helpers

    @property
    def more(self):
        return self.extras or record(charts=None, gaps=None, contemporaries=None, shared=None,
                                     api=None, log=[])

    def page(self, filename, template, title, crumbs=None, **ctx):
        # pages in a subfolder (like islam/people.html) reach the rest of the site through "../"
        root = "../" * filename.count("/")
        body = self.env.render(template, ctx, site=self.s, dates=dates, title=title, root=root)
        full = self.env.render(
            "layout.html",
            site=self.s,
            site_name=site_name,
            title=title,
            page_title=title if filename != "index.html" else None,
            crumbs=crumbs or [],
            nav=_nav(self.s),
            current=ctx.get("current", filename),
            subnav=ctx.get("subnav"),
            subnav_title=ctx.get("subnav_title"),
            subcurrent=ctx.get("subcurrent"),
            root=root,
            scripts=ctx.get("scripts", []),
            body=body,
        )
        write(os.path.join(self.out, filename), full)
        self.written.append(filename)

    # --------------------------------------------------------------- pages

    def index(self):
        s = self.s
        self.page(
            "index.html", "index.html", site_name,
            eras=[dict(era=e, toc=_toc(e.doc.headings),
                       span=dates.span_label(e.start_date.start, e.end_date.end)) for e in s.eras],
            topics=s.topics,
            counts=dict(events=len(s.events), people=len(s.people), terms=len(s.terms),
                        words=_words(s), regions=len(s.regions), topics=len(s.topics)),
        )

    def eras(self):
        for e in self.s.eras:
            self.page(
                f"{e.slug}.html", "era.html", f"part {e.number}: {e.title}",
                crumbs=[("index.html", "home")],
                era=e,
                toc=_toc(e.doc.headings),
                span=dates.span_label(e.start_date.start, e.end_date.end),
                scripts=["sort.js"],
            )

    def timeline(self):
        s = self.s
        self.page(
            "timeline.html", "timeline.html", "the whole timeline",
            crumbs=[("index.html", "home")],
            events=s.events,
            scripts=["dates.js", "sort.js", "timeline.js"],
        )

    def topics(self):
        s = self.s
        self.page(
            "topics.html", "topics.html", "topics",
            crumbs=[("index.html", "home")],
            topics=[dict(topic=t, toc=_toc(t.doc.headings)) for t in s.topics],
        )
        for t in s.topics:
            self.page(
                f"{t.slug}.html", "topic.html", t.title,
                crumbs=[("index.html", "home"), ("topics.html", "topics")],
                topic=t,
                toc=_toc(t.doc.headings),
            )

    def religions(self):
        s = self.s
        self.page(
            "religions.html", "religions.html", "religions",
            crumbs=[("index.html", "home")],
            religions=s.religions,
            shared=self.more.shared,
        )
        pages = [("index.html", "story"), ("timeline.html", "timeline"),
                 ("people.html", "people"), ("glossary.html", "glossary")]
        for i, r in enumerate(s.religions):
            common = dict(
                religion=r,
                others=[o for o in s.religions if o is not r],
                subnav=pages, subnav_title=r.name, current="religions.html",
            )
            home = [("index.html", "home"), ("religions.html", "religions")]
            inside = home + [(f"{r.slug}/index.html", r.name)]
            self.page(f"{r.slug}/index.html", "religion.html", r.name, crumbs=home,
                      subcurrent="index.html", toc=_toc(r.doc.headings), **common)
            self.page(f"{r.slug}/timeline.html", "religion_timeline.html", f"{r.name}: timeline",
                      crumbs=inside, subcurrent="timeline.html",
                      scripts=["dates.js", "sort.js", "timeline.js"], **common)
            self.page(f"{r.slug}/people.html", "religion_people.html", f"{r.name}: people",
                      crumbs=inside, subcurrent="people.html", scripts=["sort.js"], **common)
            letters = {}
            for t in r.terms:
                letters.setdefault(t.term[0], []).append(t)
            self.page(f"{r.slug}/glossary.html", "religion_glossary.html", f"{r.name}: glossary",
                      crumbs=inside, subcurrent="glossary.html", letters=sorted(letters.items()),
                      **common)

    def regions(self):
        s = self.s
        self.page(
            "regions.html", "regions.html", "history by region",
            crumbs=[("index.html", "home")],
            regions=[r for r in s.regions if r.events or r.people],
        )

    def people(self):
        together = self.more.contemporaries or {}
        for p in self.s.people:
            p.together = together.get(p.slug)
        self.page(
            "people.html", "people.html", "people",
            crumbs=[("index.html", "home")],
            people=self.s.people,
            found_together=bool(together),
            scripts=["sort.js"],
        )

    def glossary(self):
        s = self.s
        letters = {}
        for t in s.terms:
            letters.setdefault(t.term[0], []).append(t)
        self.page(
            "glossary.html", "glossary.html", "glossary",
            crumbs=[("index.html", "home")],
            letters=sorted(letters.items()),
        )

    def search(self):
        self.page(
            "search.html", "search.html", "search",
            crumbs=[("index.html", "home")],
            scripts=["search-index.js", "dates.js", "search.js"],
        )

    def statistics(self):
        s = self.s
        era_rows = []
        biggest = max((e.doc.words for e in s.eras), default=0)
        for e in s.eras:
            era_rows.append(dict(era=e, words=e.doc.words, events=len(e.events),
                                 people=len(e.people), terms=len(e.terms),
                                 bar=_bar(e.doc.words, biggest)))
        region_counts = sorted(((len(r.events), r) for r in s.regions), key=lambda x: -x[0])
        rbig = region_counts[0][0] if region_counts else 0
        region_rows = [dict(region=r, events=n, bar=_bar(n, rbig)) for n, r in region_counts if n]
        tags = Counter(t for ev in s.events for t in ev.tags).most_common(25)
        tbig = tags[0][1] if tags else 0
        tag_rows = [dict(tag=t, n=n, bar=_bar(n, tbig)) for t, n in tags]
        first, last = (s.events[0], s.events[-1]) if s.events else (None, None)
        self.page(
            "statistics.html", "statistics.html", "statistics",
            crumbs=[("index.html", "home")],
            era_rows=era_rows, region_rows=region_rows, tag_rows=tag_rows,
            first=first, last=last,
            reports=self.reports,
            extras=self.more,
            crowded=self._crowded(),
            totals=dict(words=_words(s), events=len(s.events),
                        people=len(s.people), terms=len(s.terms)),
            scripts=["sort.js"],
        )

    def _crowded(self, n=10):
        """the people who shared their lifetime with the most others (from the c# step)."""
        together = self.more.contemporaries or {}
        rows = [(together[p.slug].count, p) for p in self.s.people if p.slug in together]
        rows.sort(key=lambda x: (-x[0], x[1].life.start))
        return [dict(person=p, count=k) for k, p in rows[:n] if k]

    def api(self):
        self.page(
            "api.html", "api.html", "json api",
            crumbs=[("index.html", "home")],
            api=self.more.api,
        )

    def about(self):
        doc = markup.parse(read(os.path.join(self.s.root, "content", "about.txt")))
        self.page(
            "about.html", "page.html", "about this site",
            crumbs=[("index.html", "home")],
            doc=doc, toc=_toc(doc.headings),
        )

    def all(self):
        self.index()
        self.eras()
        self.timeline()
        self.topics()
        self.religions()
        self.regions()
        self.people()
        self.glossary()
        self.search()
        self.statistics()
        self.api()
        self.about()
        return self.written


def summary(s):
    return ", ".join([
        plural(len(s.eras), "part"),
        plural(len(s.events), "event"),
        plural(len(s.people), "person", "people"),
        plural(len(s.terms), "glossary term"),
        plural(len(s.topics), "topic"),
        plural(_words(s), "word"),
    ])
