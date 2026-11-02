import http.cookies
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

from server import api


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class AccountStoreTests(unittest.TestCase):
    def test_oauth_state_is_hashed_and_single_use(self):
        with tempfile.TemporaryDirectory() as temp:
            store = api.AccountStore(Path(temp) / "accounts.db")
            state = store.issue_state()

            with store._connect() as connection:
                saved = connection.execute("SELECT state_hash FROM oauth_states").fetchone()[0]

            self.assertNotEqual(saved, state)
            self.assertEqual(saved, api.token_digest(state))
            self.assertTrue(store.consume_state(state))
            self.assertFalse(store.consume_state(state))

    def test_session_token_is_hashed_and_resolves_account(self):
        with tempfile.TemporaryDirectory() as temp:
            store = api.AccountStore(Path(temp) / "accounts.db")
            store.upsert_github_account("42", "player", "Player One")
            token = store.create_session("42")

            with store._connect() as connection:
                saved = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]

            self.assertNotEqual(saved, token)
            self.assertEqual(saved, api.token_digest(token))
            self.assertEqual(store.account_for_session(token), {
                "github_id": "42", "login": "player", "display_name": "Player One",
            })

    def test_github_profile_uses_transient_bearer_token(self):
        response = io.BytesIO(json.dumps({"id": 42, "login": "player"}).encode("utf-8"))
        with patch("server.api.urllib.request.urlopen", return_value=response) as urlopen:
            profile = api.OAuthAPIHandler._github_profile("test-transient-token")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-transient-token")
        self.assertEqual(profile["login"], "player")


class OAuthAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = api.build_server(
            "127.0.0.1", 0, Path(self.temp.name) / "accounts.db"
        )
        self.server.client_id = "test-client-id"
        self.server.client_secret = "test-client-secret"
        self.server.redirect_uri = "http://127.0.0.1/auth/github/callback"
        self.server.secure_cookie = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        self.opener = urllib.request.build_opener(NoRedirect)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request_redirect(self, path, cookie=""):
        request = urllib.request.Request(self.base_url + path, headers={"Cookie": cookie})
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.opener.open(request)
        self.addCleanup(raised.exception.close)
        return raised.exception

    def test_health_and_github_oauth_login_callback_and_authenticated_api(self):
        with urllib.request.urlopen(self.base_url + "/api/health", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {
                "status": "ok", "service": "war-pixels-api",
            })

        login = self.request_redirect("/auth/github/login")
        self.assertEqual(login.code, 303)
        authorization = urllib.parse.urlsplit(login.headers["Location"])
        authorization_query = urllib.parse.parse_qs(authorization.query)
        self.assertEqual(authorization.netloc, "github.com")
        self.assertEqual(authorization_query["client_id"], ["test-client-id"])
        state_cookie = http.cookies.SimpleCookie()
        state_cookie.load(login.headers["Set-Cookie"])
        state = authorization_query["state"][0]
        self.assertEqual(state_cookie[api.OAUTH_STATE_COOKIE].value, state)

        with patch.object(api.OAuthAPIHandler, "_exchange_code", return_value="transient-token"), \
                patch.object(api.OAuthAPIHandler, "_github_profile",
                             return_value={"id": 99, "login": "pixel-player", "name": "Pixel Player"}):
            callback = self.request_redirect(
                f"/auth/github/callback?code=one-time-code&state={urllib.parse.quote(state)}",
                f"{api.OAUTH_STATE_COOKIE}={state}",
            )

        self.assertEqual(callback.code, 303)
        cookies = http.cookies.SimpleCookie()
        for header in callback.headers.get_all("Set-Cookie"):
            cookies.load(header)
        session_token = cookies[api.SESSION_COOKIE].value
        self.assertEqual(cookies[api.OAUTH_STATE_COOKIE]["max-age"], "0")

        request = urllib.request.Request(
            self.base_url + "/api/me",
            headers={"Cookie": f"{api.SESSION_COOKIE}={session_token}"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            body = json.loads(response.read())
        self.assertEqual(body["account"]["login"], "pixel-player")
        self.assertEqual(body["account"]["display_name"], "Pixel Player")
        with self.server.account_store._connect() as connection:
            stored_token = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
        self.assertEqual(stored_token, api.token_digest(session_token))


if __name__ == "__main__":
    unittest.main()
