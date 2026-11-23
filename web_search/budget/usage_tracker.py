import time

from ..config.settings import connect


class UsageTracker:
    """Aggregate execution telemetry; never stores queries or credentials."""

    def __init__(self, path):
        self.path = path
        with connect(path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    created REAL NOT NULL, provider TEXT, operation TEXT NOT NULL, elapsed REAL NOT NULL,
                    success INTEGER NOT NULL, cache_hit INTEGER NOT NULL, fallback INTEGER NOT NULL,
                    result_count INTEGER NOT NULL, quality REAL NOT NULL, reason TEXT NOT NULL)
            """)

    def record(self, provider, operation, elapsed, success, cache_hit, fallback, count, quality, reason):
        with connect(self.path) as connection:
            connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (time.time(), provider, operation, elapsed, int(success), int(cache_hit),
                                int(fallback), count, quality, reason[:120]))

    def summary(self):
        with connect(self.path) as connection:
            rows = connection.execute(
                "SELECT provider, COUNT(*), SUM(success), AVG(elapsed), SUM(cache_hit), SUM(fallback) "
                "FROM events GROUP BY provider").fetchall()
        return {provider: {"executions": count, "success_rate": successes / count, "average_seconds": average,
                           "cache_hits": hits, "fallbacks": fallbacks}
                for provider, count, successes, average, hits, fallbacks in rows}
