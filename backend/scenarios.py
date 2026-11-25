import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from agent import run
from database import query
from planner import QUESTIONS
from seed_db import seed

EXPECTED = dict(
    scale="R2 | Scale",
    pause="R1 | Pause",
    awareness="R3 | Healthy",
    review="R3 | Review",
    ambiguous="Which campaign",
    security="Blocked",
    zero="undefined",
    hold="Fallback | Hold",
    retry="revenue:",
    outside="supports campaign",
    missing="No campaign matches",
    awareness_scope="Brand_Reach | R3 | Healthy",
    zero_conversions="Brand_Recall",
    active_scale="Summer_Sale | R2 | Scale",
    compound_ranking="name: Summer_Clearance | spend:",
    retry_limit="Unable to complete the query after 3 attempt(s)",
)


def main():
    logs = Path(__file__).parent / "logs"
    logs.mkdir(exist_ok=True)
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "marketing.db"
        seed(db)
        for key, question in QUESTIONS.items():
            events = []
            answer = run(question, db, True, events.append)
            if key == "ranking":
                with sqlite3.connect(db) as conn:
                    expected = conn.execute("""SELECT c.channel FROM campaigns c JOIN daily_metrics m
                      ON c.id=m.campaign_id WHERE m.date BETWEEN date('now','localtime','-29 days')
                      AND date('now','localtime') GROUP BY c.channel
                      ORDER BY 1.0*SUM(revenue)/NULLIF(SUM(spend),0) DESC LIMIT 1""").fetchone()[
                        0
                    ]
            else:
                expected = EXPECTED[key]
            assert expected in answer, (key, answer, expected)
            if key == "awareness_scope":
                assert "Winter_Archive" not in answer and "Brand_Recall" not in answer
            if key == "zero_conversions":
                assert "Brand_Reach" in answer and "Launch_Queue" not in answer
            if key == "active_scale":
                assert "Renewal_Email | R2 | Scale" in answer
                assert answer.count("\n") == 2
            if key == "compound_ranking":
                assert "channel: email | roas:" in answer
            if key == "retry_limit":
                assert [e["attempt"] for e in events if "attempt" in e] == [1, 2, 3]
            if key == "retry":
                assert [e["attempt"] for e in events if "attempt" in e] == [1, 2]
                assert any("no such column" in e.get("error", "") for e in events)
            if key == "security":
                before = hashlib.sha256(db.read_bytes()).hexdigest()
                for sql in (
                    "DELETE FROM campaigns WHERE id=1",
                    "DROP TABLE daily_metrics",
                    "UPDATE campaigns SET daily_budget=100 WHERE id=1",
                    "INSERT INTO campaigns SELECT * FROM campaigns WHERE 0",
                ):
                    try:
                        query(db, sql)
                    except sqlite3.DatabaseError as exc:
                        assert exc.sqlite_errorcode == sqlite3.SQLITE_AUTH
                        events.append(
                            dict(sql=sql, layer="SQLite authorizer", result=str(exc))
                        )
                    else:
                        raise AssertionError("Write was permitted")
                after = hashlib.sha256(db.read_bytes()).hexdigest()
                assert before == after
                events.append(dict(before_sha256=before, after_sha256=after))
            events.append(dict(expected=expected, result="PASS"))
            (logs / f"{key}.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in events)
            )
            print(f"PASS {key}")


if __name__ == "__main__":
    main()
