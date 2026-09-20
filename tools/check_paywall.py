"""Prove the paywall withholds from outsiders and grants to subscribers.

Runs in CI. It asks the live database the same questions from both sides:

  1. An outsider asks for gated content — no token, a nonsense token, the
     public anon key. Any content coming back is a leak.
  2. A subscriber asks for the same path. Nothing coming back is a broken
     paywall, and until this half existed the check could not tell the two
     apart.
  3. That subscriber tries to write — to grant themselves more, or to edit the
     content. Either succeeding is worse than a leak.

This exists because the gate that was already on this site turned out to ship
the data it was hiding: the page said "account needed" and the numbers it was
withholding were in the same HTML. That fault was invisible for weeks and was
found by measuring rather than by reading the code, so the measurement is the
thing worth keeping — including the measurement of the check itself, which is
what part 2 is. A check that only ever asserts emptiness passes just as
happily when the table has been dropped.

Configuration
-------------
NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
    Both public by design — the anon key identifies the project, not a person,
    and the whole point of part 1 is that holding it grants nothing.

PAYWALL_TEST_EMAIL, PAYWALL_TEST_PASSWORD
    A test account that supabase/paywall_selftest.sql has given a permanent
    subscription. Parts 2 and 3 need it; without it they are skipped and the
    run says so. The password is a secret, and worth treating as one: it buys
    exactly what a paying subscriber gets and nothing more, but that is not
    nothing.

No service-role key appears anywhere in this file. If one ever does, part 1
stops meaning anything, because that key ignores every policy it is testing.
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

# The row supabase/paywall_selftest.sql seeds. It exists so that "no rows" is
# a decision rather than an absence.
SENTINEL = "selftest/entitlement.json"
# A row that must never come to exist. Part 3 tries to create it.
INTRUSION = "selftest/intrusion.json"
# A status the tamper attempt tries to write. Anything but this means the
# update was refused, which is the point.
TAMPER = "selftest-tamper"


def _call(
    method: str,
    url: str,
    key: str,
    token: str | None,
    body: dict | None = None,
    prefer: str | None = None,
) -> tuple[int, str]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {token or key}",
        "Accept": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


def _rows(body: str) -> list:
    """Rows from a PostgREST answer; an empty list for anything else.

    An error body is not rows, and neither is a single object — both are
    treated as "nothing came back", which is the safe direction for part 1 and
    the failing direction for part 2.
    """
    try:
        parsed = json.loads(body)
    except ValueError:
        return []
    return parsed if isinstance(parsed, list) else []


class Report:
    """Failures collected across all three parts, so one run shows all of them."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def line(self, label: str, status: int, count: int, bad: bool, note: str = "") -> None:
        mark = f"   *** {note or 'WRONG'} ***" if bad else ""
        print(f"  {label:<46} HTTP {status:<4} rows {count}{mark}")

    def fail(self, message: str) -> None:
        self.failures.append(message)


# A refusal has a shape. A select that row-level security denies comes back
# 200 with an empty array; a token the project rejects outright comes back 401
# or 403. Anything else — a transport error, a 404 for a table that is not
# there, a gateway 5xx — is not a refusal, it is a question that never got
# asked, and counting it as a pass is how a check comes to prove nothing. This
# file was briefly guilty of exactly that: with the network down, every request
# returned no rows and part 1 reported success.
REFUSALS = {200, 401, 403}


def withheld(report: Report, rest: str, anon: str) -> None:
    """Part 1 — an outsider gets nothing."""
    print("Asked for by people who should not get it")
    print("-" * 72)

    def check(label: str, path: str, token: str | None) -> None:
        status, body = _call("GET", f"{rest}/{path}", anon, token)
        rows = _rows(body)
        if status not in REFUSALS:
            report.line(label, status, len(rows), True, "NOT ASKED")
            report.fail(
                f"{label}: the project answered {status}"
                f"{' (' + body[:120] + ')' if body else ''}. No rows came back, "
                f"but nothing was refused either — the request did not arrive."
            )
            return
        report.line(label, status, len(rows), bool(rows), "LEAK")
        if rows:
            report.fail(f"{label}: returned {len(rows)} row(s)")

    check("anon key, whole table", f"{TABLE}?select=path", None)
    check("anon key, the sentinel path", f"{TABLE}?select=payload&path=eq.{SENTINEL}", None)
    check("a nonsense bearer token", f"{TABLE}?select=path", "not-a-real-token")
    check("anon key reading subscriptions", f"{SUBSCRIPTIONS}?select=user_id", None)


def sign_in(url: str, anon: str, email: str, password: str) -> tuple[str, str] | None:
    """A real session for the test account: (access token, user id)."""
    status, body = _call(
        "POST",
        f"{url}/auth/v1/token?grant_type=password",
        anon,
        None,
        {"email": email, "password": password},
    )
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = {}
    token = parsed.get("access_token") if isinstance(parsed, dict) else None
    uid = ((parsed.get("user") or {}).get("id")) if isinstance(parsed, dict) else None
    if status != 200 or not token or not uid:
        message = parsed.get("error_description") or parsed.get("msg") or body[:200]
        print(f"  sign-in failed                                 HTTP {status}  {message}")
        return None
    print(f"  signed in as {email}")
    return token, uid


