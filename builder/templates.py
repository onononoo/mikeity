"""
a small template engine, written from scratch so the project has no
dependencies outside the python standard library.

syntax:

    {{ name }}                   print a value, html-escaped
    {{ person.name }}            dotted lookup (works on dicts and attributes)
    {{ body|raw }}               print without escaping
    {{ n|commas }}               filters can be chained: {{ x|lower|raw }}
    {% if cond %} ... {% elif other %} ... {% else %} ... {% endif %}
    {% if not cond %}            simple negation
    {% for x in items %} ... {% else %} (shown when empty) ... {% endfor %}
    {% include "file.html" %}    pull in another template
    {# a comment #}

inside a for loop the name "loop" holds index (from 1), first, last and length.
"""

import html
import os
import re

_token = re.compile(r"({{.*?}}|{%.*?%}|{#.*?#})", re.S)


class template_error(Exception):
    pass


# ---------------------------------------------------------------- filters

def _commas(v):
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return v


filters = {
    "raw": lambda v: v,
    "lower": lambda v: str(v).lower(),
    "commas": _commas,
    "length": lambda v: len(v),
    "join": lambda v: ", ".join(str(x) for x in v),
    "default": lambda v: v if v not in (None, "") else "—",
    "slug": lambda v: re.sub(r"[^a-z0-9]+", "-", str(v).lower()).strip("-"),
}


# ---------------------------------------------------------------- lookups

def _lookup(ctx, path):
    path = path.strip()
    if re.fullmatch(r'"[^"]*"|\'[^\']*\'', path):
        return path[1:-1]
    if re.fullmatch(r"-?\d+", path):
        return int(path)
    parts = path.split(".")
    if parts[0] not in ctx:
        return None
    value = ctx[parts[0]]
    for p in parts[1:]:
        if isinstance(value, dict):
            value = value.get(p)
        elif re.fullmatch(r"\d+", p) and isinstance(value, (list, tuple)):
            i = int(p)
            value = value[i] if i < len(value) else None
        else:
            value = getattr(value, p, None)
        if value is None:
            return None
    return value


def _eval(ctx, expr):
    """evaluate a tiny expression: 'a', 'not a', 'a == b', 'a != b', 'a and b', 'a or b'."""
    expr = expr.strip()
    for op in (" or ", " and "):
        if op in expr:
            left, right = expr.split(op, 1)
            l = _eval(ctx, left)
            if op == " or ":
                return l or _eval(ctx, right)
            return l and _eval(ctx, right)
    if expr.startswith("not "):
        return not _eval(ctx, expr[4:])
    for op in ("==", "!="):
        if op in expr:
            a, b = (_lookup(ctx, s) for s in expr.split(op, 1))
            return (a == b) if op == "==" else (a != b)
    return _lookup(ctx, expr)


# ---------------------------------------------------------------- nodes

class _text:
    def __init__(self, s):
        self.s = s

    def render(self, ctx, env):
        return self.s


class _var:
    def __init__(self, expr):
        name, *fs = [p.strip() for p in expr.split("|")]
        for f in fs:
            if f not in filters:
                raise template_error(f"unknown filter: {f}")
        self.name, self.filters = name, fs

    def render(self, ctx, env):
        v = _lookup(ctx, self.name)
        for f in self.filters:
            v = filters[f](v)
        if v is None:
            return ""
        return str(v) if "raw" in self.filters else html.escape(str(v), quote=True)


class _if:
    def __init__(self):
        self.branches = []  # list of (condition or none, [nodes])

    def render(self, ctx, env):
        for cond, body in self.branches:
            if cond is None or _eval(ctx, cond):
                return "".join(n.render(ctx, env) for n in body)
        return ""


class _for:
    def __init__(self, var, source):
        self.var, self.source = var, source
        self.body, self.empty = [], []

    def render(self, ctx, env):
        items = _lookup(ctx, self.source) or []
        if isinstance(items, dict):
            items = list(items.items())
        items = list(items)
        if not items:
            return "".join(n.render(ctx, env) for n in self.empty)
        out = []
        n = len(items)
        for i, item in enumerate(items):
            inner = dict(ctx)
            if "," in self.var:
                names = [v.strip() for v in self.var.split(",")]
                for name, value in zip(names, item):
                    inner[name] = value
            else:
                inner[self.var] = item
            inner["loop"] = {"index": i + 1, "first": i == 0, "last": i == n - 1, "length": n,
                             "odd": i % 2 == 1}
            out.append("".join(node.render(inner, env) for node in self.body))
        return "".join(out)


class _include:
    def __init__(self, name):
        self.name = name

    def render(self, ctx, env):
        return env.get(self.name).render(ctx)


# ---------------------------------------------------------------- parser

def _compile(source, name="<string>"):
    root = []
    stack = [("root", root, None)]  # (kind, current list, node)

    def current():
        return stack[-1][1]

    for tok in _token.split(source):
        if not tok:
            continue
        if tok.startswith("{#"):
            continue
        if tok.startswith("{{"):
            current().append(_var(tok[2:-2]))
            continue
        if not tok.startswith("{%"):
            current().append(_text(tok))
            continue

        stmt = tok[2:-2].strip()
        word = stmt.split()[0]
        if word == "if":
            node = _if()
            node.branches.append((stmt[3:], []))
            current().append(node)
            stack.append(("if", node.branches[-1][1], node))
        elif word in ("elif", "else") and stack[-1][0] == "if":
            node = stack.pop()[2]
            node.branches.append((stmt[5:] if word == "elif" else None, []))
            stack.append(("if", node.branches[-1][1], node))
        elif word == "else" and stack[-1][0] == "for":
            node = stack.pop()[2]
            stack.append(("for-else", node.empty, node))
        elif word == "endif":
            if stack[-1][0] != "if":
                raise template_error(f"{name}: endif without if")
            stack.pop()
        elif word == "for":
            m = re.fullmatch(r"for\s+([\w\s,]+?)\s+in\s+(.+)", stmt)
            if not m:
                raise template_error(f"{name}: bad for statement: {stmt}")
            node = _for(m.group(1), m.group(2).strip())
            current().append(node)
            stack.append(("for", node.body, node))
        elif word == "endfor":
            if stack[-1][0] not in ("for", "for-else"):
                raise template_error(f"{name}: endfor without for")
            stack.pop()
        elif word == "include":
            current().append(_include(stmt.split(None, 1)[1].strip("\"' ")))
        else:
            raise template_error(f"{name}: unknown tag: {stmt}")

    if len(stack) != 1:
        raise template_error(f"{name}: unclosed {stack[-1][0]} block")
    return root


class template:
    def __init__(self, source, env=None, name="<string>"):
        self.nodes = _compile(source, name)
        self.env = env
        self.name = name

    def render(self, ctx=None, **kw):
        ctx = dict(ctx or {}, **kw)
        return "".join(n.render(ctx, self.env) for n in self.nodes)


class environment:
    """loads templates from a folder and caches them."""

    def __init__(self, folder):
        self.folder = folder
        self.cache = {}

    def get(self, name):
        if name not in self.cache:
            path = os.path.join(self.folder, name)
            if not os.path.exists(path):
                raise template_error(f"template not found: {name}")
            with open(path, encoding="utf-8") as f:
                self.cache[name] = template(f.read(), self, name)
        return self.cache[name]

    def render(self, name, ctx=None, **kw):
        return self.get(name).render(ctx, **kw)
