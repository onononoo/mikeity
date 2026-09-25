"""
command line entry point.

    python -m builder                 build the site into site/
    python -m builder build           same thing
    python -m builder check           load and check the data without writing anything
    python -m builder query "sql"     run a sql query against site/data/history.db
    python -m builder serve [port]    serve site/ at http://localhost:8000
"""

import os
import shutil
import sys
import time

from . import database, exports, loader, render, validate

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, "site")
db_path = os.path.join(out, "data", "history.db")


def say(msg):
    print(f"  {msg}")


def load():
    try:
        return loader.load(root)
    except loader.load_error as e:
        print("the data has problems:")
        for p in e.problems:
            print(f"  - {p}")
        sys.exit(1)


def clean():
    """empty the output folder but keep the folder itself (servers may be watching it)."""
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):
        path = os.path.join(out, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def copy_static():
    src = os.path.join(root, "static")
    n = 0
    for folder, _, files in os.walk(src):
        for f in files:
            rel = os.path.relpath(os.path.join(folder, f), src)
            dest = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(folder, f), dest)
            n += 1
    return n


def build():
    started = time.perf_counter()
    print("building the history of the world")

    s = load()
    say(f"loaded {render.summary(s)}")

    clean()
    say(f"copied {copy_static()} static files")

    db = database.build(s, db_path)
    reports = database.reports(db, root)
    db.close()
    say(f"built sqlite database with {len(reports)} reports")

    r = render.renderer(s, out)
    r.reports = reports
    pages = r.all()
    say(f"wrote {len(pages)} pages")

    n = exports.write_all(s, out)
    say(f"wrote search index ({n} entries), json and tsv exports")

    problems = validate.check_folder(out)
    if problems:
        print("the generated html has problems:")
        for p in problems[:50]:
            print(f"  - {p}")
        sys.exit(1)
    say("html checks passed")

    print(f"done in {time.perf_counter() - started:.2f}s -> {os.path.relpath(out, os.getcwd())}")


def check():
    s = load()
    print(f"ok: {render.summary(s)}")


def query(sql):
    if not os.path.exists(db_path):
        print("no database yet. run: python -m builder")
        sys.exit(1)
    cols, rows = database.query(db_path, sql)
    if not cols:
        print("(no results)")
        return
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c))
              for i, c in enumerate(cols)]
    widths = [min(w, 60) for w in widths]
    line = lambda vals: "  ".join(str(v)[:w].ljust(w) for v, w in zip(vals, widths))
    print(line(cols))
    print(line("-" * w for w in widths))
    for r in rows:
        print(line(r))
    print(f"({len(rows)} rows)")


def serve(port=8000):
    import functools
    import http.server

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=out)
    print(f"serving {out} at http://localhost:{port} (ctrl+c to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


def main(argv):
    cmd = argv[0] if argv else "build"
    if cmd == "build":
        build()
    elif cmd == "check":
        check()
    elif cmd == "query" and len(argv) > 1:
        query(" ".join(argv[1:]))
    elif cmd == "serve":
        serve(int(argv[1]) if len(argv) > 1 else 8000)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
