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

Analyst estimates. The buy/hold/sell split is free and no price target is,
not even the consensus — so a public forecast may carry ratings and the current
price and nothing else.

Screens. Each stage shows a sample; fresh breakouts are whole. And the
aggregate files must not hand back what the lists withheld: the search index
and the industry and theme pages cover the entire universe, so screen
membership on a name outside the free sample is that name's row given back in
a different file.

One path is left open knowingly. A stock's own page still carries its own
setup, so fetching all five hundred of them rebuilds the lists. Closing it
means emptying the free stock pages, which is a worse trade than the one it
protects against.

The X-ray. The most recent base is free, labelled as one of however many
there are. This is the gate that was decorative for months: the page said
"account needed" while every base sat in the same public file underneath it.

Backtests. The result is free and the trade list and yearly breakdown are not,
so no preset may still carry those keys.

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

from publish.gated import (BACKTEST_GATED_KEYS, FREE_GAMMA_ROWS,  # noqa: E402
                           FREE_SCREEN_ROWS, FREE_SCREEN_WHOLE_STAGES,
                           FREE_SEASONAL_SYMBOL, FREE_XRAY_BASES)


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

    screen_paths = [p for p in sorted((out / "screens").glob("*.json"))
                    if p.name != "diff.json"]
    on_screen_free: set[str] = set()
    oversized: list[str] = []
    for path in screen_paths:
        payload = _load(path)
        if "__unreadable__" in payload:
            failures.append(f"{path.name} could not be read: {payload['__unreadable__']}")
            continue
        for stage, rows in (payload.get("setups") or {}).items():
            on_screen_free.update(row["symbol"] for row in rows)
            if stage in FREE_SCREEN_WHOLE_STAGES:
                continue
            if len(rows) > FREE_SCREEN_ROWS:
                oversized.append(f"{path.stem}/{stage} ({len(rows)})")
    print(f"  screens/            {len(screen_paths)} screen(s)   "
          f"{len(on_screen_free)} name(s) visible free")
    if oversized:
        failures.append(
            f"{len(oversized)} screen stage(s) publish more than the free "
            f"sample of {FREE_SCREEN_ROWS}: {', '.join(oversized)}.")

    # The aggregates, cross-checked against what the screens actually showed.
    # This is the pair that matters: a screen page can be trimmed perfectly and
    # the index next to it still hand back every name it trimmed.
    index = _load(out / "search.json") if (out / "search.json").exists() else {}
    search_leaked = [row.get("symbol") for row in (index.get("rows") or [])
                     if row.get("on_screen") and row.get("symbol") not in on_screen_free]
    if search_leaked:
        failures.append(
            f"{len(search_leaked)} row(s) in search.json carry screen "
            f"membership for names the screen pages withheld "
            f"({', '.join(str(s) for s in sorted(search_leaked)[:8])}…).")

    group_leaked: list[str] = []
    for folder in ("industries", "themes"):
        for path in sorted((out / folder).glob("*.json")):
            payload = _load(path)
            for member in (payload.get("members_detail") or []):
                if (member.get("screens") or member.get("stage")) \
                        and member.get("symbol") not in on_screen_free:
                    group_leaked.append(f"{folder}/{path.stem}:{member.get('symbol')}")
    if group_leaked:
        failures.append(
            f"{len(group_leaked)} member row(s) on industry or theme pages "
            f"carry a screen or stage for names the screen pages withheld "
            f"({', '.join(group_leaked[:6])}…).")

    stocks = sorted((out / "stocks").glob("*.json"))
    leaked: list[str] = []
    forecast_leaked: list[str] = []
    xray_leaked: list[str] = []
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
        forecast = payload.get("forecast") or {}
        targets = forecast.get("targets") or {}
        if (any(targets.get(k) is not None for k in ("low", "mean", "median", "high"))
                or forecast.get("eps") or forecast.get("revenue")
                or forecast.get("upside_pct") is not None):
            forecast_leaked.append(symbol)
        if len(payload.get("base_history") or []) > FREE_XRAY_BASES:
            xray_leaked.append(symbol)

    print(f"  stocks/             {len(stocks)} file(s)   "
          f"{len(free)} public gamma / {marked} gated   "
          f"{forecast_marked} forecast head(s)   {len(xray_leaked)} oversized x-ray")

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
    leak(forecast_leaked, "analyst price targets or estimates",
         "The free half is the ratings split and the current price. No target "
         "appears in it, not even the consensus.")
    leak(xray_leaked, f"more than {FREE_XRAY_BASES} base(s) of history",
         "This is the field that made the old account gate decorative for "
         "months.")

    presets = sorted((out / "backtest" / "presets").glob("*.json"))
    preset_leaked: list[str] = []
    for path in presets:
        if path.name == "index.json":
            continue
        payload = _load(path)
        if "__unreadable__" in payload:
            failures.append(f"{path.name} could not be read: {payload['__unreadable__']}")
            continue
        present = [key for key in BACKTEST_GATED_KEYS if payload.get(key)]
        if present:
            preset_leaked.append(f"{path.stem} ({', '.join(present)})")
    print(f"  backtest/presets/   {max(len(presets) - 1, 0)} preset(s)   "
          f"{len(preset_leaked)} carrying gated keys")
    if preset_leaked:
        failures.append(
            f"{len(preset_leaked)} backtest preset(s) still publish "
            f"{' and '.join(BACKTEST_GATED_KEYS)}: {', '.join(preset_leaked)}.")

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
