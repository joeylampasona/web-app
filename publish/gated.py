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
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

# How many option books stay free. Five is enough to show what the reading is
# and what the page does with it, and short enough that the ranking itself —
# which is most of the value — is not given away.
FREE_GAMMA_ROWS = 5

# Seasonals: the benchmark's grid is free, the sector grids are not. The
# benchmark is the one everybody has already seen somewhere else, so it
# demonstrates the format without being the reading — the sector-by-sector
# comparison is what the page is for.
FREE_SEASONAL_SYMBOL = "SPY"

# How many names a screen shows for free, per stage — so no single tab ever
# runs past ten charts. It used to leave fresh breakouts untrimmed, which meant
# one screen published fifty-two charts on a tab; the daily feed in breakouts/
# still carries every one of them, so nothing is lost by capping the tab.
FREE_SCREEN_ROWS = 10

# Stages a free reader sees none of.
#
# Forming is the proposition. It is the list of bases before they break, which
# is the only stage where knowing early is worth anything — the other three
# describe something that has already happened. Ten of those is a fair sample
# of what the site does; ten of these would be giving away the thing itself.
FREE_SCREEN_LOCKED_STAGES = ("forming",)

# How many previous bases the X-ray shows for free. One, labelled as one of
# however many there are — a reader told "the most recent of six" is not being
# misled about the comparison, only shown less of it.
FREE_XRAY_BASES = 1

# What a company's analyst panel shows for free: the buy/hold/sell split and
# the current price, which is public everywhere else on the site anyway. Not a
# price target. This panel's own argument is that a consensus without its
# spread is a worse number than no consensus, so the free half deliberately
# contains no target at all rather than the middle one.
FORECAST_FREE_KEYS = ("symbol", "ratings")

