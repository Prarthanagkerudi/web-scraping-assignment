# Multi-Source Web Scraping & Data Consolidation

A Python ETL pipeline that scrapes two practice sites, cleans and validates the
data, removes duplicates and writes one tidy CSV plus a JSON summary.

- **Books to Scrape** (https://books.toscrape.com/): about 1,000 books over 50 pages
- **Quotes to Scrape** (https://quotes.toscrape.com/): 100 quotes over 10 pages

```
Scrape (both sites) -> Clean -> Validate -> Deduplicate -> Consolidate -> Save files
```

## Python version
Python 3.10 or newer. The unit tests were first run on Python 3.12, and the full real run was done on Python 3.14. (developed and tested on 3.12).

## Setup
```bash
# from the project folder
python -m venv venv
venv\Scripts\activate          # Windows (PowerShell/CMD)
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```
In VS Code: `Ctrl+Shift+P` -> "Python: Select Interpreter" -> choose the `venv` one.

## Dependencies
| Library | Purpose |
|---|---|
| requests | download pages (with retries) |
| beautifulsoup4 | search the HTML |
| lxml | fast HTML parser used by BeautifulSoup |
| pytest | unit tests (optional) |

Everything else (csv, json, logging, re, urllib, time, pathlib, hashlib, datetime) is the standard library.

## How to run
```bash
python main.py                  # full run (about 20-25 minutes, see below)
python main.py --no-details     # faster: skips the ~1,000 book detail pages
python main.py --max-pages 2    # quick smoke test: 2 listing pages per site
python main.py --delay 1.0      # pause 1 second between requests
python -m pytest                # unit tests, no internet needed
```
A full run is slow on purpose: it makes about 1,060 requests with a 0.5 s pause
between each one so the practice server is not overloaded.

## Output
| File | Content |
|---|---|
| `output/final_dataset.csv` | one row per unique, valid record, same 10 columns for every row |
| `output/summary_report.json` | counts per source (collected, cleaned, rejected, duplicates, final), rejections by reason, run time, reconciliation check |
| `logs/scraper.log` | timestamped INFO per page, WARNING per rejected record/duplicate, ERROR per failed request |

The summary reconciles: `collected - rejected - duplicates = final = rows in the CSV`
(`reconciliation.ok` in the JSON is `true` when it holds).

## Observations from exploring the sites
| Item | Books to Scrape | Quotes to Scrape |
|---|---|---|
| One record | `article.product_pod` | `div.quote` |
| Main text | `h3 > a` (full title in the `title` attribute; visible text ends with `...`) | `span.text` (wrapped in curly quotes) |
| Price / rating | `p.price_color` / class of `p.star-rating` (e.g. `Three`) | none |
| Author / tags | none | `small.author` / `a.tag` (zero or more) |
| Link | `h3 > a[href]` (relative path) | listing page URL (author link is `a[href^="/author/"]`) |
| Next page | `li.next > a` | `li.next > a` |
| Category, description | only on each book's detail page (breadcrumb 3rd link, `#product_description + p`) | none |

## How pagination works
`BaseScraper.scrape()` starts at the home page, parses it, looks for `li.next > a`,
converts its relative `href` to a full URL with `urljoin`, and repeats. When there is
no next link the loop ends. No page numbers are hard-coded, so the scraper keeps
working if the site gains or loses pages. A `visited` set prevents infinite loops.

## Data model
Columns, in order: `source, source_url, name_or_title, category, price, rating, author, tags, description, scraped_at`.
`None` (an empty CSV cell) is used where a field does not apply. Nothing is invented.

| Column | Books | Quotes |
|---|---|---|
| source | Books to Scrape | Quotes to Scrape |
| source_url | book detail page URL | the listing page where the quote appeared (my choice) |
| name_or_title | book title | quote text (curly quotes removed) |
| category | from the detail page | empty |
| price | number, e.g. 51.77 | empty |
| rating | integer 1-5 | empty |
| author | empty | author name |
| tags | empty | `tag1;tag2` (lowercase, sorted) |
| description | from the detail page (empty if the book has none) | empty |
| scraped_at | UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ` | same |

## Cleaning approach (`processing/cleaning.py`)
Small pure functions, no internet: `clean_text` (collapses tabs, newlines, spaces and
non-breaking spaces), `strip_quotes`, `clean_price` (`£51.77` -> `51.77`, also copes with
`Â£51.77`), `clean_rating` (`Three` -> `3`), `clean_tags`, `normalize_url`.
The page is decoded as UTF-8 (`response.encoding = "utf-8"`) so `£` is not corrupted.
If a value is present but cannot be parsed (for example price `n/a`), the raw text is
passed on so that validation rejects it with a reason instead of it silently becoming empty.

## Validation approach (`processing/validation.py`)
`validate_record` returns a list of problems (empty list = valid): `unknown_source`,
`missing_name`, `invalid_url`, `invalid_price` (present but not a number >= 0),
`invalid_rating` (present but not an integer 1-5). A record that crashes during cleaning is
rejected as `cleaning_error`. Rejected records are logged as warnings and counted by reason
(a record with two problems is counted once per reason, but once in `rejected_total`).

## Deduplication approach (`processing/deduplication.py`)
A fingerprint (SHA-256) is built from the identifying fields, each lower-cased with
punctuation removed and spaces collapsed:
- **Books:** source + title
- **Quotes:** source + author + first 50 characters of the (normalised) quote text

The first record seen is kept; later records with a seen fingerprint are duplicates.
**Duplicates are removed (not flagged)**, because the dataset must be one row per unique
record; each removed duplicate is logged and counted in the summary, so nothing disappears silently.
Both practice sites contain unique items, so a real run is expected to find 0 duplicates;
the logic is proven by `tests/test_deduplication.py` and `tests/test_pipeline.py` with deliberately duplicated data.

## Error-handling approach
- One shared `requests.Session` with a User-Agent, a 10 s timeout and automatic retries
  (HTTP 429/500/502/503/504, exponential backoff 1 s, 2 s, 4 s).
- Pause of 0.5 s between requests (configurable with `--delay`).
- Each record is parsed in `try/except`; missing HTML elements give `None` (`select_one` + checks).
- If a listing page still fails after retries, that source stops with the records collected so far and
  the other source still runs. If a book's detail page fails, the book is kept with empty category/description.
- Each source runs inside its own `try/except` in `main.py`.

## Project structure
```
scrapers/    base_scraper.py (session, retries, pagination), books_scraper.py, quotes_scraper.py
processing/  cleaning.py, validation.py, deduplication.py
tests/       unit tests (no internet)
schema.py    common column list and source names
main.py      connects all stages
```

## Assumptions
- Book `source_url` is the book's detail page; quote `source_url` is the listing page it appeared on.
- Quotes have no category, so `category` is empty for them.
- Two books with the same title count as duplicates (the assignment's rule), even though
  different books could theoretically share a title.
- Selectors were taken from the reference document and verified against sample HTML in the tests.

## Known limitations
- A failed listing page ends that source early (the next link cannot be found without the page).
  The log shows exactly where it stopped.
- No checkpoint/resume: an interrupted run starts again from the beginning.
- Requests are sequential (polite, but a full run takes about 20-25 minutes).
- Tags are only available for quotes; description only for books that have one on their detail page.
- If the sites change their HTML, only the selectors in `scrapers/` need updating.

## What I would change for regular production runs
Checkpoint/resume and incremental scraping, config file, a database instead of CSV, scheduled runs with alerting, and structured (JSON) logs.

## AI usage summary
See `AI_USAGE.md`.
