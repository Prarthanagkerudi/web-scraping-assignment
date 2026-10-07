"""Duplicate detection with a normalised fingerprint.

Rule (the same rule is written in README.md):
  Books : source + title
  Quotes: source + author + first 50 characters of the quote text
Each part is lower-cased, punctuation is removed and spaces are collapsed
BEFORE hashing (and before taking the first 50 characters), so differences in
case, spacing or punctuation do not matter.
"""
import hashlib
import re
import unicodedata

from schema import SOURCE_BOOKS


def _normalise(value):
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def make_fingerprint(rec):
    source = _normalise(rec.get("source"))
    if rec.get("source") == SOURCE_BOOKS:
        key = f"{source}|{_normalise(rec.get('name_or_title'))}"
    else:  # quotes
        key = (f"{source}|{_normalise(rec.get('author'))}|"
               f"{_normalise(rec.get('name_or_title'))[:50]}")
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def find_duplicates(records):
    """Return (unique, duplicates). The first record seen is kept."""
    seen, unique, dupes = set(), [], []
    for rec in records:
        fp = make_fingerprint(rec)
        (dupes if fp in seen else unique).append(rec)
        seen.add(fp)
    return unique, dupes
