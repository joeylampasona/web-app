"""Compose and send the weekly digest.

Sending is off unless it is asked for. Every run is a dry run by default,
writing what it would have sent to a directory you can read.

The letter is composed ONCE and is the same for everyone. Nothing in it comes
from an account -- no watchlist, no holdings -- so the preview a person reads is
exactly what every subscriber receives, and the worst a bug here can do is send
the wrong market summary rather than the wrong person's data. That is the main
reason this job is as short as it is.

What remains worth guarding:

  * last_sent_at makes a re-run idempotent. A job that half-finished can be run
    again without reaching anyone twice.
  * A non-200 from Supabase raises. An error that came back as an empty
    subscriber list would report "0 sent" and look like a quiet week.
  * The service-role key is read from the environment and never logged. It
    bypasses row-level security by design, which is why it lives in CI secrets
    and nowhere else. It is used for exactly one thing: reading the addresses
    of people who asked for this.
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

    # One letter, composed before the loop, because every subscriber gets the
    # same one. Composing per person would invite the bug where they stop
    # being the same.
    digest = compose.build(out)
    subject = compose.subject(digest)
    print(f"this week's letter: {subject!r}", flush=True)

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

        # The only thing that differs per recipient is their own stop link.
        unsubscribe = f"{site}/unsubscribe?t={row['unsubscribe_token']}"
        html = render.html(digest, site, unsubscribe)
        text = render.text(digest, site, unsubscribe)

        if not args.send:
            # The address goes in the file name so a preview can be checked
            # against the right person, and the body is written beside it.
            stem = email.replace("@", "_at_").replace("/", "_")
            (preview / f"{stem}.html").write_text(html)
            (preview / f"{stem}.txt").write_text(
                f"To: {email}\nSubject: {subject}\n\n{text}")
            print(f"  would send to {email}", flush=True)
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
