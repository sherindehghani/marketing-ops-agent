import argparse
import json
import os
import sys
from pathlib import Path
from agent import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze campaign performance and budget policy."
    )
    parser.add_argument("question")
    parser.add_argument(
        "--db", type=Path, default=Path(os.getenv("MARKETING_DB", "marketing.db"))
    )
    parser.add_argument(
        "--offline", action="store_true", help="Use documented test fixtures"
    )
    parser.add_argument(
        "--trace", action="store_true", help="Write JSON events to stderr"
    )
    parser.add_argument("--language", choices=["en", "fa", "both"], default="en")
    args = parser.parse_args()

    def trace(event):
        if args.trace:
            print(json.dumps(event), file=sys.stderr)

    try:
        if not args.db.is_file():
            parser.exit(1, f"Database not found at {args.db}. Run seed_db.py first.\n")
        result = run(args.question, args.db, args.offline, trace, bilingual=True)
        if args.language in ("en", "both"):
            print(result["answer"])
        if args.language in ("fa", "both"):
            print(result["answer_fa"])
    except Exception as exc:
        parser.exit(1, f"Agent failed: {exc}\n")
