"""The research ledger: every question this project has tested, kept.

A site that shows only what worked is showing a sample chosen after the fact.
The ledger is the other half: each question that was put to real data, what
was measured, and how it came out, including the ones that came out against
the idea and the ones still waiting on data that does not exist yet.

The source of truth is `research/ledger.yaml`, in the repository, so adding a
study is adding an entry and reviewing one is reading a diff. Publish checks
it and copies it into the tree; the site renders what it is given.

An entry may say only what the repository records. `source` names where:
a section of DECISIONS.md, a module whose comments carry the measurement, a
commit. Nothing is entered from memory or from anybody else's website.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re

import yaml

PATH = pathlib.Path(__file__).resolve().parent.parent / "research" / "ledger.yaml"

#: The only verdicts there are, with what each means on the page.
VERDICTS = {
    "held": "The idea was tested and stood.",
    "refuted": "The idea was tested and the evidence went against it.",
    "refused": "It would work, or was not shown to, and it is not being done.",
    "adopted": "Measured, and the site now runs on the result.",
    "open": "Not answered yet. The entry says what it is waiting for.",
}

REQUIRED = ("id", "date", "question", "measured", "result", "verdict", "source")
_ID = re.compile(r"^R\d{2,3}$")


class LedgerError(ValueError):
    """The ledger file does not say what a ledger entry must say."""


def validate(entries) -> list[dict]:
    """The entries, checked, newest first. Raises LedgerError naming the
    first thing wrong, so a bad entry stops a publish and not a reader."""
    if not isinstance(entries, list) or not entries:
        raise LedgerError("the ledger has no entries")
    seen: set[str] = set()
    out = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise LedgerError(f"entry {index} is not a mapping")
        name = str(entry.get("id") or f"entry {index}")
        for field in REQUIRED:
            if entry.get(field) in (None, "", []):
                raise LedgerError(f"{name}: no {field}")
        if not _ID.match(name):
            raise LedgerError(f"{name}: an id is R and two or three digits")
        if name in seen:
            raise LedgerError(f"{name}: used twice")
        seen.add(name)
        if entry["verdict"] not in VERDICTS:
            raise LedgerError(f"{name}: verdict {entry['verdict']!r} is not one of "
                              f"{', '.join(VERDICTS)}")
        try:
            day = (entry["date"] if isinstance(entry["date"], dt.date)
                   else dt.date.fromisoformat(str(entry["date"])))
        except ValueError as exc:
            raise LedgerError(f"{name}: date {entry['date']!r} is not a date") from exc
        sources = entry["source"] if isinstance(entry["source"], list) else [entry["source"]]
        if entry["verdict"] == "open" and not entry.get("waiting_for"):
            raise LedgerError(f"{name}: an open question says what it is waiting for")
        out.append({
            "id": name, "date": day.isoformat(),
            "question": " ".join(str(entry["question"]).split()),
            "measured": " ".join(str(entry["measured"]).split()),
            "result": " ".join(str(entry["result"]).split()),
            "verdict": entry["verdict"],
            "source": [str(s) for s in sources],
            "waiting_for": (" ".join(str(entry["waiting_for"]).split())
                            if entry.get("waiting_for") else None),
        })
    out.sort(key=lambda e: (e["date"], e["id"]), reverse=True)
    return out


def load(path: pathlib.Path | None = None) -> dict:
    """The ledger as the site reads it."""
    raw = yaml.safe_load((path or PATH).read_text()) or {}
    entries = validate(raw.get("entries"))
    return {
        "verdicts": VERDICTS,
        "counts": {verdict: sum(1 for e in entries if e["verdict"] == verdict)
                   for verdict in VERDICTS},
        "note": " ".join(str(raw.get("note") or "").split()),
        "entries": entries,
    }
