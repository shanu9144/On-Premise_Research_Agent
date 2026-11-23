import hashlib
import json
import time

from ..config.settings import connect

TTL_SECONDS = {"normal": 86400, "recent": 900, "live": 0}


class CacheManager:
    def __init__(self, path):
        self.path = path
        with connect(path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS cache "
                               "(key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)")

    @staticmethod
    def key(value):
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def get(self, key):
        with connect(self.path) as connection:
            row = connection.execute("SELECT value FROM cache WHERE key = ? AND expires > ?",
                                     (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, value, ttl):
        if ttl <= 0:
            return
        with connect(self.path) as connection:
            connection.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                               (key, json.dumps(value, ensure_ascii=False), time.time() + ttl))

    def clear(self):
        with connect(self.path) as connection:
            connection.execute("DELETE FROM cache")
