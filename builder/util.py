"""small helpers shared by the other modules."""

import os
import re
import unicodedata


def slugify(text):
    """'göbekli tepe' -> 'gobekli-tepe'. used for ids and file names."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-") or "x"


def write(path, text):
    """write a text file with unix line endings, creating folders as needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def plural(n, word, many=None):
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
