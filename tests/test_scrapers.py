"""Scraper tests use fake pages and a fake session, so they need no internet."""
import requests

from scrapers.books_scraper import BooksScraper, parse_book_details
from scrapers.quotes_scraper import QuotesScraper

BOOKS_P1 = """<html><body>
<article class="product_pod"><h3><a href="catalogue/book-one_1/index.html" title="Book One Full Title">Book One F...</a></h3>
<p class="star-rating Three"></p><div><p class="price_color">\u00a351.77</p></div></article>
<article class="product_pod"><h3><a href="catalogue/book-two_2/index.html" title="Book Two">Book Two</a></h3>
<p class="star-rating One"></p></article>
<ul class="pager"><li class="next"><a href="catalogue/page-2.html">next</a></li></ul></body></html>"""

BOOKS_P2 = """<html><body>
<article class="product_pod"><h3><a href="book-three_3/index.html" title="Book Three">Book Three</a></h3>
<p class="star-rating Five"></p><p class="price_color">\u00a310.00</p></article></body></html>"""

BOOK_DETAIL = """<html><body><ul class="breadcrumb"><li><a href="/">Home</a></li><li><a href="/b">Books</a></li>
<li><a href="/p">Poetry</a></li><li class="active">Book One</li></ul>
<div id="product_description" class="sub-header"><h2>Product Description</h2></div><p>A lovely description.</p></body></html>"""

QUOTES_P1 = """<html><body>
<div class="quote"><span class="text">\u201cQuote one.\u201d</span><span>by <small class="author">Author A</small></span>
<div class="tags"><a class="tag" href="/t/1">life</a><a class="tag" href="/t/2">love</a></div></div>
<div class="quote"><span class="text">\u201cNo author here.\u201d</span><div class="tags"></div></div>
<nav><ul class="pager"><li class="next"><a href="/page/2/">Next</a></li></ul></nav></body></html>"""

QUOTES_P2 = """<html><body><div class="quote"><span class="text">\u201cQuote three.\u201d</span>
<small class="author">Author C</small></div></body></html>"""


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code, self.encoding = text, status, None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeSession:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get(self, url, timeout=None):
        self.calls.append(url)
        if url not in self.pages:
            raise requests.ConnectionError("network down")
        page = self.pages[url]
        return page if isinstance(page, FakeResponse) else FakeResponse(page)


BOOKS_HOME = "https://books.toscrape.com/"
BOOKS_PAGES = {BOOKS_HOME: BOOKS_P1, "https://books.toscrape.com/catalogue/page-2.html": BOOKS_P2}
QUOTES_HOME = "https://quotes.toscrape.com/"
QUOTES_PAGES = {QUOTES_HOME: QUOTES_P1, "https://quotes.toscrape.com/page/2/": QUOTES_P2}


def test_books_pagination_follows_next_link_and_resolves_relative_urls():
    s = BooksScraper(session=FakeSession(BOOKS_PAGES), delay=0, fetch_details=False)
    records = s.scrape()
    assert len(records) == 3
    assert records[0]["title"] == "Book One Full Title"  # from the title attribute, not the cut-off text
    assert records[0]["source_url"] == "https://books.toscrape.com/catalogue/book-one_1/index.html"
    assert records[2]["source_url"] == "https://books.toscrape.com/catalogue/book-three_3/index.html"
    assert records[0]["price_raw"] == "\u00a351.77" and records[0]["rating_raw"] == "star-rating Three"
    assert s.stats["pages_fetched"] == 2


def test_missing_price_does_not_crash():
    s = BooksScraper(session=FakeSession(BOOKS_PAGES), delay=0, fetch_details=False)
    assert s.scrape()[1]["price_raw"] is None  # Book Two has no price element


def test_book_detail_parsing():
    category, description = parse_book_details(__import__("bs4").BeautifulSoup(BOOK_DETAIL, "lxml"))
    assert category == "Poetry" and description == "A lovely description."


def test_book_detail_missing_elements_give_none():
    category, description = parse_book_details(__import__("bs4").BeautifulSoup("<html></html>", "lxml"))
    assert category is None and description is None


def test_books_with_details():
    pages = dict(BOOKS_PAGES)
    pages["https://books.toscrape.com/catalogue/book-one_1/index.html"] = BOOK_DETAIL
    s = BooksScraper(session=FakeSession(pages), delay=0, fetch_details=True)
    records = s.scrape()
    assert records[0]["category_raw"] == "Poetry"
    assert records[1]["category_raw"] is None  # its detail page failed: kept, left empty
    assert len(records) == 3


def test_quotes_pagination_and_missing_author():
    s = QuotesScraper(session=FakeSession(QUOTES_PAGES), delay=0)
    records = s.scrape()
    assert len(records) == 3
    assert records[0]["tags_raw"] == ["life", "love"]
    assert records[1]["author_raw"] is None  # missing element -> None, no crash
    assert records[2]["source_url"] == "https://quotes.toscrape.com/page/2/"


def test_failed_page_stops_that_source_but_keeps_earlier_records():
    session = FakeSession({QUOTES_HOME: QUOTES_P1})  # page 2 raises ConnectionError
    s = QuotesScraper(session=session, delay=0)
    records = s.scrape()
    assert len(records) == 2
    assert s.stats["pages_failed"] == 1


def test_http_error_is_handled():
    session = FakeSession({QUOTES_HOME: FakeResponse("boom", status=500)})
    s = QuotesScraper(session=session, delay=0)
    assert s.scrape() == [] and s.stats["pages_failed"] == 1


def test_max_pages_limits_pagination():
    s = QuotesScraper(session=FakeSession(QUOTES_PAGES), delay=0, max_pages=1)
    assert len(s.scrape()) == 2
