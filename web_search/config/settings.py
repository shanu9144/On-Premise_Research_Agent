import os
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / ".research_agent" / "search.sqlite3"


@lru_cache(maxsize=1)
def _dotenv():
    return dotenv_values(ROOT / ".env")


def setting(key, default=""):
    """Environment variables override the project's gitignored .env file."""
    return os.getenv(key) or _dotenv().get(key) or default


def number(key, default):
    return float(setting(key, str(default)))


@contextmanager
def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 30000")
        yield connection
    finally:
        connection.close()
