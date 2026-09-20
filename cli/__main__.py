from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description="US equities base & breakout pipeline.")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_uni = sub.add_parser("universe", help="build the tradable universe")
    p_uni.add_argument("--refresh", action="store_true",
                       help="re-pull reference data and backfill bars first")
    p_uni.add_argument("--reset", action="store_true",
                       help="clear every bar and cursor first — needed when "
                            "switching data.provider")

    sub.add_parser("rank", help="relative strength, groups, breadth, rotation")
    sub.add_parser("scan", help="run the four detectors over the universe")
    sub.add_parser("catalysts", help="dated events and implied volatility")

    p_bt = sub.add_parser("backtest", help="replay a screen's rules over history")
    p_bt.add_argument("--screen", default=None)
    p_bt.add_argument("--enter", default=None, choices=["breakout_close", "at_pivot"])
    p_bt.add_argument("--positions", type=int, default=None)
    p_bt.add_argument("--stop", type=float, default=None, help="cut a loser at N percent")
    p_bt.add_argument("--exit-rule", default=None,
                      choices=["trail_50d", "trail_30w", "take_25"])
    p_bt.add_argument("--risk", type=float, default=None, help="risk per trade, percent")
    p_bt.add_argument("--capital", type=float, default=None)
    p_bt.add_argument("--period", default=None, help="all, or a year like 2025")
    p_bt.add_argument("--json", dest="as_json", action="store_true",
                      help="print the summary as JSON and save it as a preset")
    p_bt.add_argument("--skip-weak-markets", dest="skip_weak", action="store_true", default=None)
    p_bt.add_argument("--no-skip-weak-markets", dest="skip_weak", action="store_false")
    p_bt.add_argument("--skip-earnings", dest="skip_earnings", action="store_true", default=None)
    p_bt.add_argument("--no-skip-earnings", dest="skip_earnings", action="store_false")

    p_q = sub.add_parser("quotes",
                         help="delayed intraday prices for the names on a screen")
    p_q.add_argument("--out", help="where to write the file "
                                   "(default: the out/ tree's quotes.json)")
    sub.add_parser("publish", help="write the out/ JSON tree")
    sub.add_parser("gated", help="upload the staged gated/ documents to Supabase")
    sub.add_parser("all", help="universe, rank, scan, catalysts, backtests, publish")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    from cli import commands
    handler = getattr(commands, f"cmd_{args.command}")
    return int(handler(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
