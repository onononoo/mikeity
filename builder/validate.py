"""
checks run on the finished html:

  - every tag that must be closed is closed, in the right order
  - every piece of text a visitor can read is lowercase
  - no page is empty

(links and anchors are checked separately by tools/checklinks.js.)
"""

import os
from html.parser import HTMLParser

_void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
         "source", "track", "wbr"}
# closing these is optional in html, so the checker does not insist on it
_optional = {"li", "p", "tr", "td", "th", "dt", "dd", "option", "thead", "tbody"}
# text inside these is code, not something a reader sees
_code = {"script", "style"}


class _checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.problems = []
        self.text = 0

    def where(self):
        line, _ = self.getpos()
        return f"line {line}"

    def handle_starttag(self, tag, attrs):
        if tag in _void:
            return
        self.stack.append(tag)
        for name, value in attrs:
            if name in ("title", "placeholder", "alt", "value", "aria-label") and value:
                self._lower(value, f"{tag} {name}")

    def handle_endtag(self, tag):
        if tag in _void:
            return
        while self.stack and self.stack[-1] != tag and self.stack[-1] in _optional:
            self.stack.pop()
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"{self.where()}: unexpected </{tag}>")
            return
        self.stack.pop()

    def handle_data(self, data):
        if self.stack and self.stack[-1] in _code:
            return
        if data.strip():
            self.text += len(data.strip())
            self._lower(data, "text")

    def _lower(self, text, what):
        if text != text.lower():
            snippet = " ".join(text.split())[:60]
            self.problems.append(f"{self.where()}: uppercase in {what}: {snippet!r}")

    def finish(self):
        leftover = [t for t in self.stack if t not in _optional]
        if leftover:
            self.problems.append(f"unclosed tags at end: {', '.join(leftover)}")
        if self.text == 0:
            self.problems.append("page has no text")


def check_file(path):
    c = _checker()
    with open(path, encoding="utf-8") as f:
        c.feed(f.read())
    c.close()
    c.finish()
    return c.problems


def check_folder(folder):
    problems = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".html"):
            problems += [f"{name}: {p}" for p in check_file(os.path.join(folder, name))]
    return problems
