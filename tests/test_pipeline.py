"""End-to-end test of the pipeline stages using fake scrapers (no internet)."""
import csv
import json

from main import run_pipeline
from schema import COLUMNS


class FakeScraper:
    def __init__(self, source_name, records):
        self.source_name = source_name
        self.records = records
        self.stats = {"pages_fetched": 1, "pages_failed": 0, "parse_errors": 0}

    def scrape(self):
        return self.records


class CrashingScraper(FakeScraper):
    def scrape(self):
        raise RuntimeError("boom")


def book(title, price="\u00a310.00", rating="star-rating Four", url="https://books.toscrape.com/x/index.html"):
    return {"source": "Books to Scrape", "source_url": url, "title": title, "price_raw": price,
            "rating_raw": rating, "category_raw": "Fiction", "description_raw": None, "scraped_at": "t"}


def quote(text, author="Someone"):
    return {"source": "Quotes to Scrape", "source_url": "https://quotes.toscrape.com/", "text_raw": text,
            "author_raw": author, "tags_raw": ["a", "b"], "scraped_at": "t"}


def test_pipeline_outputs_reconcile(tmp_path):
    books = [book("Good Book"), book("good  book "), book("Bad Price", price="n/a"),
             book("Bad Url", url="javascript:void(0)"), book("")]
    quotes = [quote("\u201cHello there.\u201d"), quote("\u201cHello there.\u201d"), quote("\u201cAnother.\u201d")]
    stats = run_pipeline([FakeScraper("Books to Scrape", books), FakeScraper("Quotes to Scrape", quotes)],
                         output_dir=tmp_path)

    assert stats["collected_per_source"] == {"Books to Scrape": 5, "Quotes to Scrape": 3}
    assert stats["duplicates_detected"] == 2
    assert stats["rejected_total"] == 3
    assert stats["rejected_by_reason"]["invalid_price"] == 1
    assert stats["rejected_by_reason"]["invalid_url"] == 1
    assert stats["rejected_by_reason"]["missing_name"] == 1
    assert stats["final_record_count"] == 3
    assert stats["reconciliation"]["ok"] is True

    with open(tmp_path / "final_dataset.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == stats["final_record_count"] == 3
    assert list(rows[0].keys()) == COLUMNS
    assert {r["source"] for r in rows} == {"Books to Scrape", "Quotes to Scrape"}
    assert rows[0]["price"] == "10.0" and rows[2]["price"] == ""   # quotes have an empty price cell

    saved = json.loads((tmp_path / "summary_report.json").read_text(encoding="utf-8"))
    assert saved["final_record_count"] == 3


def test_one_source_crashing_does_not_stop_the_other(tmp_path):
    stats = run_pipeline([CrashingScraper("Books to Scrape", []),
                          FakeScraper("Quotes to Scrape", [quote("\u201cStill works.\u201d")])],
                         output_dir=tmp_path)
    assert stats["failed_sources"] == ["Books to Scrape"]
    assert stats["final_record_count"] == 1
    assert stats["reconciliation"]["ok"] is True
