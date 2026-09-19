"""Compose and send the weekly digest.

Sending is off unless it is asked for. Every run is a dry run by default,
writing what it would have sent to a directory you can read. The switch to
actually send is an argument, not a default, because the failure that matters
here is not a broken layout: it is one person receiving another person's
watchlist, and that cannot be taken back.

Three things guard against it:

  * Rows are fetched per user and every row is checked to carry the user_id it
    was fetched for. A mismatch aborts the whole run rather than skipping the
    row, because a mismatch means the query is wrong and every other row is
    suspect too.
  * last_sent_at makes a re-run idempotent. A job that half-finished can be run
    again without reaching anyone twice.
  * The service-role key is read from the environment and never logged. It
    bypasses row-level security by design, which is why it lives in CI secrets
    and nowhere else.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
from typing import Any

import requests

from digest import compose, render

RESEND_ENDPOINT = "https://api.resend.com/emails"

# A re-run inside this window treats a person as already reached.
RESEND_GUARD_HOURS = 72
# Resend's API is rate limited; a small gap is cheaper than a 429 storm.
PAUSE_BETWEEN_SENDS = 0.6


class DigestError(RuntimeError):
    pass


def _env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise DigestError(f"{name} is not set")
    return value


def _supabase_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def fetch_subscribers(url: str, service_key: str) -> list[dict[str, Any]]:
    """Everyone who asked for the digest and has not been switched off."""
    resp = requests.get(
        f"{url}/rest/v1/email_prefs",
        headers=_supabase_headers(service_key),
        params={
            "select": "user_id,email,unsubscribe_token,last_sent_at",
            "weekly_digest": "eq.true",
            "disabled_at": "is.null",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise DigestError(f"reading subscribers failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def fetch_watchlist(url: str, service_key: str, user_id: str) -> list[str]:
    """One person's tickers, checked to actually be theirs.

    The check is not paranoia about the database. It is about the query: a
    filter that silently stopped applying would return everyone's rows, and
    the only visible symptom would be strangers' tickers in somebody's email.
    """
    resp = requests.get(
        f"{url}/rest/v1/watchlist",
        headers=_supabase_headers(service_key),
        params={"select": "symbol,user_id", "user_id": f"eq.{user_id}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise DigestError(f"reading a watchlist failed: {resp.status_code} {resp.text[:200]}")
    rows = resp.json()
    for row in rows:
        if row.get("user_id") != user_id:
            raise DigestError(
                "a watchlist row came back for a different account than it was "
                "requested for. Refusing to send anything: if this filter is "
                "wrong, every other row in this run is suspect too."
            )
    return [r["symbol"] for r in rows]


def mark_sent(url: str, service_key: str, user_id: str) -> None:
    requests.patch(
        f"{url}/rest/v1/email_prefs",
        headers={**_supabase_headers(service_key), "Prefer": "return=minimal"},
        params={"user_id": f"eq.{user_id}"},
        json={"last_sent_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        timeout=30,
    )


def recently_sent(row: dict[str, Any]) -> bool:
    stamp = row.get("last_sent_at")
    if not stamp:
        return False
    try:
        when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = dt.datetime.now(dt.timezone.utc) - when
    return age < dt.timedelta(hours=RESEND_GUARD_HOURS)


def deliver(api_key: str, sender: str, to: str, subject: str,
            html: str, text: str, unsubscribe_url: str) -> str:
    """Hand one message to Resend. Returns its id."""
    resp = requests.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
            # Gmail and Outlook render their own unsubscribe button from these,
            # which is both a courtesy and the thing that keeps complaints from
            # turning into a domain reputation problem.
            "headers": {
                "List-Unsubscribe": f"<{unsubscribe_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise DigestError(f"Resend refused a message: {resp.status_code} {resp.text[:200]}")
    return resp.json().get("id", "")


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Send the weekly digest.")
    ap.add_argument("--send", action="store_true",
                    help="actually send. Without it, nothing leaves the building.")
    ap.add_argument("--out", default="out", help="the published tree to read")
    ap.add_argument("--preview-dir", default="var/digest-preview",
                    help="where a dry run writes what it would have sent")
    ap.add_argument("--only", default="",
                    help="one address, for a test send to yourself")
    ap.add_argument("--force", action="store_true",
                    help="ignore last_sent_at. Can send someone a second copy.")
    args = ap.parse_args(argv)

    site = os.environ.get("SITE_URL", "https://thetape.cc").rstrip("/")
    out = pathlib.Path(args.out)
    if not (out / "meta.json").exists():
        raise DigestError(f"no published data at {out}/ — nothing to send")

    url = _env("SUPABASE_URL").rstrip("/")
    service_key = _env("SUPABASE_SERVICE_ROLE_KEY")
    sender = os.environ.get("DIGEST_FROM", "The Tape <noreply@thetape.cc>")
    api_key = _env("RESEND_API_KEY", required=args.send)

    subscribers = fetch_subscribers(url, service_key)
    if args.only:
        subscribers = [s for s in subscribers if s.get("email") == args.only]
    print(f"{len(subscribers)} subscriber(s) opted in", flush=True)

    preview = pathlib.Path(args.preview_dir)
    if not args.send:
        preview.mkdir(parents=True, exist_ok=True)

    sent = skipped = 0
    for row in subscribers:
        user_id, email = row["user_id"], row["email"]
        if not args.force and recently_sent(row):
            skipped += 1
            continue

        watchlist = fetch_watchlist(url, service_key, user_id)
        digest = compose.build(out, watchlist)
        unsubscribe = f"{site}/unsubscribe?t={row['unsubscribe_token']}"
        html = render.html(digest, site, unsubscribe)
        text = render.text(digest, site, unsubscribe)
        subject = compose.subject(digest)

        if not args.send:
            # The address goes in the file name so a preview can be checked
            # against the right person, and the body is written beside it.
            stem = email.replace("@", "_at_").replace("/", "_")
            (preview / f"{stem}.html").write_text(html)
            (preview / f"{stem}.txt").write_text(
                f"To: {email}\nSubject: {subject}\n\n{text}")
            print(f"  would send to {email}: {subject} "
                  f"({len(watchlist)} on their watchlist)", flush=True)
            sent += 1
            continue

        deliver(api_key, sender, email, subject, html, text, unsubscribe)
        mark_sent(url, service_key, user_id)
        sent += 1
        print(f"  sent to {email}", flush=True)
        time.sleep(PAUSE_BETWEEN_SENDS)

    verb = "sent" if args.send else "composed (nothing sent)"
    print(f"\n{sent} {verb}, {skipped} skipped as already reached this week",
          flush=True)
    if not args.send:
        print(f"Read them in {preview}/", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except DigestError as exc:
        print(f"digest failed: {exc}", file=sys.stderr)
        sys.exit(1)
