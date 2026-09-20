"""Prove the paywall withholds, against the live database.

Runs in CI. It asks for gated content the way an outsider would — with no
token, with a nonsense token, and with the public anon key — and fails the
build if any of them comes back with content.

This exists because the gate that was already on this site turned out to ship
the data it was hiding: the page said "account needed" and the numbers it was
withholding were in the same HTML. That fault was invisible for weeks and was
found by measuring rather than by reading the code, so the measurement is the
thing worth keeping.

Needs NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY. Both are
public by design — the anon key identifies the project, not a person, and the
whole point of this check is that holding it grants nothing.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = 20
TABLE = "gated_content"
SUBSCRIPTIONS = "subscriptions"


def _request(url: str, key: str, token: str | None) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={
        "apikey": key,
        "Authorization": f"Bearer {token or key}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def main() -> int:
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    anon = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or ""
    if not url or not anon:
        print("Supabase is not configured for this build; skipping the check.")
        print("That is not a pass. Set both variables to have it mean anything.")
        return 0

    rest = f"{url}/rest/v1"
    failures: list[str] = []

    def check(label: str, path: str, token: str | None) -> None:
        status, body = _request(f"{rest}/{path}", anon, token)
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        rows = parsed if isinstance(parsed, list) else []
        leaked = bool(rows)
        print(f"  {label:<44} HTTP {status}  rows {len(rows)}"
              f"{'   *** LEAK ***' if leaked else ''}")
        if leaked:
            failures.append(f"{label}: returned {len(rows)} row(s)")

    print("Gated content, asked for by people who should not get it")
    print("-" * 66)
    check("anon key alone", f"{TABLE}?select=path", None)
    check("anon key, one named path", f"{TABLE}?select=payload&path=eq.market/gamma.json", None)
    check("a nonsense bearer token", f"{TABLE}?select=path", "not-a-real-token")

    print()
    print("Subscriptions, which nobody should be able to read or forge")
    print("-" * 66)
    check("anon key reading subscriptions", f"{SUBSCRIPTIONS}?select=user_id", None)

    print()
    if failures:
        print("FAILED — the paywall is not withholding:")
        for line in failures:
            print(f"  {line}")
        return 1
    print("PASSED — every unentitled request came back empty.")
    print()
    print("Note what this does and does not prove. It proves an outsider gets")
    print("nothing. It cannot prove a subscriber gets something, because that")
    print("needs a real signed-in session, and a check that only ever asserts")
    print("emptiness would still pass if the table were simply missing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
