from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


EST = timezone(timedelta(hours=-5), "EST")


def est_today() -> str:
    return datetime.now(EST).date().isoformat()


def est_yesterday() -> str:
    return (datetime.now(EST).date() - timedelta(days=1)).isoformat()


def est_days_ago(days: int) -> str:
    return (datetime.now(EST).date() - timedelta(days=days)).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def dumps_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def loads_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def require_row(row: sqlite3.Row | None, entity: str, entity_id: str) -> sqlite3.Row:
    if row is None:
        raise LookupError(f"{entity} not found: {entity_id}")
    return row
