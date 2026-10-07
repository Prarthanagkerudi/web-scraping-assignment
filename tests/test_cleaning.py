from processing.cleaning import (
    clean_book, clean_price, clean_quote, clean_rating, clean_tags,
    clean_text, normalize_url, strip_quotes,
)


def test_clean_text_collapses_whitespace():
    assert clean_text("  Hello \n  World ") == "Hello World"
    assert clean_text("a\xa0b\tc") == "a b c"


def test_clean_text_empty_becomes_none():
    assert clean_text("   ") is None
    assert clean_text(None) is None


def test_strip_quotes():
    assert strip_quotes("\u201cThe world as we have created it.\u201d") == "The world as we have created it."
    assert strip_quotes('"plain"') == "plain"


def test_clean_price():
    assert clean_price("\u00a351.77") == 51.77
    assert clean_price("\u00c2\u00a351.77") == 51.77      # wrong-encoding pound sign
    assert clean_price("\u00a31,051.00") == 1051.0
    assert clean_price("free") is None
    assert clean_price(None) is None


def test_clean_rating():
    assert clean_rating("star-rating Three") == 3
    assert clean_rating("Five") == 5
    assert clean_rating("star-rating") is None
    assert clean_rating(None) is None


def test_clean_tags_lowercase_sort_join_dedupe():
    assert clean_tags(["Love", " books ", "love", ""]) == "books;love"
    assert clean_tags([]) is None


def test_normalize_url():
    assert normalize_url("catalogue/x/index.html", base="https://books.toscrape.com/") == \
        "https://books.toscrape.com/catalogue/x/index.html"
    assert normalize_url("  https://a.com/x ") == "https://a.com/x"
    assert normalize_url("not a url") is None
    assert normalize_url(None) is None


def test_clean_book_full_record():
    raw = {"source_url": "https://books.toscrape.com/a/index.html", "title": "  A  Light \xa0in the Attic ",
           "price_raw": "\u00a351.77", "rating_raw": "star-rating Three",
           "category_raw": " Poetry ", "description_raw": None, "scraped_at": "2026-10-06T10:00:00Z"}
    rec = clean_book(raw)
    assert rec["name_or_title"] == "A Light in the Attic"
    assert rec["price"] == 51.77 and rec["rating"] == 3
    assert rec["category"] == "Poetry"
    assert rec["author"] is None and rec["tags"] is None and rec["description"] is None


def test_clean_book_keeps_unparseable_price_so_validation_can_reject_it():
    rec = clean_book({"source_url": "https://x.com", "title": "T", "price_raw": "n/a", "rating_raw": "Zero"})
    assert rec["price"] == "n/a"
    assert rec["rating"] == "Zero"


def test_clean_quote_record():
    raw = {"source_url": "https://quotes.toscrape.com/", "text_raw": "\u201c Be   yourself. \u201d",
           "author_raw": " Oscar Wilde ", "tags_raw": ["Life", "inspirational"], "scraped_at": "t"}
    rec = clean_quote(raw)
    assert rec["name_or_title"] == "Be yourself."
    assert rec["author"] == "Oscar Wilde"
    assert rec["tags"] == "inspirational;life"
    assert rec["price"] is None and rec["rating"] is None
