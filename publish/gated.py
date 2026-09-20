"""What goes behind the paywall, and how it gets there.

Two jobs, kept in one file because they have to agree: deciding which part of
a night's work is free, and putting the rest somewhere the data branch is not.

The rule
--------
For gamma, the free part is the few deepest option books — whole rows, levels
and all — and everything below them is gated. One rule, applied in both places
gamma appears: the board and the individual stock pages.

That last clause is the load-bearing one. An earlier sketch gated the board and
left per-stock gamma public, which reads as a paywall and is not one: the board
is a ranking of the stock pages, so anyone willing to fetch a few hundred files
could rebuild it exactly. Gating the view while publishing its ingredients is
the same fault this site already shipped once, when a page said "account
needed" and the withheld numbers were in the same HTML.

Showing the top few in full rather than showing all of them partially is a
choice about what a sample should be. A truncated row demonstrates the format;
a complete row demonstrates the work. The thing being sold here is the reading,
so the sample has to contain one.

Where it goes
-------------
Never into `out/`. That whole directory is force-pushed to the `data` branch of
a public repository every night, so anything written there is published to the
world no matter what the website does with it afterwards. Gated documents are
written to a sibling directory and uploaded to Postgres, where a policy decides
who may read them.

The upload uses the service-role key, which ignores row-level security. That is
correct here and nowhere else: this is the writer, and there is no insert policy
for anyone else to use. The key lives in the workflow environment; it must never
reach `out/`, a log line, or the browser.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

# How many option books stay free. Five is enough to show what the reading is
# and what the page does with it, and short enough that the ranking itself —
# which is most of the value — is not given away.
FREE_GAMMA_ROWS = 5

TABLE = "gated_content"
TIMEOUT = 60
# PostgREST takes an array and upserts it in one statement. Chunked anyway, so
# a night with an unusually deep option universe cannot produce a request body
# large enough to be refused.
CHUNK = 200


@dataclass(frozen=True)
class Document:
    """One row of `gated_content`: a path, a payload, and the session it is of."""
    path: str
    payload: Any
    as_of: dt.date

    def row(self) -> dict:
        return {"path": self.path, "payload": self.payload,
                "as_of": self.as_of.isoformat()}


def gated_dir() -> pathlib.Path:
    """Where gated documents are staged. Deliberately not under `out/`."""
    root = pathlib.Path(__file__).resolve().parent.parent
    return pathlib.Path(os.environ.get("GATED_DIR") or (root / "gated"))


# --------------------------------------------------------------- the split

def free_symbols(gamma: dict[str, dict] | None) -> set[str]:
    """The names whose gamma stays public: the deepest books by open interest.

    Ties break on the symbol so two runs over the same data produce the same
    free set. Without that a name could drift in and out of the free tier from
    one night to the next for no reason a reader could see.
    """
    usable = [(symbol, payload) for symbol, payload in (gamma or {}).items()
              if payload and payload.get("levels")]
    usable.sort(key=lambda pair: (-(pair[1].get("open_interest") or 0), pair[0]))
    return {symbol for symbol, _ in usable[:FREE_GAMMA_ROWS]}


def gamma_documents(board_rows: list[dict], gamma: dict[str, dict] | None,
                    free: set[str], as_of: dt.date) -> list[Document]:
    """Everything about gamma that a non-subscriber does not get.

    The whole board, including the free rows — a subscriber asks for one
    document and renders the page from it, rather than stitching a public head
    onto a private tail and hoping the two were built from the same run.
    """
    documents = [Document("market/gamma.json",
                          {"as_of": as_of.isoformat(),
                           "count": len(board_rows),
                           "rows": board_rows},
                          as_of)]
    for symbol, payload in sorted((gamma or {}).items()):
        if symbol in free or not payload or not payload.get("levels"):
            continue
        # Lower-cased because the path is matched against a strict shape in the
        # route that serves it, and that shape does not admit capitals.
        documents.append(Document(f"stocks/gamma/{symbol.lower()}.json",
                                  payload, as_of))
    return documents


# --------------------------------------------------------------- staging

def stage(documents: Iterable[Document], directory: pathlib.Path | None = None
          ) -> list[pathlib.Path]:
    """Write documents to disk so a run can be inspected before it is uploaded."""
    target = directory or gated_dir()
    written = []
    for document in documents:
        path = target / document.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document.row(), separators=(",", ":"),
                                   default=str), encoding="utf-8")
        written.append(path)
    return written


def load(directory: pathlib.Path | None = None) -> list[Document]:
    """Read back what `stage` wrote."""
    target = directory or gated_dir()
    documents = []
    for path in sorted(target.rglob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        documents.append(Document(row["path"], row["payload"],
                                  dt.date.fromisoformat(row["as_of"])))
    return documents


# --------------------------------------------------------------- upload

def _call(method: str, url: str, key: str, body: Any = None,
          prefer: str | None = None) -> tuple[int, str]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    payload = json.dumps(body, default=str).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


@dataclass
class Upload:
    configured: bool = False
    written: int = 0
    removed: int = 0
    problems: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.problems is None:
            self.problems = []

    @property
    def ok(self) -> bool:
        return not self.problems

    def render(self) -> str:
        if not self.configured:
            return ("Gated content was not uploaded: SUPABASE_URL and "
                    "SUPABASE_SERVICE_ROLE_KEY are unset. The site will show "
                    "the free sample to everyone, including subscribers.")
        lines = [f"Gated content: {self.written} document(s) written, "
                 f"{self.removed} stale row(s) removed."]
        lines += [f"  problem: {line}" for line in self.problems]
        return "\n".join(lines)


def upload(documents: list[Document], as_of: dt.date) -> Upload:
    """Upsert tonight's documents and delete anything left over from before.

    The delete is not housekeeping. Without it a name that drops out of the
    gamma universe keeps its last good row for ever, and a subscriber is served
    a reading from a session that may be months old with nothing on the page
    saying so. Everything this writer owns carries tonight's date, so anything
    older under the same prefixes is by definition no longer produced.
    """
    url = (os.environ.get("SUPABASE_URL")
           or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return Upload(configured=False)

    report = Upload(configured=True)
    rest = f"{url}/rest/v1/{TABLE}"

    # Stamped at upload rather than at stage, so the column says when the row
    # was last actually written. An upsert does not refresh a default, so
    # without this a document re-uploaded every night for a month would still
    # claim to have been written on the first of them.
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    for start in range(0, len(documents), CHUNK):
        batch = [dict(document.row(), updated_at=now)
                 for document in documents[start:start + CHUNK]]
        status, body = _call("POST", f"{rest}?on_conflict=path", key, batch,
                             prefer="resolution=merge-duplicates,return=minimal")
        if status in (200, 201, 204):
            report.written += len(batch)
        else:
            report.problems.append(
                f"writing {len(batch)} document(s) starting at "
                f"{batch[0]['path']}: HTTP {status} {body[:200]}")

    # Not after a failed write. The sweep deletes what tonight's upload was
    # supposed to replace, so running it when some of that upload did not land
    # turns "a subscriber sees last night's numbers" into "a subscriber sees
    # nothing" — strictly worse, and for no gain, since a stale row is at least
    # dated.
    if report.problems:
        report.problems.append(
            "stale rows were left in place, because tonight's write did not "
            "fully land and deleting them would leave subscribers with nothing")
        return report

    # Only sweep prefixes this run actually produced. A night where gamma fails
    # to stage at all should leave last night's gamma alone rather than
    # deleting it and emptying the page.
    prefixes = sorted({document.path.split("/")[0] for document in documents})
    for prefix in prefixes:
        status, body = _call(
            "DELETE",
            f"{rest}?path=like.{prefix}/*&as_of=lt.{as_of.isoformat()}",
            key, prefer="return=representation")
        if status in (200, 204):
            try:
                report.removed += len(json.loads(body or "[]"))
            except ValueError:
                pass
        else:
            report.problems.append(
                f"sweeping stale {prefix}/ rows: HTTP {status} {body[:200]}")

    return report
