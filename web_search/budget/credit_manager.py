import uuid
from datetime import datetime, timezone

from ..config.settings import connect
from ..models.provider_usage import SCALE, to_units


class BudgetExceeded(Exception):
    pass


def _periods():
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now.timestamp(), day.timestamp(), day.replace(day=1).timestamp()


class CreditManager:
    """Atomic per-provider reservations; uncertain charges keep their estimate."""

    def __init__(self, path):
        self.path = path
        with connect(path) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS reservations (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL, created REAL NOT NULL,
                    estimated INTEGER NOT NULL, charged INTEGER NOT NULL, actual INTEGER, status TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS reservations_provider_time ON reservations(provider, created);
            """)

    @staticmethod
    def _used(connection, provider, day, month):
        return connection.execute(
            "SELECT COALESCE(SUM(CASE WHEN created >= ? THEN charged ELSE 0 END), 0), COALESCE(SUM(charged), 0) "
            "FROM reservations WHERE provider = ? AND created >= ?", (day, provider, month)).fetchone()

    def reserve(self, provider, estimate, budget, important=False):
        amount = to_units(estimate)
        now, day, month = _periods()
        reservation = uuid.uuid4().hex
        with connect(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            daily, monthly = self._used(connection, provider, day, month)
            monthly_limit = to_units(budget.monthly) - (0 if important else to_units(budget.reserve))
            if daily + amount > to_units(budget.daily) or monthly + amount > monthly_limit:
                connection.rollback()
                raise BudgetExceeded(f"{provider} budget exhausted")
            connection.execute("INSERT INTO reservations VALUES (?, ?, ?, ?, ?, NULL, 'pending')",
                               (reservation, provider, now, amount, amount))
            connection.commit()
        return reservation

    def settle(self, reservation, actual=None, definitely_unbilled=False):
        with connect(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT estimated, status FROM reservations WHERE id = ?",
                                     (reservation,)).fetchone()
            if not row or row[1] != "pending":
                connection.rollback()
                raise ValueError("Unknown or already settled reservation")
            actual_units = to_units(actual) if actual is not None else None
            charge = 0 if definitely_unbilled else max(row[0], actual_units or 0)
            connection.execute("UPDATE reservations SET charged = ?, actual = ?, status = 'settled' WHERE id = ?",
                               (charge, actual_units, reservation))
            connection.commit()

    def remaining(self, provider, budget):
        _, day, month = _periods()
        with connect(self.path) as connection:
            daily, monthly = self._used(connection, provider, day, month)
        return {"daily": max(0, budget.daily - daily / SCALE),
                "monthly": max(0, budget.monthly - monthly / SCALE), "unit": budget.unit}

    def spending(self, provider):
        _, _, month = _periods()
        with connect(self.path) as connection:
            count, estimated, charged, actual = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(estimated), 0), COALESCE(SUM(charged), 0), SUM(actual) "
                "FROM reservations WHERE provider = ? AND created >= ?", (provider, month)).fetchone()
        return {"requests": count, "estimated": estimated / SCALE, "accounted": charged / SCALE,
                "reported_actual": None if actual is None else actual / SCALE}
