from __future__ import annotations

import re
from typing import Any, Iterator

from supabase import create_client, Client


def _escape_value(v: Any) -> str:
    """Convert a Python value to a safely-quoted SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    # String: escape single quotes by doubling them
    return "'" + str(v).replace("'", "''") + "'"


def _substitute(sql: str, params: tuple) -> str:
    """Replace ? placeholders with safely-quoted literals."""
    sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, flags=re.IGNORECASE)
    parts = sql.split("?")
    if len(parts) != len(params) + 1:
        raise ValueError(f"Placeholder count mismatch: {len(parts)-1} ? vs {len(params)} params")
    result = parts[0]
    for val, part in zip(params, parts[1:]):
        result += _escape_value(val) + part
    return result


class SupabaseCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.rowcount = len(rows)

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return self._rows

    def __iter__(self) -> Iterator[dict]:
        return iter(self._rows)


class SupabaseConnection:
    """
    Mimics sqlite3.Connection but routes queries to Supabase via RPC.
    Parameter substitution is done locally; ? placeholders are supported.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def execute(self, sql: str, params: tuple = ()) -> SupabaseCursor:
        final_sql = _substitute(sql.strip(), params)
        stripped = final_sql.lstrip().upper()

        if stripped.startswith("SELECT") or stripped.startswith("WITH"):
            rows = self._client.rpc("_rpc_query", {"sql": final_sql}).execute().data or []
            if isinstance(rows, list):
                return SupabaseCursor(rows)
            return SupabaseCursor([])
        else:
            self._client.rpc("_rpc_exec", {"sql": final_sql}).execute()
            return SupabaseCursor([])

    def executescript(self, sql: str) -> None:
        """Run multiple semicolon-separated DDL/DML statements."""
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            self._client.rpc("_rpc_exec", {"sql": stmt}).execute()

    def commit(self) -> None:
        pass  # Supabase REST is auto-commit

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> "SupabaseConnection":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


# Alias so existing imports still resolve
PgConnection = SupabaseConnection


def connect_supabase(url: str, service_role_key: str) -> SupabaseConnection:
    client = create_client(url, service_role_key)
    return SupabaseConnection(client)


def connect_postgres(dsn: str) -> SupabaseConnection:
    """Legacy entry-point — dsn is ignored; reads env for Supabase credentials."""
    import os
    from pathlib import Path

    env: dict[str, str] = {}
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")

    url = os.environ.get("SUPABASE_URL") or env.get("SUPABASE_URL") or ""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY") or ""

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    return connect_supabase(url, key)
