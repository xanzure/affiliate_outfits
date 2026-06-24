"""
TikTok OAuth helper — get an access token for the Content Posting API.

Commands:
  python scripts/tiktok_auth.py url            Print the auth URL to open in browser
  python scripts/tiktok_auth.py exchange CODE  Exchange a code for access + refresh tokens
  python scripts/tiktok_auth.py refresh        Refresh an expired access token

Requires in .env:
  TIKTOK_CLIENT_KEY
  TIKTOK_CLIENT_SECRET
  TIKTOK_REDIRECT_URI   (e.g. http://localhost:3100/)
  TIKTOK_REFRESH_TOKEN  (only for 'refresh' command)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen

# Load .env
for _line in (Path(__file__).parents[1] / ".env").read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        k, _, v = _line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:3100/")
SCOPE = "user.info.basic,video.publish"

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_VERIFIER_FILE = Path(__file__).parent / ".tiktok_code_verifier"


def _require_credentials() -> None:
    if not CLIENT_KEY or not CLIENT_SECRET:
        print("Error: TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be set in .env")
        sys.exit(1)


def _make_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _post_form(url: str, fields: dict) -> dict:
    body = urlencode(fields).encode()
    req = Request(url, data=body, method="POST",
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req) as resp:
        return json.loads(resp.read())


def _print_tokens(data: dict) -> None:
    if data.get("error"):
        print(f"Error: {data}")
        sys.exit(1)
    print("\nAdd these to your .env:\n")
    print(f"TIKTOK_ACCESS_TOKEN={data['access_token']}")
    if data.get("refresh_token"):
        print(f"TIKTOK_REFRESH_TOKEN={data['refresh_token']}")
    print(f"\nAccess token expires in: {data.get('expires_in', '?')} seconds")
    if data.get("refresh_token_expires_in"):
        print(f"Refresh token expires in: {data['refresh_token_expires_in']} seconds")


def cmd_url() -> None:
    _require_credentials()
    verifier, challenge = _make_pkce()
    _VERIFIER_FILE.write_text(verifier)
    params = urlencode({
        "client_key": CLIENT_KEY,
        "scope": SCOPE,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": "vance_auth",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print("Open this URL in your browser and authorize with your TikTok account:\n")
    print(f"https://www.tiktok.com/v2/auth/authorize/?{params}")
    print(f"\nAfter authorizing, you'll be redirected to:\n  {REDIRECT_URI}?code=XXXX&state=vance_auth")
    print("\nCopy the 'code' value from the URL and run:")
    print("  python scripts/tiktok_auth.py exchange <CODE>")


def cmd_exchange(code: str) -> None:
    _require_credentials()
    if not _VERIFIER_FILE.exists():
        print("Error: run 'url' command first to generate a code verifier")
        sys.exit(1)
    verifier = _VERIFIER_FILE.read_text().strip()
    code = unquote(code)  # decode %2A → * etc from URL bar copy-paste
    data = _post_form(TOKEN_URL, {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    })
    _VERIFIER_FILE.unlink(missing_ok=True)
    _print_tokens(data)


def cmd_refresh() -> None:
    _require_credentials()
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN", "")
    if not refresh_token:
        print("Error: TIKTOK_REFRESH_TOKEN must be set in .env")
        sys.exit(1)
    data = _post_form(TOKEN_URL, {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    _print_tokens(data)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "url"
    if cmd == "url":
        cmd_url()
    elif cmd == "exchange":
        if len(sys.argv) < 3:
            print("Usage: python scripts/tiktok_auth.py exchange <CODE>")
            sys.exit(1)
        cmd_exchange(sys.argv[2])
    elif cmd == "refresh":
        cmd_refresh()
    else:
        print(__doc__)
