from processing.validation import validate_record

BOOK = {"source": "Books to Scrape", "source_url": "https://books.toscrape.com/x", "name_or_title": "T",
        "price": 10.5, "rating": 4}
QUOTE = {"source": "Quotes to Scrape", "source_url": "https://quotes.toscrape.com/", "name_or_title": "Q",
         "price": None, "rating": None, "author": "A"}


def test_valid_records_have_no_problems():
    assert validate_record(BOOK) == []
    assert validate_record(QUOTE) == []


def test_unknown_source():
    assert "unknown_source" in validate_record({**BOOK, "source": "Other"})


def test_missing_name():
    assert "missing_name" in validate_record({**BOOK, "name_or_title": None})
    assert "missing_name" in validate_record({**BOOK, "name_or_title": ""})


def test_invalid_url():
    assert "invalid_url" in validate_record({**BOOK, "source_url": "ftp://x"})
    assert "invalid_url" in validate_record({**BOOK, "source_url": None})


def test_invalid_price():
    assert "invalid_price" in validate_record({**BOOK, "price": -1})
    assert "invalid_price" in validate_record({**BOOK, "price": "n/a"})
    assert validate_record({**BOOK, "price": 0}) == []


def test_invalid_rating():
    assert "invalid_rating" in validate_record({**BOOK, "rating": 6})
    assert "invalid_rating" in validate_record({**BOOK, "rating": 0})
    assert "invalid_rating" in validate_record({**BOOK, "rating": "Zero"})


def test_several_problems_are_all_reported():
    problems = validate_record({"source": "x", "source_url": "", "name_or_title": ""})
    assert set(problems) == {"unknown_source", "missing_name", "invalid_url"}
