# AI Usage

## AI tools used
- **Claude (Anthropic)** via claude.ai.

## What it was used for
- Reading the assignment and reference material and summarising the requirements.
- Generating the first version of the project code: scrapers, cleaning, validation, deduplication and `main.py`.
- Generating the unit tests and the first drafts of `README.md` and this file.
- Helping me fix setup problems (folder location, `lxml` install error, full disk).

## Representative prompts
1. "this is from reference materials, i want to send some more" (I shared screenshots of the reference document and the assignment).
2. "now explain in brief what project is this"
3. "give me the full project code, so that i will run in vs code, can i run this successfully in vs code?"
4. I pasted my terminal errors (`requirements.txt` not found, `lxml` build failure, "No space left on device") and asked for fixes.

## Which parts were AI-assisted
Almost all of the first draft of the code was AI-generated: `scrapers/*`, `processing/*`, `main.py`, `tests/*` and the documentation drafts. I then ran it on my own machine, checked the output, and updated the documentation with my real results.

## Important changes compared with the reference snippets
- Fingerprint for quotes: the text is normalised **before** taking the first 50 characters (the reference snippet sliced first), so extra spaces cannot shift the cut. A missing author is handled safely.
- A price or rating that exists but cannot be parsed is passed on as raw text, so validation rejects it with a reason instead of silently turning it into an empty cell.
- Scrapers keep `self.records` page by page, so a crash in the middle of a run keeps what was already collected.
- The summary report includes a reconciliation check (`collected - rejected - duplicates = final = CSV rows`) and per-source details.
- Book detail pages are fetched to fill `category` and `description` (can be switched off with `--no-details`).

## Incorrect or incomplete AI suggestions found
- `requirements.txt` pinned `lxml==5.3.0`. On my machine (Python 3.14) pip had no prebuilt package for it and tried to compile it, which failed. I fixed it by installing a newer `lxml` version and re-saving `requirements.txt` with `pip freeze`.
- A test expectation written by the AI in `tests/test_pipeline.py` was wrong at first (it expected two `invalid_url` rejections; the empty-title book is correctly `missing_name`). The test was corrected, not the code.
- The AI could not access the two websites, so it could only test with sample HTML. The selectors were confirmed by my real run.

## How the final solution was tested and verified
- `python -m pytest`: unit tests for cleaning, validation, deduplication, scrapers (using fake HTML pages) and the end-to-end pipeline, all without internet.
- A quick test with `python main.py --max-pages 2`, then I opened the CSV and checked the values.
- Full run on my machine on 6 October 2026: 1,000 books and 100 quotes collected, 0 records rejected, 1 duplicate detected and removed, 1,099 final records, run time 1,408 seconds (about 23.5 minutes).
- `summary_report.json` shows `reconciliation.ok = true`, and `final_record_count` (1,099) equals the number of rows in `final_dataset.csv`.
- I checked the CSV: