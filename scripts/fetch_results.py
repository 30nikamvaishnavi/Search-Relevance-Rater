"""Fetch DuckDuckGo text results for queries without saved results."""

import csv
import logging
import random
import time
from pathlib import Path
from typing import Any

from ddgs import DDGS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERIES_PATH = PROJECT_ROOT / "data" / "queries.csv"
RESULTS_PATH = PROJECT_ROOT / "data" / "results.csv"
ERROR_LOG_PATH = PROJECT_ROOT / "fetch_errors.log"
QUERY_COLUMNS = ("query_id", "language", "query", "intent")
RESULT_COLUMNS = ("query_id", "rank", "title", "url", "snippet")
REGION = "in-en"
MAX_RESULTS = 5
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 2


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("fetch_results")
    logger.setLevel(logging.WARNING)
    if not logger.handlers:
        handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def _load_queries() -> list[dict[str, str]]:
    with QUERIES_PATH.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(QUERY_COLUMNS):
            raise ValueError(f"{QUERIES_PATH} must have columns {', '.join(QUERY_COLUMNS)}")
        return list(reader)


def _load_existing_query_ids() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()

    with RESULTS_PATH.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(RESULT_COLUMNS):
            raise ValueError(f"{RESULTS_PATH} must have columns {', '.join(RESULT_COLUMNS)}")
        return {row["query_id"] for row in reader if row.get("query_id")}


def _append_results(query_id: str, results: list[dict[str, Any]]) -> None:
    with RESULTS_PATH.open("a", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=RESULT_COLUMNS)
        if RESULTS_PATH.stat().st_size == 0:
            writer.writeheader()
        rows = []
        for rank, result in enumerate(results[:MAX_RESULTS], start=1):
            rows.append(
                {
                    "query_id": query_id,
                    "rank": rank,
                    "title": result.get("title") or "",
                    "url": result.get("href") or result.get("url") or "",
                    "snippet": result.get("body") or result.get("snippet") or "",
                }
            )
        writer.writerows(rows)


def _fetch_query(client: DDGS, query_id: str, query: str, logger: logging.Logger) -> list[dict[str, Any]]:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return client.text(query, region=REGION, max_results=MAX_RESULTS)
        except Exception as error:
            logger.warning(
                "Attempt %d/%d failed for query_id=%s query=%r: %s",
                attempt,
                MAX_ATTEMPTS,
                query_id,
                query,
                error,
            )
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(BACKOFF_SECONDS * (2 ** (attempt - 1)))

    raise RuntimeError(f"Search attempts exhausted for query_id={query_id}")


def main() -> int:
    logger = _configure_logging()
    queries = _load_queries()
    completed_query_ids = _load_existing_query_ids()
    pending = [row for row in queries if row["query_id"] not in completed_query_ids]
    failures: list[str] = []

    if not pending:
        print("All queries already have results; nothing to fetch.")
        return 0

    with DDGS(timeout=12) as client:
        for index, row in enumerate(pending):
            query_id = row["query_id"]
            query = row["query"]
            try:
                results = _fetch_query(client, query_id, query, logger)
            except Exception as error:
                logger.error(
                    "Giving up on query_id=%s query=%r after %d attempts: %s",
                    query_id,
                    query,
                    MAX_ATTEMPTS,
                    error,
                )
                failures.append(query_id)
                print(f"Failed to fetch {query_id} after {MAX_ATTEMPTS} attempts.")
            else:
                _append_results(query_id, results)
                print(f"Fetched {len(results[:MAX_RESULTS])} results for {query_id}.")

            if index < len(pending) - 1:
                time.sleep(random.uniform(2.0, 3.0))

    if failures:
        print(f"Failed queries: {', '.join(failures)}. See fetch_errors.log.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
