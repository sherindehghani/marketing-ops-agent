import argparse
import json
import sys
from pathlib import Path
from agent import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze campaign performance and budget policy."
    )
    parser.add_argument("question")
    parser.add_argument("--db", type=Path, default=Path("marketing.db"))
    parser.add_argument(
        "--offline", action="store_true", help="Use documented English test fixtures"
    )
    parser.add_argument(
        "--trace", action="store_true", help="Write JSON events to stderr"
    )
    args = parser.parse_args()

    def trace(event):
        if args.trace:
            print(json.dumps(event), file=sys.stderr)

    try:
        print(run(args.question, args.db, args.offline, trace))
    except Exception as exc:
        parser.exit(1, f"Agent failed: {exc}\n")
