"""Books to Scrape: selectors, pagination start point and detail-page parsing."""
import logging
from urllib.parse import urljoin

from schema import SOURCE_BOOKS
from scrapers.base_scraper import BaseScraper, utc_now_iso

logger = logging.getLogger(__name__)


def parse_book(article, page_url):
    """Build a raw dictionary from one <article class="product_pod">.

    A missing element gives None instead of crashing (select_one returns None).
    """
    link = article.select_one("h3 > a")
    price = article.select_one("p.price_color")
    rating = article.select_one("p.star-rating")
    href = link.get("href") if link else None
    return {
        "source": SOURCE_BOOKS,
        "source_url": urljoin(page_url, href) if href else None,
        # the visible text is cut off with "...", the full title is in the title attribute
        "title": (link.get("title") or link.get_text()) if link else None,
        "price_raw": price.get_text() if price else None,
        # class is a list like ['star-rating', 'Three']
        "rating_raw": " ".join(rating.get("class", [])) if rating else None,
        "category_raw": None,
        "description_raw": None,
        "scraped_at": utc_now_iso(),
    }


def parse_book_details(soup):
    """Return (category, description) from a book detail page; None if missing."""
    crumbs = soup.select("ul.breadcrumb li a")  # Home > Books > <Category>
    category = crumbs[2].get_text() if len(crumbs) >= 3 else None
    desc = soup.select_one("#product_description + p")
    return category, (desc.get_text() if desc else None)


class BooksScraper(BaseScraper):
    source_name = SOURCE_BOOKS
    start_url = "https://books.toscrape.com/"

    def __init__(self, *args, fetch_details=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fetch_details = fetch_details
        self._details_done = 0

    def parse_page(self, soup, page_url):
        records = []
        for article in soup.select("article.product_pod"):
            try:
                records.append(parse_book(article, page_url))
            except Exception as exc:  # one bad record must not stop the page
                self.stats["parse_errors"] += 1
                logger.warning("[%s] Skipped a record on %s: %s", self.source_name, page_url, exc)
        if self.fetch_details:
            for record in records:
                self._add_details(record)
        return records

    def _add_details(self, record):
        """Visit the book's own page to get category and description."""
        url = record.get("source_url")
        if not url:
            return
        soup = self.get_soup(url)
        self._details_done += 1
        if self._details_done % 100 == 0:
            logger.info("[%s] Detail pages done: %d", self.source_name, self._details_done)
        if soup is None:
            logger.warning("[%s] No detail page for %s; category/description left empty.",
                           self.source_name, url)
            return
        try:
            record["category_raw"], record["description_raw"] = parse_book_details(soup)
        except Exception as exc:
            self.stats["parse_errors"] += 1
            logger.warning("[%s] Could not parse details of %s: %s", self.source_name, url, exc)
