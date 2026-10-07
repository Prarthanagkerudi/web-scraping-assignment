"""Quotes to Scrape: selectors and per-quote parsing."""
import logging

from schema import SOURCE_QUOTES
from scrapers.base_scraper import BaseScraper, utc_now_iso

logger = logging.getLogger(__name__)


def parse_quote(div, page_url):
    """Build a raw dictionary from one <div class="quote">."""
    text = div.select_one("span.text")
    author = div.select_one("small.author")
    return {
        "source": SOURCE_QUOTES,
        "source_url": page_url,  # the listing page where the quote appeared
        "text_raw": text.get_text() if text else None,
        "author_raw": author.get_text() if author else None,
        "tags_raw": [a.get_text() for a in div.select("a.tag")],  # zero or more
        "scraped_at": utc_now_iso(),
    }


class QuotesScraper(BaseScraper):
    source_name = SOURCE_QUOTES
    start_url = "https://quotes.toscrape.com/"

    def parse_page(self, soup, page_url):
        records = []
        for div in soup.select("div.quote"):
            try:
                records.append(parse_quote(div, page_url))
            except Exception as exc:
                self.stats["parse_errors"] += 1
                logger.warning("[%s] Skipped a record on %s: %s", self.source_name, page_url, exc)
        return records
