from processing.deduplication import find_duplicates, make_fingerprint


def test_duplicates_ignore_case_and_spaces():
    base = {"source": "Books to Scrape", "author": None}
    records = [
        {**base, "name_or_title": "Example Book Title"},
        {**base, "name_or_title": "  Example Book Title "},
        {**base, "name_or_title": "EXAMPLE BOOK TITLE"},
    ]
    unique, dupes = find_duplicates(records)
    assert len(unique) == 1 and len(dupes) == 2
    assert unique[0] is records[0]  # the first one is kept


def test_duplicates_ignore_punctuation():
    base = {"source": "Books to Scrape", "author": None}
    a = {**base, "name_or_title": "It's a Book!"}
    b = {**base, "name_or_title": "Its a Book"}
    assert make_fingerprint(a) == make_fingerprint(b)


def test_different_books_are_not_duplicates():
    base = {"source": "Books to Scrape", "author": None}
    unique, dupes = find_duplicates([{**base, "name_or_title": "One"}, {**base, "name_or_title": "Two"}])
    assert len(unique) == 2 and not dupes


def test_quote_duplicates_use_author_and_first_50_characters():
    base = {"source": "Quotes to Scrape", "author": "Albert Einstein"}
    long_text = "A" * 60
    records = [
        {**base, "name_or_title": long_text + " ending one"},
        {**base, "name_or_title": long_text + " different ending"},  # same first 50 chars
    ]
    unique, dupes = find_duplicates(records)
    assert len(unique) == 1 and len(dupes) == 1


def test_same_quote_text_by_different_authors_is_not_a_duplicate():
    a = {"source": "Quotes to Scrape", "author": "A", "name_or_title": "Same text"}
    b = {"source": "Quotes to Scrape", "author": "B", "name_or_title": "Same text"}
    unique, dupes = find_duplicates([a, b])
    assert len(unique) == 2 and not dupes


def test_same_title_in_different_sources_is_not_a_duplicate():
    a = {"source": "Books to Scrape", "author": None, "name_or_title": "Hope"}
    b = {"source": "Quotes to Scrape", "author": None, "name_or_title": "Hope"}
    unique, _ = find_duplicates([a, b])
    assert len(unique) == 2
