"""
Pinterest OAuth helper — get an access token for the Pinterest API v5.

Commands:
  python scripts/pinterest_auth.py url            Print the auth URL to open in browser
  python scripts/pinterest_auth.py exchange CODE  Exchange a code for access + refresh tokens
  python scripts/pinterest_auth.py refresh        Refresh an expired access token
  python scripts/pinterest_auth.py boards         List your boards (to find PINTEREST_BOARD_ID)

Requires in .env:
  PINTEREST_CLIENT_ID
  PINTEREST_CLIENT_SECRET
  PINTEREST_REDIRECT_URI   (e.g. http://localhost:3100/)
  PINTEREST_REFRESH_TOKEN  (only for 'refresh' command)
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Load .env
for _line in (Path(__file__).parents[1] / ".env").read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        k, _, v = _line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

CLIENT_ID = os.environ.get("PINTEREST_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("PINTEREST_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("PINTEREST_REDIRECT_URI", "http://localhost:3100/")
SCOPE = "pins:write,boards:read,user_accounts:read"

TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"


def _require_credentials() -> None:
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: PINTEREST_CLIENT_ID and PINTEREST_CLIENT_SECRET must be set in .env")
        sys.exit(1)


def _basic_auth() -> str:
    return base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()


def _post_form(url: str, fields: dict) -> dict:
    body = urlencode(fields).encode()
    req = Request(url, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_basic_auth()}",
    })
    with urlopen(req) as resp:
        return json.loads(resp.read())


def _print_tokens(data: dict) -> None:
    if data.get("status") == "failure" or "error" in data:
        print(f"Error: {data}")
        sys.exit(1)
    print("\nAdd these to your .env:\n")
    print(f"PINTEREST_ACCESS_TOKEN={data['access_token']}")
    if data.get("refresh_token"):
        print(f"PINTEREST_REFRESH_TOKEN={data['refresh_token']}")
    print(f"\nAccess token expires in: {data.get('expires_in', '?')} seconds")
    if data.get("refresh_token_expires_in"):
        print(f"Refresh token expires in: {data['refresh_token_expires_in']} seconds")


def cmd_url() -> None:
    _require_credentials()
    params = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": "vance_auth",
    })
    print("Open this URL in your browser and authorize with your Pinterest account:\n")
    print(f"https://www.pinterest.com/oauth/?{params}")
    print(f"\nAfter authorizing, you'll be redirected to:\n  {REDIRECT_URI}?code=XXXX&state=vance_auth")
    print("\nCopy the 'code' value from the URL and run:")
    print("  python scripts/pinterest_auth.py exchange <CODE>")


def cmd_exchange(code: str) -> None:
    _require_credentials()
    data = _post_form(TOKEN_URL, {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })
    _print_tokens(data)


def cmd_refresh() -> None:
    _require_credentials()
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN", "")
    if not refresh_token:
        print("Error: PINTEREST_REFRESH_TOKEN must be set in .env")
        sys.exit(1)
    data = _post_form(TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    _print_tokens(data)


def cmd_boards() -> None:
    access_token = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
    if not access_token:
        print("Error: PINTEREST_ACCESS_TOKEN must be set in .env first")
        sys.exit(1)
    req = Request(
        "https://api.pinterest.com/v5/boards?page_size=25",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urlopen(req) as resp:
        data = json.loads(resp.read())
    boards = data.get("items", [])
    if not boards:
        print("No boards found.")
        return
    print("\nYour boards (copy the id into PINTEREST_BOARD_ID in .env):\n")
    for board in boards:
        print(f"  {board['id']}  —  {board['name']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "url"
    if cmd == "url":
        cmd_url()
    elif cmd == "exchange":
        if len(sys.argv) < 3:
            print("Usage: python scripts/pinterest_auth.py exchange <CODE>")
            sys.exit(1)
        cmd_exchange(sys.argv[2])
    elif cmd == "refresh":
        cmd_refresh()
    elif cmd == "boards":
        cmd_boards()
    else:
        print(__doc__)
