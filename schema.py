"""Common data model shared by both sources.

Every record in the final dataset has exactly these columns, in this order.
A field that does not apply to a source is left as None (empty cell in the CSV).
"""

SOURCE_BOOKS = "Books to Scrape"
SOURCE_QUOTES = "Quotes to Scrape"
VALID_SOURCES = {SOURCE_BOOKS, SOURCE_QUOTES}

COLUMNS = [
    "source",
    "source_url",
    "name_or_title",
    "category",
    "price",
    "rating",
    "author",
    "tags",
    "description",
    "scraped_at",
]
