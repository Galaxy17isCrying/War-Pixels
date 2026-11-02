"""Small GitHub OAuth and JSON account API backed by a separate SQLite database."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import http.cookies
import json
import logging
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.config import SAVE_DIR

ROOT = Path(__file__).resolve().parent.parent
SESSION_TTL = 7 * 24 * 60 * 60
STATE_TTL = 10 * 60
OAUTH_STATE_COOKIE = "war_pixels_oauth_state"
SESSION_COOKIE = "war_pixels_session"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AccountStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS github_accounts (
                    github_id TEXT PRIMARY KEY,
                    login TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_hash TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    github_id TEXT NOT NULL REFERENCES github_accounts(github_id) ON DELETE CASCADE,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            with connection:
                yield connection
        finally:
            connection.close()

    def issue_state(self) -> str:
        state = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("DELETE FROM oauth_states WHERE created_at < ?", (now - STATE_TTL,))
            connection.execute("INSERT INTO oauth_states(state_hash, created_at) VALUES (?, ?)",
                               (token_digest(state), now))
        return state

    def consume_state(self, state: str) -> bool:
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = connection.execute(
                "DELETE FROM oauth_states WHERE state_hash=? AND created_at>=?",
                (token_digest(state), now - STATE_TTL),
            )
            return result.rowcount == 1

    def upsert_github_account(self, github_id: str, login: str, display_name: str) -> None:
        now = int(time.time())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO github_accounts(github_id,login,display_name,created_at,updated_at) "
                "VALUES(?,?,?,?,?) ON CONFLICT(github_id) DO UPDATE SET "
                "login=excluded.login,display_name=excluded.display_name,updated_at=excluded.updated_at",
                (github_id, login, display_name, now, now),
            )

    def create_session(self, github_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions(token_hash,github_id,created_at,expires_at) VALUES(?,?,?,?)",
                (token_digest(token), github_id, now, now + SESSION_TTL),
            )
        return token

    def account_for_session(self, token: str):
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            row = connection.execute(
                "SELECT account.github_id,account.login,account.display_name "
                "FROM sessions AS session JOIN github_accounts AS account "
                "ON account.github_id=session.github_id "
                "WHERE session.token_hash=? AND session.expires_at>?",
                (token_digest(token), now),
            ).fetchone()
        return dict(row) if row else None

    def revoke_session(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_digest(token),))


class OAuthHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, store, client_id, client_secret, redirect_uri, secure_cookie):
        self.account_store = store
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.secure_cookie = secure_cookie
        super().__init__(address, handler)


class OAuthAPIHandler(BaseHTTPRequestHandler):
    server: OAuthHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format_string, *args):
        path = urllib.parse.urlsplit(self.path).path
        logging.info("%s %s", self.command, path)

    def _send_json(self, status: int, value: dict, headers=()) -> None:
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _session_token(self):
        authorization = self.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return authorization[7:].strip()
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except http.cookies.CookieError:
            return ""
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _cookie(self, name: str, value: str, max_age: int) -> str:
        secure = "; Secure" if self.server.secure_cookie else ""
        return f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax{secure}"

    def _redirect(self, location: str, cookies=()) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", "0")
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path)
        if path.path == "/api/health":
            self._send_json(200, {"status": "ok", "service": "war-pixels-api"})
        elif path.path == "/auth/github/login":
            self._github_login()
        elif path.path == "/auth/github/callback":
            self._github_callback(urllib.parse.parse_qs(path.query, keep_blank_values=True))
        elif path.path == "/api/me":
            account = self.server.account_store.account_for_session(self._session_token())
            if account is None:
                self._send_json(401, {"error": "authentication_required"})
            else:
                self._send_json(200, {"account": account})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/logout":
            self._send_json(404, {"error": "not_found"})
            return
        token = self._session_token()
        if token:
            self.server.account_store.revoke_session(token)
        cookie = self._cookie(SESSION_COOKIE, "", 0)
        self._send_json(200, {"status": "signed_out"}, (("Set-Cookie", cookie),))

    def _github_login(self):
        if not self.server.client_id or not self.server.client_secret:
            self._send_json(503, {"error": "github_oauth_not_configured"})
            return
        state = self.server.account_store.issue_state()
        query = urllib.parse.urlencode({
            "client_id": self.server.client_id,
            "redirect_uri": self.server.redirect_uri,
            "scope": "read:user",
            "state": state,
        })
        self._redirect(
            "https://github.com/login/oauth/authorize?" + query,
            (self._cookie(OAUTH_STATE_COOKIE, state, STATE_TTL),),
        )

    def _github_callback(self, query):
        provider_error = query.get("error", [""])[0]
        if provider_error:
            self._send_json(400, {"error": "github_authorization_denied"})
            return
        code = query.get("code", [""])[0]
        state = query.get("state", [""])[0]
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except http.cookies.CookieError:
            self._send_json(400, {"error": "invalid_oauth_state"})
            return
        state_cookie = cookie.get(OAUTH_STATE_COOKIE)
        if (not code or not state or state_cookie is None or
                not secrets.compare_digest(state, state_cookie.value) or
                not self.server.account_store.consume_state(state)):
            self._send_json(400, {"error": "invalid_oauth_state"})
            return
        if not self.server.client_id or not self.server.client_secret:
            self._send_json(503, {"error": "github_oauth_not_configured"})
            return

        try:
            access_token = self._exchange_code(code)
            profile = self._github_profile(access_token)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            logging.exception("GitHub OAuth exchange failed")
            self._send_json(502, {"error": "github_authorization_failed"})
            return
        github_id = profile.get("id")
        login = profile.get("login")
        display_name = profile.get("name") or login
        if (isinstance(github_id, bool) or not isinstance(github_id, int) or
                not isinstance(login, str) or not login):
            self._send_json(502, {"error": "invalid_github_profile"})
            return
        account_id = str(github_id)
        self.server.account_store.upsert_github_account(account_id, login[:64], str(display_name)[:128])
        token = self.server.account_store.create_session(account_id)
        session_cookie = self._cookie(SESSION_COOKIE, token, SESSION_TTL)
        state_clear = self._cookie(OAUTH_STATE_COOKIE, "", 0)
        self._redirect("/api/me", (session_cookie, state_clear))

    def _exchange_code(self, code: str) -> str:
        body = urllib.parse.urlencode({
            "client_id": self.server.client_id,
            "client_secret": self.server.client_secret,
            "code": code,
            "redirect_uri": self.server.redirect_uri,
        }).encode("ascii")
        request = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=body,
            headers={"Accept": "application/json", "User-Agent": "War-Pixels"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read(65536))
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError("GitHub did not return an access token")
        return token

    @staticmethod
    def _github_profile(access_token: str):
        request = urllib.request.Request(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "War-Pixels",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            profile = json.loads(response.read(65536))
        if not isinstance(profile, dict):
            raise ValueError("GitHub returned an invalid profile")
        return profile


def build_server(host: str, port: int, db_path: Path | None = None) -> OAuthHTTPServer:
    load_dotenv()
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")
    redirect_uri = os.environ.get(
        "GITHUB_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/github/callback"
    )
    parsed_redirect = urllib.parse.urlsplit(redirect_uri)
    if parsed_redirect.scheme not in ("http", "https") or not parsed_redirect.netloc:
        raise ValueError("GITHUB_OAUTH_REDIRECT_URI must be an absolute HTTP(S) URL.")
    if parsed_redirect.scheme != "https" and parsed_redirect.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("GitHub OAuth requires HTTPS except for localhost development.")
    database_path = db_path or Path(os.environ.get("WARPIXELS_AUTH_DB", SAVE_DIR / "accounts.db"))
    store = AccountStore(database_path)
    secure_cookie = os.environ.get("WARPIXELS_COOKIE_SECURE", "true").lower() in ("1", "true", "yes")
    return OAuthHTTPServer(
        (host, port), OAuthAPIHandler, store, client_id, client_secret, redirect_uri, secure_cookie
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the War Pixels GitHub OAuth and REST API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = build_server(args.host, args.port)
    logging.info("War Pixels API listening on %s:%s", *server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("API server stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
