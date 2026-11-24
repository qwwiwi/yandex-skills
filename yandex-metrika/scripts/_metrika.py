"""Shared helpers for the Yandex Metrika scripts: settings loading + HTTP.

Configuration comes from environment variables (or an optional env file):
  YANDEX_OAUTH_TOKEN   OAuth token with metrika:read (+ metrika:write for goals)
  METRIKA_COUNTER_ID   default counter id, or several ids separated by commas
  YANDEX_ENV_FILE      optional path to a KEY=VALUE file (default: ./.env)

All requests use the `Authorization: OAuth <token>` header.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_HOST = "https://api-metrika.yandex.net"


def _read_env_file() -> dict[str, str]:
    """Parse a KEY=VALUE file; returns {} when the file does not exist."""
    path = Path(os.environ.get("YANDEX_ENV_FILE", ".env"))
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_setting(name: str) -> str:
    """Return a setting from the environment, falling back to the env file."""
    return os.environ.get(name) or _read_env_file().get(name, "")


def load_token() -> str:
    """Return the OAuth token or exit with a clear message."""
    token = get_setting("YANDEX_OAUTH_TOKEN")
    if not token:
        raise SystemExit(
            "YANDEX_OAUTH_TOKEN is not set. Export it or put it into the env file "
            "(see README.md, section about the OAuth token)."
        )
    return token


def counters_for(counter: str | None) -> str:
    """Resolve the counter id(s): --counter value, else METRIKA_COUNTER_ID."""
    value = (counter or get_setting("METRIKA_COUNTER_ID")).replace(" ", "")
    if not value:
        raise SystemExit(
            "Counter id is not set. Pass --counter <id> or set METRIKA_COUNTER_ID. "
            "Run metrika_check.py to list the counters available to your token."
        )
    for part in value.split(","):
        if not part.isdigit():
            raise SystemExit(f"Invalid counter id '{part}': expected digits only.")
    return value


def request(method: str, path: str, token: str, params: dict | None = None,
            body: dict | None = None) -> dict:
    """Call the Metrika API and return parsed JSON; exit with a hint on HTTP errors."""
    url = API_HOST + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"OAuth {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            err = json.loads(raw)
        except ValueError:
            err = {"errors": raw[:400]}
        hint = ""
        if e.code == 401:
            hint = "\nHint: токен просрочен или невалиден – выпустите новый OAuth-токен."
        elif e.code == 429:
            hint = "\nHint: превышена квота (30 запросов/с, 5000/день, 3 параллельных) – подождите."
        raise SystemExit(f"HTTP {e.code}: {json.dumps(err, ensure_ascii=False)[:400]}{hint}")
