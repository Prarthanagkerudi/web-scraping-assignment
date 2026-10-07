"""Record validation. Returns a list of problems; an empty list means valid."""
from schema import VALID_SOURCES

REASONS = [
    "unknown_source",
    "missing_name",
    "invalid_url",
    "invalid_price",
    "invalid_rating",
    "cleaning_error",  # a record that crashed while being cleaned
]


def validate_record(rec):
    problems = []
    if rec.get("source") not in VALID_SOURCES:
        problems.append("unknown_source")
    if not rec.get("name_or_title"):
        problems.append("missing_name")
    if not str(rec.get("source_url") or "").startswith(("http://", "https://")):
        problems.append("invalid_url")
    price = rec.get("price")
    if price is not None and (
        isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0
    ):
        problems.append("invalid_price")
    rating = rec.get("rating")
    if rating is not None and (isinstance(rating, bool) or rating not in (1, 2, 3, 4, 5)):
        problems.append("invalid_rating")
    return problems
