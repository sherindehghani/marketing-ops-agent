
import sqlite3
from datetime import date, timedelta

BASE = """
SELECT c.id, c.name, c.channel, c.objective, c.status, c.daily_budget,
       SUM(m.impressions) AS impressions, SUM(m.clicks) AS clicks,
       SUM(m.spend) AS spend, SUM(m.conversions) AS conversions, SUM(m.revenue) AS revenue
FROM campaigns AS c LEFT JOIN daily_metrics AS m
  ON c.id=m.campaign_id AND m.date BETWEEN ? AND ?
GROUP BY c.id
"""
RATIOS = """
1.0*revenue/NULLIF(spend,0) AS roas,
100.0*clicks/NULLIF(impressions,0) AS ctr,
100.0*conversions/NULLIF(clicks,0) AS conversion_rate
"""


def window(days):
    end = date.today()
    return ((end - timedelta(days=days - 1)).isoformat(), end.isoformat())


def query(path, sql, bindings=()):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ}
        functions = {
            "sum",
            "nullif",
            "count",
            "avg",
            "min",
            "max",
            "round",
            "coalesce",
            "like",
            "abs",
            "lower",
            "instr",
        }

        def authorize(action, first, second, db, source):
            if action in allowed or (
                action == sqlite3.SQLITE_FUNCTION and second.lower() in functions
            ):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        conn.set_authorizer(authorize)
        budget = iter(range(2000))
        conn.set_progress_handler(lambda: next(budget, None) is None, 1000)
        rows = conn.execute(sql, bindings).fetchmany(201)
        if len(rows) > 200:
            raise ValueError("More than 200 rows. Narrow the request.")
        return [dict(row) for row in rows]
    finally:
        conn.close()
