"""Shared networking and pagination logic for all scrapers.

Anything that touches the internet lives in the scrapers/ package.
"""
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

USER_AGENT = "ScrapingAssignment/1.0 (learning project)"
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]


def create_session() -> requests.Session:
    """One session with a User-Agent and automatic retries (waits 1s, 2s, 4s)."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=RETRY_STATUS_CODES,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BaseScraper:
    """Subclasses set source_name/start_url and implement parse_page()."""

    source_name = ""
    start_url = ""

    def __init__(self, session=None, delay=0.5, timeout=10, max_pages=None):
        self.session = session or create_session()
        self.delay = delay
        self.timeout = timeout
        self.max_pages = max_pages
        self.records = []  # filled page by page, so partial results survive a crash
        self.stats = {"pages_fetched": 0, "pages_failed": 0, "parse_errors": 0}
        self._last_request = 0.0

    # ---- networking -------------------------------------------------
    def _pause(self):
        """Rate limit: wait so there are at least `delay` seconds between requests."""
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

    def get_soup(self, url):
        """Download a page and return a BeautifulSoup object, or None on failure."""
        self._pause()
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()  # raises on 404, 500, ...
            response.encoding = "utf-8"  # keeps the pound sign correct
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            return None
        finally:
            self._last_request = time.monotonic()

    # ---- pagination -------------------------------------------------
    @staticmethod
    def find_next_url(soup, current_url):
        """Return the absolute URL of the 'next' page, or None on the last page."""
        next_link = soup.select_one("li.next > a")
        if next_link is None or not next_link.get("href"):
            return None
        return urljoin(current_url, next_link["href"])

    def parse_page(self, soup, page_url):
        """Return a list of raw dictionaries found on one page."""
        raise NotImplementedError

    def scrape(self):
        """Follow the 'next' link until there is none. Never hard-codes page numbers."""
        self.records = []
        url, page, visited = self.start_url, 1, set()
        while url and url not in visited:
            if self.max_pages and page > self.max_pages:
                logger.info("[%s] Reached max_pages=%d, stopping.", self.source_name, self.max_pages)
                break
            visited.add(url)
            logger.info("[%s] Page %d: %s", self.source_name, page, url)
            soup = self.get_soup(url)
            if soup is None:
                self.stats["pages_failed"] += 1
                logger.error(
                    "[%s] Page %d failed after retries. Stopping this source; "
                    "%d records kept so far.", self.source_name, page, len(self.records),
                )
                break
            self.stats["pages_fetched"] += 1
            page_records = self.parse_page(soup, url)
            self.records.extend(page_records)
            logger.info("[%s] Page %d: %d records (total %d)",
                        self.source_name, page, len(page_records), len(self.records))
            url = self.find_next_url(soup, url)
            page += 1
        return self.records