def granted(report: Report, rest: str, anon: str, token: str, uid: str) -> None:
    """Part 2 — a subscriber gets the thing."""
    print()
    print("Asked for by somebody who has paid")
    print("-" * 72)

    status, body = _call(
        "GET", f"{rest}/{TABLE}?select=payload&path=eq.{SENTINEL}", anon, token
    )
    rows = _rows(body)
    missing = len(rows) != 1
    report.line("the sentinel path", status, len(rows), missing, "WITHHELD")
    if missing:
        report.fail(
            f"the sentinel path returned {len(rows)} row(s) to a subscriber. "
            f"Either the policy denies everyone — which would make every check "
            f"above pass for the wrong reason — or supabase/paywall_selftest.sql "
            f"has not been run against this project."
        )

    status, body = _call("GET", f"{rest}/{SUBSCRIPTIONS}?select=status", anon, token)
    rows = _rows(body)
    wrong = len(rows) != 1
    report.line("their own subscription row", status, len(rows), wrong)
    if wrong:
        report.fail(f"a subscriber read {len(rows)} subscription rows, expected 1")

    # The function the policy is written in terms of, asked directly. If this
    # disagrees with the row above, entitlement has two answers.
    status, body = _call("POST", f"{rest}/rpc/is_subscriber", anon, token, {})
    verdict = body.strip().lower()
    bad = verdict != "true"
    print(f"  {'is_subscriber() says':<46} HTTP {status:<4} {verdict}"
          f"{'   *** WRONG ***' if bad else ''}")
    if bad:
        report.fail(f"is_subscriber() answered {verdict!r} for a paid account")


def cannot_write(report: Report, rest: str, anon: str, token: str, uid: str) -> None:
    """Part 3 — that subscriber cannot write, to content or to entitlement.

    Both attempts are verified by reading back rather than by trusting the
    status code. PostgREST reports a row-level-security refusal in more than
    one shape depending on the verb, and "it returned an error" is a weaker
    claim than "the data is unchanged".
    """
    print()
    print("The same subscriber, trying to write")
    print("-" * 72)

    _call(
        "POST", f"{rest}/{TABLE}", anon, token,
        {"path": INTRUSION, "payload": {"note": "should never exist"}},
        prefer="return=minimal",
    )
    status, body = _call(
        "GET", f"{rest}/{TABLE}?select=path&path=eq.{INTRUSION}", anon, token
    )
    rows = _rows(body)
    report.line("insert into gated_content", status, len(rows), bool(rows), "WRITABLE")
    if rows:
        report.fail(
            f"a subscriber inserted {INTRUSION} into {TABLE}. Anyone holding the "
            f"anon key can write the paid content. Remove the insert policy."
        )

    status, before = _call(
        "GET", f"{rest}/{SUBSCRIPTIONS}?select=status&user_id=eq.{uid}", anon, token
    )
    was = (_rows(before) or [{}])[0].get("status")
    _call(
        "PATCH", f"{rest}/{SUBSCRIPTIONS}?user_id=eq.{uid}", anon, token,
        {"status": TAMPER}, prefer="return=minimal",
    )
    status, after = _call(
        "GET", f"{rest}/{SUBSCRIPTIONS}?select=status&user_id=eq.{uid}", anon, token
    )
    now = (_rows(after) or [{}])[0].get("status")
    tampered = now == TAMPER
    print(f"  {'edit own subscription status':<46} HTTP {status:<4} "
          f"{was} -> {now}{'   *** WRITABLE ***' if tampered else ''}")
    if tampered:
        report.fail(
            "a subscriber edited their own subscription row. Entitlement is "
            "self-service: anyone with an account can grant themselves the "
            "paid tier. Remove the update policy on subscriptions."
        )


def main() -> int:
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    anon = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or ""
    if not url or not anon:
        print("Supabase is not configured for this build; skipping the check.")
        print("That is not a pass. Set both variables to have it mean anything.")
        return 0

    rest = f"{url}/rest/v1"
    report = Report()
    withheld(report, rest, anon)

    email = os.environ.get("PAYWALL_TEST_EMAIL") or ""
    password = os.environ.get("PAYWALL_TEST_PASSWORD") or ""
    both_sides = False
    if email and password:
        print()
        session = sign_in(url, anon, email, password)
        if session is None:
            report.fail(
                "could not sign in as the test account, so nothing here proves a "
                "subscriber gets anything"
            )
        else:
            token, uid = session
            granted(report, rest, anon, token, uid)
            cannot_write(report, rest, anon, token, uid)
            both_sides = True

    print()
    if report.failures:
        print("FAILED:")
        for line in report.failures:
            print(f"  - {line}")
        return 1

    if both_sides:
        print("PASSED — outsiders got nothing, a subscriber got the sentinel and")
        print("could not write. Both halves are real: the same path answered")
        print("differently depending on who asked.")
        return 0

    print("PASSED, one-sidedly — every unentitled request came back empty.")
    print()
    print("Read that narrowly. It proves an outsider gets nothing. It does not")
    print("prove a subscriber gets something, and a dropped table or a policy")
    print("that denies everybody would pass exactly this way. Set")
    print("PAYWALL_TEST_EMAIL and PAYWALL_TEST_PASSWORD to close that gap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
