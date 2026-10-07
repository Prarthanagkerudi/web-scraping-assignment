"""Pure cleaning functions: a value goes in, a cleaned value comes out.

No internet and no files here, so everything can be tested with plain strings.
"""
import re
from urllib.parse import urljoin

from schema import SOURCE_BOOKS, SOURCE_QUOTES

RATING_MAP = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def clean_text(value):
    """Collapse tabs, newlines, extra and non-breaking spaces. Empty -> None."""
    if value is None:
        return None
    text = str(value).replace("\xa0", " ").replace("\u200b", "")
    text = " ".join(text.split())
    return text or None


def strip_quotes(value):
    """Remove the curly (or straight) double quotation marks around a quote."""
    text = clean_text(value)
    if text is None:
        return None
    return clean_text(text.strip("\u201c\u201d\""))


def clean_price(raw):
    """'£51.77' -> 51.77. Returns None if no number can be found."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return round(float(raw), 2)
    match = re.search(r"\d+(?:\.\d+)?", str(raw).replace(",", ""))
    return round(float(match.group()), 2) if match else None


def clean_rating(raw):
    """'star-rating Three' -> 3. Returns None if no rating word is found."""
    if raw is None:
        return None
    for word in str(raw).lower().split():
        if word in RATING_MAP:
            return RATING_MAP[word]
        if word.isdigit():
            return int(word)
    return None


def clean_tags(tags):
    """Lowercase, remove blanks and repeats, sort, join with ';'. None if empty."""
    if tags is None:
        return None
    if isinstance(tags, str):
        tags = tags.split(";")
    cleaned = {clean_text(t).lower() for t in tags if clean_text(t)}
    return ";".join(sorted(cleaned)) or None


def normalize_url(url, base=None):
    """Make a URL complete. Returns None if it does not end up http(s)."""
    url = clean_text(url)
    if url is None:
        return None
    if base:
        url = urljoin(base, url)
    return url if url.lower().startswith(("http://", "https://")) else None


def _keep_if_unparseable(cleaned, raw):
    """If a value was present but could not be parsed, pass the raw text on.

    Validation then rejects it with a reason, instead of the problem being
    silently turned into an empty cell.
    """
    if cleaned is None and clean_text(raw) is not None:
        return clean_text(raw)
    return cleaned


def clean_book(raw):
    return {
        "source": SOURCE_BOOKS,
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": clean_text(raw.get("title")),
        "category": clean_text(raw.get("category_raw")),
        "price": _keep_if_unparseable(clean_price(raw.get("price_raw")), raw.get("price_raw")),
        "rating": _keep_if_unparseable(clean_rating(raw.get("rating_raw")), raw.get("rating_raw")),
        "author": None,
        "tags": None,
        "description": clean_text(raw.get("description_raw")),
        "scraped_at": raw.get("scraped_at"),
    }


def clean_quote(raw):
    return {
        "source": SOURCE_QUOTES,
        "source_url": normalize_url(raw.get("source_url")),
        "name_or_title": strip_quotes(raw.get("text_raw")),
        "category": None,
        "price": None,
        "rating": None,
        "author": clean_text(raw.get("author_raw")),
        "tags": clean_tags(raw.get("tags_raw")),
        "description": None,
        "scraped_at": raw.get("scraped_at"),
    }


def clean_record(raw):
    """Pick the right cleaner for a raw dictionary, based on its source."""
    source = raw.get("source")
    if source == SOURCE_BOOKS:
        return clean_book(raw)
    if source == SOURCE_QUOTES:
        return clean_quote(raw)
    raise ValueError(f"Unknown source: {source!r}")