# Analyst estimates have no free sample, and deliberately so. There is no
# ranking here to show the top of — a forecast is a per-company fact, and any
# "sample" would just be an arbitrary list of companies whose page happens to
# be more useful than the next one's. The site samples generously elsewhere;
# this one is whole or not at all.

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
                    free: set[str], as_of: dt.date,
                    total: int | None = None) -> list[Document]:
    """Everything about gamma that a non-subscriber does not get.

    The whole board, including the free rows — a subscriber asks for one
    document and renders the page from it, rather than stitching a public head
    onto a private tail and hoping the two were built from the same run.

    `count` is every name that returned usable open interest, the same thing it
    means in the public file. It was the length of the board here, so the page
    read "129 names carried usable open interest" for a free reader and "60"
    for a subscriber — the same sentence, quietly meaning something else
    depending on who was looking.
    """
    documents = [Document("market/gamma.json",
                          {"as_of": as_of.isoformat(),
                           "count": len(board_rows) if total is None else total,
                           "board_rows": len(board_rows),
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


def seasonal_documents(symbols: list[dict], as_of: dt.date) -> list[Document]:
    """The whole grid, benchmark included, as one document."""
    if not symbols:
        return []
    return [Document("market/seasonals.json",
                     {"as_of": as_of.isoformat(), "symbols": symbols}, as_of)]


def free_seasonals(symbols: list[dict]) -> list[dict]:
    """The grids that stay public: the benchmark, or the first if it is absent."""
    if not symbols:
        return []
    for row in symbols:
        if row.get("symbol") == FREE_SEASONAL_SYMBOL:
            return [row]
    return symbols[:1]


def forecast_documents(forecasts: dict[str, dict] | None,
                       as_of: dt.date) -> list[Document]:
    """One document per company with estimates."""
    return [Document(f"stocks/forecast/{symbol.lower()}.json", payload, as_of)
            for symbol, payload in sorted((forecasts or {}).items())
            if payload]


def free_forecast(payload: dict | None) -> dict | None:
    """The part of an analyst panel everyone sees: the ratings split."""
    if not payload:
        return None
    head = {key: payload[key] for key in FORECAST_FREE_KEYS if key in payload}
    if not head.get("ratings"):
        return None
    current = (payload.get("targets") or {}).get("current")
    head["targets"] = {"current": current, "low": None, "mean": None,
                       "median": None, "high": None}
    head["upside_pct"] = None
    head["eps"] = []
    head["revenue"] = []
    head["gated"] = True
    return head


def free_xray(history: list) -> list:
    """The most recent completed base. The rest is the comparison."""
    return list(history or [])[-FREE_XRAY_BASES:]


def split_screen(payload: dict) -> tuple[dict, dict]:
    """(what everyone sees, the whole thing) for one screen.

    Truncates each stage rather than removing it, so the shape of the page is
    the same either way and every stage still says how many names are in it.
    `stage_counts` is untouched on purpose: a paywall that will not say what it
    is withholding is asking to be paid on trust.
    """
    setups = payload.get("setups") or {}
    trimmed = {}
    for stage, rows in setups.items():
        if stage in FREE_SCREEN_LOCKED_STAGES:
            trimmed[stage] = []
        else:
            trimmed[stage] = rows[:FREE_SCREEN_ROWS]
    public = dict(payload)
    public["setups"] = trimmed
    public["gated"] = True
    public["free_rows"] = FREE_SCREEN_ROWS
    public["locked_stages"] = list(FREE_SCREEN_LOCKED_STAGES)
    return public, payload


def screen_documents(screens: dict[str, dict],
                     as_of: dt.date) -> tuple[dict[str, dict], list[Document]]:
    """Public screen files, and the full lists behind them."""
    public: dict[str, dict] = {}
    documents: list[Document] = []
    for key, payload in screens.items():
        head, whole = split_screen(payload)
        public[key] = head
        documents.append(Document(f"screens/{key}.json", whole, as_of))
    return public, documents


def free_symbols_on_screens(screens: dict[str, dict]) -> set[str]:
    """Every symbol a free reader can see on a screen page.

    Used to keep the aggregate files — the search index, the industry and theme
    pages — from handing back the names the screen lists just withheld. Callers
    add the names in the public breakouts feed, which publishes the day's fresh
    breakouts across every screen whether or not a particular screen's tab had
    room for them; without that union the aggregates would withhold a name the
    home page is showing, which is a contradiction rather than a secret.

    It does not close every path: a stock's own page still carries its own
    setup, so somebody willing to fetch all of them can rebuild the lists. That
    is a deliberate trade, written down in the README, because stripping setups
    from stock pages would empty the free site to protect a list that a
    determined scraper gets anyway.
    """
    free: set[str] = set()
    for payload in screens.values():
        head, _ = split_screen(payload)
        for rows in (head.get("setups") or {}).values():
            free.update(row["symbol"] for row in rows)
    return free


def xray_documents(bases: dict[str, list], as_of: dt.date) -> list[Document]:
    """Every base a stock has built, per company.

    The document holds all of them, including the one shown for free, so a
    subscriber renders the chart from one source rather than splicing a public
    base onto a private list.
    """
    return [Document(f"stocks/xray/{symbol.lower()}.json", history, as_of)
            for symbol, history in sorted(bases.items()) if history]


# The parts of a backtest that are the work rather than the claim. The headline
# stays free on purpose: this site's own out-of-sample results are the argument
# that it is honest about itself, and hiding them would be asking to be paid on
# trust by a product whose whole pitch is that it does not ask for that.
BACKTEST_GATED_KEYS = ("trades", "yearly")


def split_backtest(payload: dict) -> tuple[dict, dict | None]:
    """(what everyone sees, what a subscriber sees) for one preset.

    The free half keeps every caveat — provisional, survivorship, the notes —
    because those travel with the number and a version of the result without
    them would be a better-looking lie.
    """
    gated = {key: payload[key] for key in BACKTEST_GATED_KEYS if key in payload}
    if not gated:
        return payload, None
    public = {key: value for key, value in payload.items()
              if key not in BACKTEST_GATED_KEYS}
    public["gated"] = True
    public["gated_counts"] = {key: len(value) if isinstance(value, list) else 1
                              for key, value in gated.items()}
    return public, gated


def backtest_documents(backtests: dict[str, dict] | None,
                       as_of: dt.date) -> tuple[dict[str, dict], list[Document]]:
    """Public presets, and the documents holding what was taken out of them."""
    public: dict[str, dict] = {}
    documents: list[Document] = []
    for key, payload in (backtests or {}).items():
        head, tail = split_backtest(payload)
        public[key] = head
        if tail is not None:
            documents.append(Document(f"backtest/{key}.json", tail, as_of))
    return public, documents


# --------------------------------------------------------------- staging

def stage(documents: Iterable[Document], directory: pathlib.Path | None = None
          ) -> list[pathlib.Path]:
    """Write documents to disk so a run can be inspected before it is uploaded.

    Emptied first. A name that drops out of the gamma universe leaves its file
    behind otherwise, and the next upload sends it again — a document nothing
    produced any more, carrying whatever date it had when it was last real. CI
    checks out fresh every run and would never have shown this; a local one
    would, eventually and confusingly.
    """
    target = directory or gated_dir()
    shutil.rmtree(target, ignore_errors=True)
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


def fetch(prefix: str) -> dict[str, Any]:
    """Read back gated documents under a path prefix, as the writer.

    For the jobs that need to know what was gated — the intraday sweep has to
    quote the names the public screens no longer list, or a subscriber's own
    rows are the only ones on the page without a live price.
    """
    url = (os.environ.get("SUPABASE_URL")
           or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return {}
    status, body = _call(
        "GET",
        f"{url}/rest/v1/{TABLE}?select=path,payload&path=like.{prefix}*",
        key)
    if status != 200:
        return {}
    try:
        rows = json.loads(body)
    except ValueError:
        return {}
    return {row["path"]: row["payload"] for row in rows
            if isinstance(row, dict) and "path" in row}


def upload(documents: list[Document], as_of: dt.date,
           sweep: bool = True) -> Upload:
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

    if not sweep:
        # For a writer that owns a fixed set of paths and overwrites them in
        # place — the intraday sweep writes one. Letting it sweep would be a
        # quiet disaster: it writes under market/, and the delete is by prefix
        # and date, so a Monday quote run would remove Friday's gamma and
        # seasonals for carrying an older session.
        return report

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
