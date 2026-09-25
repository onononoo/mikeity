"""
a tiny markup language for the era text files.

block syntax (one per line or paragraph):

    == section title            a section heading (h2). an id is made from the title,
    == section title {#my-id}   or given by hand like this
    === subsection title        a subsection heading (h3)
    - item                      a bullet list
    + item                      a numbered list
    > text                      a quote or aside
    | a | b |                   a table row. a row of dashes (|---|---|) under the
                                first row makes it a header
    ---                         a horizontal rule
    anything else               a paragraph. paragraphs are split by blank lines

inline syntax:

    **bold**  _italic_
    [[term]]                    link to a glossary entry
    [[term|shown words]]        same, with different link text
    [[@person name]]            link to someone on the people page
    [[part:slug|words]]         link to another part of the site
                                (pages in a subfolder pass root="../")
    [words](url)                a normal link

everything is html-escaped before the inline syntax is applied, so the text
files can never inject raw html.
"""

import html
import re

from .util import slugify


class document:
    def __init__(self):
        self.html = ""
        self.headings = []   # list of (level, id, text)
        self.terms = set()   # glossary slugs referenced
        self.people = set()  # people slugs referenced
        self.parts = set()   # era slugs referenced
        self.words = 0


_inline_link = re.compile(r"\[\[(.+?)\]\]")
_plain_link = re.compile(r"\[([^\[\]]+?)\]\(([^()\s]+)\)")
_bold = re.compile(r"\*\*(.+?)\*\*")
_italic = re.compile(r"(?<![\w/])_(.+?)_(?![\w])")
_heading = re.compile(r"^(={2,3})\s+(.+?)(?:\s+\{#([a-z0-9-]+)\})?\s*$")


def _inline(text, doc, root=""):
    """apply inline markup to one already-escaped line of text."""

    def link(m):
        body = m.group(1)
        target, _, shown = body.partition("|")
        target = target.strip()
        shown = shown.strip()
        if target.startswith("@"):
            name = target[1:].strip()
            slug = slugify(name)
            doc.people.add(slug)
            return f'<a href="people.html#{slug}">{shown or name}</a>'
        if target.startswith("part:"):
            slug = target[5:].strip()
            doc.parts.add(slug)
            return f'<a href="{root}{slug}.html">{shown or slug.replace("-", " ")}</a>'
        slug = slugify(target)
        doc.terms.add(slug)
        return f'<a href="glossary.html#{slug}" class="term">{shown or target}</a>'

    text = _inline_link.sub(link, text)
    text = _plain_link.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = _bold.sub(r"<b>\1</b>", text)
    text = _italic.sub(r"<i>\1</i>", text)
    return text


def _words(text):
    # strip link syntax before counting so "[[term|words]]" counts as its words
    text = _inline_link.sub(lambda m: m.group(1).split("|")[-1].lstrip("@"), text)
    return len(re.findall(r"[a-z0-9'’-]+", text.lower()))


def _table(rows, doc, root=""):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head = None
    if len(cells) > 1 and all(re.fullmatch(r":?-{3,}:?", c) for c in cells[1]):
        head, cells = cells[0], cells[2:]
    out = ['<table class="grid">']
    if head:
        out.append("<tr>" + "".join(f"<th>{_inline(c, doc, root)}</th>" for c in head) + "</tr>")
    for row in cells:
        out.append("<tr>" + "".join(f"<td>{_inline(c, doc, root)}</td>" for c in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def parse(source, reserved=(), root=""):
    """
    turn markup text into a document. ids in `reserved` are already used by
    the page template, so headings that would clash get a number added.
    """
    doc = document()
    out = []
    used_ids = set(reserved)

    # split into blocks of consecutive lines that share a type
    blocks = []
    kind, lines = None, []

    def flush():
        nonlocal kind, lines
        if lines:
            blocks.append((kind, lines))
        kind, lines = None, []

    for raw in source.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if line.startswith("#"):
            # lines starting with a single # are notes for the writer, not shown
            continue
        if _heading.match(line):
            flush()
            blocks.append(("heading", [line]))
            continue
        if line.strip() == "---":
            flush()
            blocks.append(("rule", [line]))
            continue
        k = {"- ": "ul", "+ ": "ol", "> ": "quote", "| ": "table"}.get(line[:2], "p")
        if line.startswith("|"):
            k = "table"
        if k != kind:
            flush()
            kind = k
        lines.append(line)
    flush()

    for kind, lines in blocks:
        if kind == "heading":
            m = _heading.match(lines[0])
            level = len(m.group(1))
            title = html.escape(m.group(2), quote=False)
            hid = m.group(3) or slugify(m.group(2))
            base, n = hid, 2
            while hid in used_ids:
                hid, n = f"{base}-{n}", n + 1
            used_ids.add(hid)
            plain = re.sub(r"<[^>]+>", "", _inline(title, document()))
            doc.headings.append((level, hid, plain))
            out.append(f'<h{level} id="{hid}">{_inline(title, doc, root)}</h{level}>')
            continue
        if kind == "rule":
            out.append("<hr>")
            continue

        if kind in ("ul", "ol", "quote"):
            # drop the "- ", "+ " or "> " marker before escaping
            lines = [l[2:].strip() for l in lines]
        doc.words += sum(_words(l) for l in lines)
        esc = [html.escape(l, quote=False) for l in lines]

        if kind in ("ul", "ol"):
            items = "\n".join(f"<li>{_inline(l, doc, root)}</li>" for l in esc)
            out.append(f"<{kind}>\n{items}\n</{kind}>")
        elif kind == "quote":
            body = " ".join(esc)
            out.append(f"<blockquote>{_inline(body, doc, root)}</blockquote>")
        elif kind == "table":
            out.append(_table(esc, doc, root))
        else:
            out.append(f"<p>{_inline(' '.join(l.strip() for l in esc), doc, root)}</p>")

    doc.html = "\n\n".join(out)
    return doc
