import argparse
import os
import random
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE campaigns (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 channel TEXT NOT NULL CHECK(channel IN ('google_ads','instagram','linkedin','email')),
 objective TEXT NOT NULL CHECK(objective IN ('conversion','brand_awareness','retargeting')),
 daily_budget REAL NOT NULL CHECK(daily_budget>0),
 status TEXT NOT NULL CHECK(status IN ('active','paused','ended')), start_date TEXT NOT NULL
);
CREATE TABLE daily_metrics (
 id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id), date TEXT NOT NULL,
 impressions INTEGER NOT NULL CHECK(impressions>=0), clicks INTEGER NOT NULL CHECK(clicks BETWEEN 0 AND impressions),
 spend REAL NOT NULL CHECK(spend>=0), conversions INTEGER NOT NULL CHECK(conversions BETWEEN 0 AND clicks),
 revenue REAL NOT NULL CHECK(revenue>=0), UNIQUE(campaign_id,date)
);
CREATE TABLE leads (
 id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
 customer_segment TEXT NOT NULL CHECK(customer_segment IN ('SMB','Enterprise')),
 status TEXT NOT NULL CHECK(status IN ('new','qualified','won','lost')),
 deal_value REAL NOT NULL CHECK(deal_value>=0), created_at TEXT NOT NULL
);
"""
# Daily profile: impressions, clicks, spend, conversions, revenue.
PROFILES = [
    ("Summer_Sale", "google_ads", "conversion", 100, "active", (1000, 80, 30, 8, 144)),
    (
        "Summer_Clearance",
        "instagram",
        "conversion",
        90,
        "active",
        (1500, 45, 40, 1, 32),
    ),
    ("Brand_Reach", "linkedin", "brand_awareness", 70, "active", (1000, 22, 12, 0, 0)),
    ("Brand_Recall", "instagram", "brand_awareness", 50, "active", (1000, 10, 8, 0, 0)),
    ("Launch_Queue", "email", "retargeting", 20, "paused", (0, 0, 0, 0, 0)),
    ("Trial_Search", "google_ads", "conversion", 25, "active", (500, 20, 5, 1, 4)),
    ("Renewal_Email", "email", "retargeting", 50, "active", (800, 60, 10, 5, 45)),
    ("Winter_Archive", "linkedin", "conversion", 60, "ended", (700, 35, 20, 2, 40)),
]


def seed(path, today=None, *, if_missing=False):
    if if_missing and path.exists():
        return False
    today = today or date.today()
    rng = random.Random(42)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    os.close(fd)
    try:
        conn = sqlite3.connect(temp)
        try:
            conn.executescript(SCHEMA)
            for cid, (*campaign, profile) in enumerate(PROFILES, 1):
                start = today - timedelta(days=44)
                conn.execute(
                    "INSERT INTO campaigns VALUES(?,?,?,?,?,?,?)",
                    (cid, *campaign, start.isoformat()),
                )
                for offset in range(45):
                    day = today - timedelta(days=offset)
                    if campaign[4] == "ended" and offset < 30:
                        continue
                    multiplier = rng.choice([1, 1, 2])
                    values = [x * multiplier for x in profile]
                    conn.execute(
                        "INSERT INTO daily_metrics VALUES(NULL,?,?,?,?,?,?,?)",
                        (cid, day.isoformat(), *values),
                    )
                if any(profile):
                    for segment in ("SMB", "Enterprise"):
                        for status in ("new", "qualified", "won", "lost"):
                            conn.execute(
                                "INSERT INTO leads VALUES(NULL,?,?,?,?,?)",
                                (
                                    cid,
                                    segment,
                                    status,
                                    rng.randrange(1, 15) * 100,
                                    start.isoformat(),
                                ),
                            )
            conn.commit()
        finally:
            conn.close()
        if if_missing:
            try:
                os.link(temp, path)
            except FileExistsError:
                return False
        else:
            os.replace(temp, path)
        return True
    finally:
        Path(temp).unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("marketing.db"))
    parser.add_argument("--if-missing", action="store_true")
    args = parser.parse_args()
    if seed(args.db, if_missing=args.if_missing):
        print(f"Created {args.db}")
