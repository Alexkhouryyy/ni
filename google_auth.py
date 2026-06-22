"""
JARVIS Google Auth — Non-blocking OAuth2 for Google Calendar + Gmail.

Flow:
  1. User downloads credentials.json from Google Cloud Console (Desktop app type)
  2. PUT credentials.json in the JARVIS directory
  3. Frontend calls /api/google/connect → gets auth_url back immediately
  4. Frontend opens auth_url in a new tab (or JARVIS opens it automatically)
  5. A background HTTP server on port 8341 waits for the OAuth callback
  6. After Google redirects back, token is saved to google_token.json
  7. Frontend polls /api/google/status until connected: true

Why not run_local_server()?
  run_local_server() blocks until auth is complete, which causes the API
  request to hang/timeout. This implementation returns the auth URL immediately
  and handles the callback asynchronously.
"""

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

log = logging.getLogger("jarvis.google_auth")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE       = Path(__file__).parent / "google_token.json"
CALLBACK_PORT    = 8341
REDIRECT_URI     = f"http://localhost:{CALLBACK_PORT}/"

# ---------------------------------------------------------------------------
# OAuth state (module-level — one flow at a time)
# ---------------------------------------------------------------------------

_pending_flow   = None
_oauth_running  = False
_oauth_error: str | None = None


# ---------------------------------------------------------------------------
# Core credential helpers
# ---------------------------------------------------------------------------

def get_credentials():
    """Return valid Google credentials, refreshing if needed. Returns None if not authorized."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        log.error("google-auth packages not installed. Run: pip install google-auth-oauthlib google-api-python-client")
        return None

    if not TOKEN_FILE.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            log.info("Google token refreshed successfully")
            return creds
    except Exception as e:
        log.warning(f"Token load/refresh failed: {e}")

    return None


def is_connected() -> bool:
    """Check if Google is authorized (no browser needed)."""
    if not CREDENTIALS_FILE.exists():
        return False
    return get_credentials() is not None


def get_oauth_status() -> dict:
    """Return current OAuth flow state for polling."""
    return {
        "running": _oauth_running,
        "error":   _oauth_error,
    }


# ---------------------------------------------------------------------------
# OAuth flow — non-blocking
# ---------------------------------------------------------------------------

def start_oauth() -> str:
    """
    Start the OAuth flow. Returns an auth URL immediately.

    Internally starts a lightweight HTTP server on port 8341 that waits for
    Google's redirect callback. Call is_connected() to check completion.

    Raises FileNotFoundError if credentials.json is missing.
    Raises RuntimeError if google-auth-oauthlib is not installed.
    """
    global _pending_flow, _oauth_running, _oauth_error

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "credentials.json not found in JARVIS folder. "
            "Download it from Google Cloud Console → APIs & Services → Credentials "
            "(create OAuth 2.0 Client ID, Desktop app type) and place it here."
        )

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise RuntimeError("google-auth-oauthlib not installed. Run: pip install google-auth-oauthlib")

    # Kill any previous pending flow
    _oauth_running = True
    _oauth_error   = None

    # Build flow + auth URL
    _pending_flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    _pending_flow.redirect_uri = REDIRECT_URI

    auth_url, _ = _pending_flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    log.info(f"OAuth flow started — callback listening on port {CALLBACK_PORT}")

    # Start background callback server
    _start_callback_server()

    return auth_url


def _start_callback_server():
    """Spin up a single-request HTTP server on CALLBACK_PORT to catch Google's redirect."""

    def _make_handler():
        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                global _oauth_running, _oauth_error, _pending_flow

                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" in params:
                    code = params["code"][0]
                    try:
                        _pending_flow.fetch_token(code=code)
                        TOKEN_FILE.write_text(_pending_flow.credentials.to_json())
                        _oauth_error   = None
                        _oauth_running = False

                        html = (
                            b"<html><head><style>"
                            b"body{font-family:-apple-system,sans-serif;text-align:center;"
                            b"padding:80px;background:#0a0e1a;color:#e0f7fa}"
                            b"h1{color:#4fc3f7;font-size:2rem}p{color:#90a4ae}"
                            b"</style></head><body>"
                            b"<h1>&#10003;&nbsp; JARVIS Connected</h1>"
                            b"<p>Google account authorized successfully.<br>You can close this tab.</p>"
                            b"</body></html>"
                        )
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.send_header("Content-Length", str(len(html)))
                        self.end_headers()
                        self.wfile.write(html)
                        log.info("Google OAuth complete — token saved to google_token.json")

                    except Exception as e:
                        _oauth_error   = str(e)
                        _oauth_running = False
                        log.error(f"OAuth token exchange failed: {e}")
                        body = f"<html><body><h2>Error</h2><pre>{e}</pre></body></html>".encode()
                        self.send_response(500)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(body)

                elif "error" in params:
                    error_msg = params["error"][0]
                    _oauth_error   = f"Google denied access: {error_msg}"
                    _oauth_running = False
                    log.error(f"OAuth denied: {error_msg}")
                    body = f"<html><body><h2>Access Denied</h2><p>{error_msg}</p></body></html>".encode()
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(body)

                else:
                    # Unexpected callback
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Unexpected callback")
                    _oauth_running = False

                # Shut down server after handling
                threading.Thread(target=self.server.shutdown, daemon=True).start()

            def log_message(self, *args):
                pass  # Silence HTTPServer's default request logging

        return _Handler

    def _run():
        global _oauth_running, _oauth_error
        try:
            server = HTTPServer(("localhost", CALLBACK_PORT), _make_handler())
            server.serve_forever()
        except OSError as e:
            # Port in use — likely a previous callback server still running
            _oauth_error   = f"Port {CALLBACK_PORT} is in use. Try again in a moment. ({e})"
            _oauth_running = False
            log.error(f"Callback server failed to start: {e}")
        except Exception as e:
            _oauth_error   = str(e)
            _oauth_running = False
            log.error(f"Callback server error: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------

def revoke():
    """Remove the saved token (forces re-auth on next use)."""
    global _oauth_running, _oauth_error
    _oauth_running = False
    _oauth_error   = None
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        log.info("Google token revoked")
