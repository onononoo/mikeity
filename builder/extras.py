"""
steps written in other languages. python compiles and runs each one if its
compiler or runtime is installed, then reads back what it printed so the
pages can show it. a step whose tool is missing is skipped and the pages
leave that part out; a step that is there but fails stops the build.

    tools/chart.cpp          c++    svg charts of when events happened
    tools/gaps.awk           awk    the quietest stretches and busiest years
    tools/contemporaries.cs  c#     which people were alive at the same time

all three read the files that exports.py has already written into site/data/.
"""

import os
import shutil
import subprocess
import time

from .loader import record


class extras_error(Exception):
    pass


def _exe(path):
    return path + ".exe" if os.name == "nt" else path


def _find(*names):
    """the first of these programs on the path. git for windows keeps awk out of
    the path in powershell and cmd, so look in its usr/bin folder too."""
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", ""), os.environ.get("LOCALAPPDATA", "") + r"\Programs"):
            for n in names:
                path = os.path.join(base, "Git", "usr", "bin", n + ".exe")
                if os.path.exists(path):
                    return path
    return None


def _run(cmd, what, timeout=600, env=None):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise extras_error(f"{what} took longer than {timeout} seconds") from None
    out = p.stdout.decode("utf-8", "replace")
    if p.returncode != 0:
        err = (p.stderr.decode("utf-8", "replace") + out).strip()
        raise extras_error(f"{what} failed (exit {p.returncode}):\n{err[-3000:]}")
    return out


def _rows(text, kind):
    """the tab separated lines that start with this kind, without the kind."""
    return [line.split("\t")[1:] for line in text.splitlines() if line.startswith(kind + "\t")]


# ---------------------------------------------------------------- c++

def chart(root, out):
    gxx = _find("g++", "clang++", "c++")
    if not gxx:
        return None, "no c++ compiler (g++ or clang++)"
    src = os.path.join(root, "tools", "chart.cpp")
    exe = _exe(os.path.join(root, "tools", "bin", "chart"))
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        # on windows, link the c++ runtime in, or the exe may pick up some other
        # program's libstdc++ dll from the path and refuse to start
        static = ["-static"] if os.name == "nt" else []
        _run([gxx, "-std=c++17", "-O2", "-Wall", "-Wextra", *static, "-o", exe, src],
             "compiling tools/chart.cpp")
    text = _run([exe, os.path.join(out, "data", "events.tsv"), os.path.join(out, "images")],
                "tools/chart.cpp")
    return parse_charts(text), None


def parse_charts(text):
    charts = []
    for line in text.splitlines():
        name, width, height, about = line.split("\t")
        charts.append(record(src=f"images/{name}", width=int(width), height=int(height), alt=about))
    return charts


# ---------------------------------------------------------------- awk

def gaps(root, out):
    awk = _find("awk", "gawk", "mawk")
    if not awk:
        return None, "no awk"
    text = _run([awk, "-f", os.path.join(root, "tools", "gaps.awk"),
                 os.path.join(out, "data", "events.tsv")], "tools/gaps.awk")
    return parse_gaps(text), None


def parse_gaps(text):
    quiet = [record(years=int(float(y)), before_date=d1, before=t1, after_date=d2, after=t2)
             for y, d1, t1, d2, t2 in _rows(text, "gap")]
    busy = [record(year=int(float(y)), events=int(n), date=d, what=w.split(" / "))
            for y, n, d, w in _rows(text, "year")]
    busy.sort(key=lambda b: (-b.events, b.year))
    return record(quiet=quiet, busy=busy[:12])


# ---------------------------------------------------------------- c#

def contemporaries(root, out, s):
    dotnet = _find("dotnet")
    if not dotnet:
        return None, "no dotnet"
    env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
    try:
        sdks = _run([dotnet, "--list-sdks"], "dotnet --list-sdks", env=env)
    except extras_error:
        sdks = ""
    if not any(line.split(".")[0].isdigit() and int(line.split(".")[0]) >= 10 for line in sdks.splitlines()):
        return None, "needs the .net 10 sdk"
    text = _run([dotnet, "run", os.path.join(root, "tools", "contemporaries.cs"), "--",
                 os.path.join(out, "data", "history.json")], "tools/contemporaries.cs", env=env)
    return parse_contemporaries(text, s.person_by_slug), None


def parse_contemporaries(text, people):
    """-> {slug: record(count, alongside=[record(person, years)])}"""
    found = {}
    for slug, n in _rows(text, "count"):
        found[slug] = record(count=int(n), alongside=[])
    for slug, other, years in _rows(text, "with"):
        if slug in found and other in people:
            found[slug].alongside.append(record(person=people[other], years=int(years)))
    return found


# ---------------------------------------------------------------- all of them

steps = [
    ("charts", "c++", "tools/chart.cpp", lambda root, out, s: chart(root, out)),
    ("gaps", "awk", "tools/gaps.awk", lambda root, out, s: gaps(root, out)),
    ("contemporaries", "c#", "tools/contemporaries.cs", contemporaries),
]


def run_all(root, out, s, say=print):
    """run every step. returns a record with one field per step (none if it was
    skipped) and a 'log' list saying what happened to each."""
    result = record(log=[])
    for name, language, source, fn in steps:
        started = time.perf_counter()
        value, skipped = fn(root, out, s)
        seconds = time.perf_counter() - started
        result[name] = value
        status = f"skipped: {skipped}" if skipped else "ran"
        result.log.append(record(name=name, language=language, source=source, status=status,
                                 ran=not skipped))
        say(f"{language} ({source}): {status}" + ("" if skipped else f" in {seconds:.1f}s"))
    return result
