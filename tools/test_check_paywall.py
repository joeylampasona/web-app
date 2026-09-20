"""Does the paywall check actually catch a broken paywall?

check_paywall.py only ever runs against the live project, where — if
everything is working — every assertion passes. That is the one condition
under which a check tells you nothing about itself. So this stands up a fake
project that is broken in a specific way and confirms the check fails, once
per way it can be broken:

  healthy        outsiders refused, subscriber served, writes rejected -> pass
  leaking        the anon key gets the content                         -> fail
  denies-all     nobody gets it, subscribers included                  -> fail
  unseeded       the policy is fine but the sentinel row is missing    -> fail
  writable       a subscriber can insert content                       -> fail
  self-service   a subscriber can edit their own subscription          -> fail
  unreachable    the project does not answer at all                    -> fail

"denies-all" and "unreachable" are the two that matter most, because both look
exactly like a working paywall from the outside: no content comes back. Every
version of this check before the subscriber half existed passed both.

No network and no secrets — it talks to a socket on localhost.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "check_paywall.py")

ANON = "anon-key-for-the-fake-project"
TOKEN = "a-real-looking-access-token"
UID = "00000000-0000-4000-8000-000000000001"
SENTINEL = "selftest/entitlement.json"
EMAIL = "selftest@example.invalid"
PASSWORD = "not-a-real-password"


class Project:
    """A fake Supabase, broken in one named way."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.content = {SENTINEL: {"note": "fixture"}}
        self.status = "active"

    def entitled(self, bearer: str) -> bool:
        if self.mode == "denies-all":
            return False
        return bearer == TOKEN

    def rows_for(self, bearer: str, path: str | None) -> list:
        if self.mode == "leaking":
            visible = self.content
        elif self.entitled(bearer):
            visible = self.content
        else:
            visible = {}
        if self.mode == "unseeded":
            visible = {k: v for k, v in visible.items() if k != SENTINEL}
        if path is not None:
            return [{"path": path, "payload": visible[path]}] if path in visible else []
        return [{"path": k, "payload": v} for k, v in visible.items()]


class Handler(BaseHTTPRequestHandler):
    project: Project

    def log_message(self, *args) -> None:  # quiet
        pass

    def _send(self, code: int, body) -> None:
        raw = json.dumps(body).encode() if not isinstance(body, str) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _bearer(self) -> str:
        return (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except ValueError:
            return {}

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        bearer = self._bearer()
        if bearer not in (ANON, TOKEN):
            self._send(401, {"message": "invalid claim"})
            return
        if url.path == "/rest/v1/gated_content":
            eq = (query.get("path") or [""])[0]
            path = eq.removeprefix("eq.") if eq else None
            self._send(200, self.project.rows_for(bearer, path))
            return
        if url.path == "/rest/v1/subscriptions":
            if bearer != TOKEN:
                self._send(200, [])
                return
            self._send(200, [{"user_id": UID, "status": self.project.status}])
            return
        self._send(404, {"message": "no such table"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        bearer = self._bearer()
        if url.path == "/auth/v1/token":
            body = self._body()
            if body.get("email") == EMAIL and body.get("password") == PASSWORD:
                self._send(200, {"access_token": TOKEN, "user": {"id": UID}})
            else:
                self._send(400, {"error_description": "Invalid login credentials"})
            return
        if url.path == "/rest/v1/rpc/is_subscriber":
            self._send(200, "true" if self.project.entitled(bearer) else "false")
            return
        if url.path == "/rest/v1/gated_content":
            if self.project.mode == "writable" and bearer == TOKEN:
                body = self._body()
                self.project.content[body["path"]] = body.get("payload") or {}
                self._send(201, "")
            else:
                self._send(403, {"code": "42501", "message": "row-level security"})
            return
        self._send(404, {"message": "no such route"})

    def do_PATCH(self) -> None:
        url = urlparse(self.path)
        bearer = self._bearer()
        if url.path == "/rest/v1/subscriptions":
            if self.project.mode == "self-service" and bearer == TOKEN:
                self.project.status = self._body().get("status", self.project.status)
                self._send(204, "")
            else:
                self._send(403, {"code": "42501", "message": "row-level security"})
            return
        self._send(404, {"message": "no such route"})


def run(mode: str) -> tuple[int, str]:
    if mode == "unreachable":
        # A port nothing is listening on: the shape of a network failure, which
        # is the case that used to read as a pass.
        base, server = "http://127.0.0.1:9", None
    else:
        Handler.project = Project(mode)
        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"

    env = dict(os.environ)
    env.update({
        "NEXT_PUBLIC_SUPABASE_URL": base,
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": ANON,
        "PAYWALL_TEST_EMAIL": EMAIL,
        "PAYWALL_TEST_PASSWORD": PASSWORD,
        # The check must reach the stub directly; a proxy in the environment
        # would turn every scenario into "unreachable".
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    })
    done = subprocess.run([sys.executable, CHECK], env=env,
                          capture_output=True, text=True, timeout=120)
    if server is not None:
        server.shutdown()
    return done.returncode, done.stdout + done.stderr


EXPECTED = {
    "healthy": 0,
    "leaking": 1,
    "denies-all": 1,
    "unseeded": 1,
    "writable": 1,
    "self-service": 1,
    "unreachable": 1,
}


def main() -> int:
    print("The paywall check, against projects broken on purpose")
    print("-" * 72)
    bad = 0
    for mode, want in EXPECTED.items():
        code, output = run(mode)
        ok = code == want
        verb = "passes" if code == 0 else "fails"
        print(f"  {mode:<14} check {verb:<7} expected {'pass' if want == 0 else 'fail'}"
              f"   {'ok' if ok else '*** WRONG ***'}")
        if not ok:
            bad += 1
            print("    ---- what it printed ----")
            for line in output.splitlines():
                print(f"    {line}")
    print()
    if bad:
        print(f"FAILED — {bad} scenario(s) the check does not catch.")
        return 1
    print("PASSED — the check notices all six ways this can break, including")
    print("the two that look identical to a working paywall from outside.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
