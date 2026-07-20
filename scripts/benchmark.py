import argparse
import json
import statistics
import time
from pathlib import Path

from src.api.dependencies import get_service, set_database
from src.config.settings import get_settings
from src.database.connection import Database

parser = argparse.ArgumentParser()
parser.add_argument("query")
parser.add_argument("--runs", type=int, default=20)
args = parser.parse_args()
database = Database(get_settings().database_url)
database.open()
set_database(database)
try:
    service = get_service()
    service.search(args.query)
    timings = []
    for _ in range(args.runs):
        start = time.perf_counter()
        service.search(args.query)
        timings.append((time.perf_counter() - start) * 1000)
    report = {"runs": args.runs, "mean_ms": statistics.mean(timings),
              "p95_ms": sorted(timings)[max(0, int(args.runs * .95) - 1)]}
    Path("benchmark-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
finally:
    database.close()

