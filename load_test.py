"""Exercise the HTTP API with concurrent offline ranking questions."""

import argparse
import json
import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from planner import QUESTIONS


def probe(url):
    payload = {"question": QUESTIONS["ranking"], "offline": True}
    request = Request(url, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urlopen(request, timeout=30) as response:
            answer = json.load(response)["answer"]
            if "channel:" not in answer or "roas:" not in answer:
                raise ValueError("Expected a channel ranking")
            status = response.status
    except HTTPError as error:
        if error.code != 503 or not error.headers.get("Retry-After"):
            raise
        status = error.code
    return status, time.monotonic() - started


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/questions")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--clients", type=int, default=12)
    args = parser.parse_args()
    if min(args.requests, args.clients) < 1:
        parser.error("Requests and clients must be positive")
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.clients) as pool:
        samples = list(pool.map(probe, [args.url] * args.requests))
    elapsed = time.monotonic() - started
    counts = Counter(status for status, _ in samples)
    completed = sorted(duration for status, duration in samples if status == 200)
    if completed:
        p95 = completed[math.ceil(len(completed) * 0.95) - 1]
        print(f"Successful request p95: {p95 * 1000:.0f} ms")
    print(f"Successful: {counts[200]}, busy: {counts[503]}, "
          f"successful requests/s: {counts[200] / elapsed:.1f}")
    raise SystemExit(0 if counts[200] else 1)
