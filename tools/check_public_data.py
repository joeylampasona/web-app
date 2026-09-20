"""Does the public tree contain anything the paywall claims to be withholding?

Run against a built `out/` tree, before it is pushed to the data branch, and
against the data branch itself. It is the other half of tools/check_paywall.py:
that one asks the database whether an outsider is refused, this one asks whether
the answer matters, because a policy that refuses perfectly protects nothing if
the same numbers are sitting in a public JSON file.

This is not a hypothetical failure. The gate that was already on this site did
exactly that — the page said "account needed" and the numbers it was withholding
were in the same HTML — and it went unnoticed for weeks because everything
looked right from the outside.

What it knows how to check
--------------------------
Gamma. The deepest few option books are free in full and everything below them
is gated, in both places gamma is published: the board, and each stock page. So
the public board must carry no more than the free sample, and no stock file may
carry a gamma payload for a name outside it. The second is the one worth
having: gating a ranking while publishing every row of it gives the ranking
away to anyone willing to fetch a few hundred files.

Seasonals. The benchmark's grid is free, the sector grids are not.

Analyst estimates. No free sample at all, so no stock file may carry one.

Every rule here is the same shape: something is supposed to be absent from a
public file, and this opens the file and looks. A gate that is only enforced in
a component is a gate on the interface, not on the data — which is what the
X-ray still is, and what the old account gate was for weeks.

Usage: python tools/check_public_data.py [out-directory]
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from publish.gated import FREE_GAMMA_ROWS, FREE_SEASONAL_SYMBOL  # noqa: E402


def _load(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        return {"__unreadable__": str(problem)}


def check(out: pathlib.Path) -> list[str]:
    failures: list[str] = []

    board_path = out / "market" / "gamma.json"
    if not board_path.exists():
        # Not a failure. A tree built before gamma existed, or a run where no
        # chain returned usable open interest, has no board and nothing to leak.
        print("  market/gamma.json is absent — nothing published, nothing to leak.")
        free: set[str] = set()
    else:
        board = _load(board_path)
        if "__unreadable__" in board:
            failures.append(f"market/gamma.json could not be read: {board['__unreadable__']}")
            return failures
        rows = board.get("rows") or []
        free = {row.get("symbol") for row in rows}
        total = board.get("count", len(rows))
        print(f"  market/gamma.json   {len(rows)} public row(s) of {total}"
              f"   gated={board.get('gated')}")
        if len(rows) > FREE_GAMMA_ROWS:
            failures.append(
                f"the public gamma board carries {len(rows)} rows; the free "
                f"sample is {FREE_GAMMA_ROWS}. The rest belongs in gated_content.")
        if not board.get("gated"):
            failures.append(
                "market/gamma.json is not marked gated, so the page will render "
                "its rows as the whole board and never offer the rest.")
        if any(row.get("levels") is None for row in rows):
            failures.append(
                "a public gamma row has no levels. The free sample is supposed "
                "to be complete rows — a truncated one shows the format and "
                "not the work.")

    seasonal_path = out / "market" / "seasonals.json"
    if seasonal_path.exists():
        seasonals = _load(seasonal_path)
        symbols = [row.get("symbol") for row in (seasonals.get("symbols") or [])]
        total = seasonals.get("count", len(symbols))
        print(f"  market/seasonals.json   {len(symbols)} public grid(s) of {total}"
              f"   gated={seasonals.get('gated')}")
        extra = [s for s in symbols if s != FREE_SEASONAL_SYMBOL]
        if extra:
            failures.append(
                f"the public seasonals file carries grids for "
                f"{', '.join(str(s) for s in extra)}. Only "
                f"{FREE_SEASONAL_SYMBOL} is free.")

    stocks = sorted((out / "stocks").glob("*.json"))
    leaked: list[str] = []
    forecast_leaked: list[str] = []
    marked = 0
    forecast_marked = 0
    for path in stocks:
        payload = _load(path)
        if "__unreadable__" in payload:
            failures.append(f"{path.name} could not be read: {payload['__unreadable__']}")
            continue
        symbol = payload.get("symbol") or path.stem
        if payload.get("gamma_gated"):
            marked += 1
        if payload.get("gamma") and symbol not in free:
            leaked.append(symbol)
        if payload.get("forecast_gated"):
            forecast_marked += 1
        if payload.get("forecast"):
            forecast_leaked.append(symbol)

    print(f"  stocks/             {len(stocks)} file(s)   "
          f"{len(free)} public gamma / {marked} gated   "
          f"{len(forecast_leaked)} public forecast / {forecast_marked} gated")

    def leak(names: list[str], what: str, why: str) -> None:
        if not names:
            return
        shown = ", ".join(sorted(names)[:12])
        more = f" and {len(names) - 12} more" if len(names) > 12 else ""
        failures.append(f"{len(names)} stock file(s) publish {what} "
                        f"({shown}{more}). {why}")

    leak(leaked, "gamma for names outside the free sample",
         "The board is gated and its rows are not, which gives the board away "
         "to anyone who fetches the files.")
    leak(forecast_leaked, "analyst estimates",
         "Estimates have no free sample; the whole panel is gated.")

    # The staging directory is not part of the tree, and a tree that contains
    # it has had the gated content copied into the thing that gets pushed.
    strays = [p for p in out.rglob("*") if p.is_dir() and p.name == "gated"]
    if strays:
        failures.append(
            f"a directory named 'gated' is inside the published tree: "
            f"{', '.join(str(p) for p in strays)}. That tree is force-pushed to "
            f"a public branch whole.")

    return failures


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    if not out.exists():
        print(f"No tree at {out}. Build one with `python -m cli publish` first.")
        return 1

    print(f"What the public tree at {out} actually contains")
    print("-" * 72)
    failures = check(out)
    print()
    if failures:
        print("FAILED — the public tree carries content the paywall withholds:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("PASSED — nothing gated appears in the tree that gets published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
