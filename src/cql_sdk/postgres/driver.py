"""Optional PostgreSQL driver loading and URL handling."""

from __future__ import annotations

import os
from importlib import import_module
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


def connect(database_url: str | None) -> Any:
    """Open a pg8000 DB-API connection from a PostgreSQL URL."""
    if not database_url:
        raise ValueError("database_url is required when no connection is supplied.")
    try:
        pg8000 = import_module("pg8000.dbapi")
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL execution requires the 'postgres' extra: "
            "pip install 'ms-cql-sdk[postgres]'"
        ) from exc

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("database_url must use the postgres:// or postgresql:// scheme.")
    if not parsed.hostname or not parsed.path.lstrip("/") or parsed.username is None:
        raise ValueError("database_url must include host, database, and user.")

    options: dict[str, Any] = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": unquote(parsed.path.lstrip("/")),
        "user": unquote(parsed.username),
        "password": (
            unquote(parsed.password) if parsed.password is not None else os.getenv("PGPASSWORD")
        ),
    }
    ssl_mode = parse_qs(parsed.query).get("sslmode", [None])[-1]
    if ssl_mode == "disable":
        options["ssl_context"] = False
    elif ssl_mode in {"require", "verify-ca", "verify-full"}:
        options["ssl_context"] = True
    return pg8000.connect(**options)
