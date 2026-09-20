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

    sub.add_parser("publish", help="write the out/ JSON tree")
    sub.add_parser("all", help="universe, rank, scan, catalysts, publish")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    from cli import commands
    handler = getattr(commands, f"cmd_{args.command}")
    return int(handler(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
