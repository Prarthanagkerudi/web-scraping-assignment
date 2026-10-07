"""Entry point: python main.py

Pipeline: scrape (both sites) -> clean -> validate -> deduplicate -> consolidate -> save files.
"""
import argparse
import csv
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from processing.cleaning import clean_record
from processing.deduplication import find_duplicates
from processing.validation import REASONS, validate_record
from schema import COLUMNS
from scrapers.base_scraper import create_session
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = BASE_DIR / "logs" / "scraper.log"

logger = logging.getLogger("main")


def setup_logging(log_file=LOG_FILE):
    """Log to the console and to logs/scraper.log (overwritten on every run)."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    console = logging.StreamHandler()
    for handler in (file_handler, console):
        handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)


# ---------------------------------------------------------------- stages
def clean_and_validate(raw_records):
    """Clean every raw record, then validate it. Bad records are rejected, not fatal.

    Returns (valid_records, rejected) where rejected is a list of
    {"source", "name", "reasons"} dictionaries.
    """
    valid, rejected = [], []
    for raw in raw_records:
        source = raw.get("source")
        name = raw.get("title") or raw.get("text_raw")
        try:
            record = clean_record(raw)
        except Exception as exc:
            logger.warning("Rejected %r from %s: cleaning_error (%s)", name, source, exc)
            rejected.append({"source": source, "name": name, "reasons": ["cleaning_error"]})
            continue
        problems = validate_record(record)
        if problems:
            logger.warning("Rejected %r from %s: %s", name, source, ", ".join(problems))
            rejected.append({"source": source, "name": name, "reasons": problems})
        else:
            valid.append(record)
    return valid, rejected


def write_csv(records, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)  # None is written as an empty cell


def count_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def write_summary(stats, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)


# -------------------------------------------------------------- pipeline
def run_pipeline(scrapers, output_dir=OUTPUT_DIR, settings=None):
    """Run every stage and write final_dataset.csv and summary_report.json."""
    started = datetime.now(timezone.utc)
    timer = time.perf_counter()
    sources = [s.source_name for s in scrapers]

    # 1. Scrape. Each source has its own try/except so one failure does not stop the other.
    raw_records, failed_sources = [], []
    for scraper in scrapers:
        try:
            scraper.scrape()
        except Exception:
            logger.exception("Source %s crashed; keeping the records it had collected.",
                             scraper.source_name)
            failed_sources.append(scraper.source_name)
        if not scraper.records and scraper.source_name not in failed_sources:
            failed_sources.append(scraper.source_name)
        raw_records.extend(scraper.records)
        logger.info("%s: %d raw records collected", scraper.source_name, len(scraper.records))

    # 2-3. Clean and validate
    valid, rejected = clean_and_validate(raw_records)
    # 4. Deduplicate (duplicates are removed, and counted and logged)
    unique, dupes = find_duplicates(valid)
    for rec in dupes:
        logger.warning("Duplicate removed: %r from %s", rec["name_or_title"], rec["source"])

    # 5-6. Consolidate and save
    csv_path = Path(output_dir) / "final_dataset.csv"
    write_csv(unique, csv_path)
    csv_rows = count_csv_rows(csv_path)

    # Summary
    collected = Counter(r.get("source") for r in raw_records)
    rejected_n = Counter(r["source"] for r in rejected)
    cleaning_errors = Counter(r["source"] for r in rejected if "cleaning_error" in r["reasons"])
    dupes_n = Counter(r["source"] for r in dupes)
    final_n = Counter(r["source"] for r in unique)
    reasons = Counter({reason: 0 for reason in REASONS})
    for r in rejected:
        reasons.update(r["reasons"])  # a record with 2 problems counts once per reason

    per_source = {}
    for s in scrapers:
        name = s.source_name
        per_source[name] = {
            "collected": collected[name],
            "scrape_parse_errors": s.stats["parse_errors"],
            "pages_fetched": s.stats["pages_fetched"],
            "pages_failed": s.stats["pages_failed"],
            "cleaned": collected[name] - cleaning_errors[name],
            "rejected": rejected_n[name],
            "duplicates": dupes_n[name],
            "final": final_n[name],
        }

    total_collected = sum(collected.values())
    reconciles = (
        total_collected - len(rejected) - len(dupes) == len(unique) == csv_rows
        and all(v["collected"] - v["rejected"] - v["duplicates"] == v["final"]
                for v in per_source.values())
    )
    finished = datetime.now(timezone.utc)
    stats = {
        "collected_per_source": {n: per_source[n]["collected"] for n in sources},
        "cleaned_per_source": {n: per_source[n]["cleaned"] for n in sources},
        "rejected_total": len(rejected),
        "rejected_by_reason": dict(reasons),
        "duplicates_detected": len(dupes),
        "final_record_count": len(unique),
        "final_per_source": {n: per_source[n]["final"] for n in sources},
        "start_time": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": round(time.perf_counter() - timer, 1),
        "per_source_details": per_source,
        "failed_sources": failed_sources,
        "settings": settings or {},
        "reconciliation": {
            "rule": "collected - rejected - duplicates = final = rows in final_dataset.csv",
            "csv_rows": csv_rows,
            "ok": reconciles,
        },
    }
    write_summary(stats, Path(output_dir) / "summary_report.json")
    return stats


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Scrape, clean and consolidate two practice sites.")
    parser.add_argument("--no-details", action="store_true",
                        help="skip the ~1,000 book detail pages (faster; category/description stay empty)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="stop each source after N listing pages (handy for a quick test)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="seconds to pause between requests (default 0.5)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # avoid Windows console encoding errors
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    setup_logging()
    logger.info("Starting run (details=%s, max_pages=%s, delay=%s)",
                not args.no_details, args.max_pages, args.delay)

    session = create_session()  # one session shared by both scrapers
    common = {"session": session, "delay": args.delay, "max_pages": args.max_pages}
    scrapers = [
        BooksScraper(fetch_details=not args.no_details, **common),
        QuotesScraper(**common),
    ]
    settings = {"fetch_book_details": not args.no_details,
                "max_pages": args.max_pages, "delay_seconds": args.delay}
    stats = run_pipeline(scrapers, settings=settings)

    logger.info("Finished in %.1fs: collected=%s rejected=%d duplicates=%d final=%d",
                stats["duration_seconds"], stats["collected_per_source"],
                stats["rejected_total"], stats["duplicates_detected"], stats["final_record_count"])
    logger.info("Reconciliation OK: %s", stats["reconciliation"]["ok"])
    return 0 if stats["final_record_count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
