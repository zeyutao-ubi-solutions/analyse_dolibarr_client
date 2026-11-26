# Handoff: run and monitor LinkedIn company page scraping (Apify) in this repository

## Background

Repository: `/Users/zeyutao/Projects/analyse_dolibarr_client` (uv + pandas + pytest, `pythonpath=["src"]`).
We are building a lookalike model: using only the LinkedIn company page, judge whether a company looks like our end customers (overall model + business-line allocation model). Labels and samples are ready; **what is missing is the LinkedIn features**, and that is your task. You are responsible only for scraping and storage; **do not train any model**.

Read first:

1. `docs/labeling/linkedin_scrape_contract.md`: input list, output fields, matching rules (**this is the reference**)
2. `docs/labeling/feature_policy.md`: which fields are features and which are only for checking
3. `src/analyse_dolibarr_client/scrape_list.py`: how the list is generated
4. Reference (**read-only, do not modify**): `~/web_app_refactoring/backEnd/src/integrations/apify/linkedin_company_details_scraper.py`, `~/web_app_refactoring/backEnd/src/workflows/shared/validate_company/scrape_output.py` (how the web app calls the same actor and parses its output)

## Task

For the units in `data/processed/2026-11-18/labeling/linkedin_scrape_list.csv` (3,276 with `batch=main`, 140 spare with `batch=reserve`), scrape LinkedIn company pages with the Apify actor **`harvestapi/linkedin-company`**, and store both the raw and the cleaned results locally.

## Must follow

- **token**: read `APIFY_TOKEN` from `~/web_app_refactoring/backEnd/.env` at runtime. Do not print it, copy it, write it to any file or log, or commit it to git; do not put it in URL query parameters (use an `Authorization: Bearer` header or apify-client).
- **Do not modify** any file in `~/web_app_refactoring`.
- **Scrape company pages only**, not employees, contacts or posts; do not use anyone's LinkedIn login cookie.
- **Do not bring in labels**: the list has no "is a customer" field, and the matching stage (including any LLM judgement) must not read the `label` in `lookalike_units.csv` either.
- **Data goes only under `data/`** (gitignored). Code goes in `src/analyse_dolibarr_client/`, tests in `tests/`. Do not commit `data/`, `.env` or any secret.
- **Pilot first, then full run**: see "Steps" below. You must stop and wait for user confirmation before the full run.

## Steps

### 1. Write the scraping module

`src/analyse_dolibarr_client/linkedin_scrape.py` (CLI: `uv run python -m analyse_dolibarr_client.linkedin_scrape ...`):

- Read the scrape list; call the actor in batches (suggested 25–50 searches per run, at most 1–2 runs at a time, configurable).
- Input: when `web_domain` is present, try `{"searches": [search_name]}` first, then check against the returned `website` domain; when nothing is found or the domain does not match, try `alt_search_names` in turn. Once you have a page URL and need more details, use `{"companies": [url]}`. The actual return format is whatever the pilot shows; adjust if needed.
- **Resumable and idempotent**: maintain a progress file recording the status of each `unit_id`; on rerun, skip completed ones unless a rescrape is explicitly requested. Write to disk at the end of every batch.
- Retry failures / timeouts at most 2 times, then record `error` and continue.
- Dependencies: you may `uv add apify-client`, or call the Apify REST API with the standard library.
- Tests: mock Apify; tests must not access the network. Cover: domain matching, name matching, ambiguous, resume skips completed units, the token appears in no output.

### 2. Local storage (all under `data/processed/2026-11-18/labeling/linkedin/`)

| File | Content |
|---|---|
| `raw/<apify_run_id>.jsonl` | The dataset of each Apify run saved as is, fields unchanged |
| `runs.csv` | Per run: run_id, dataset_id, list of input unit_ids, status, start / end time, item count, cost (usage returned by Apify) |
| `progress.csv` | Per unit_id: status, number of attempts, last error |
| `scrape.log` | Progress log (no token) |
| `../linkedin_companies_<YYYY-MM-DD>.csv` | Results cleaned per the contract, one row per unit_id, fields as in section 2 of the contract |

### 3. Pilot (required, then stop)

Take 20 units from `batch=main`: about half with a domain and half without, including at least a few non-French units. When done, **stop and report to the user**:

- Matching results: counts of matched / not_found / ambiguous / error; share of `match_method=domain` among them
- What the returned fields actually look like: coverage of description, industry, employee count, website etc.; where the return format differs from the contract
- Pick 5 `name_country` matches for the user to check manually
- **Cost and time**: actual cost per company, time per batch, and the estimated total cost and total duration for all 3,276

Run the full set only after the user confirms.

### 4. Full run and monitoring

- Run in the background; report progress regularly: completed / total, count per status, cumulative cost, estimated time remaining.
- Pause and report if: the error rate exceeds 20% for a whole batch; cumulative cost exceeds 1.5 times the pilot estimate; Apify returns rate limiting / insufficient quota.
- After `main` is done, compute the `not_found` rate per country. For any country with `not_found` above 15%, scrape units from **the same country** in `batch=reserve`, roughly as many as the shortfall.

### 5. Wrap-up

- Generate `linkedin_companies_<YYYY-MM-DD>.csv` and write a short summary: total, counts per `match_status` / `match_method`, match rate per `country_code`, field coverage, total cost.
- Run `uv run pytest -q`; everything passes.
- Commit the code and tests on the current branch (without `data/`), with a commit message that clearly describes what was done; do not push.
- Report: result file path, summary, open issues (e.g. the number of ambiguous units needing manual judgement).
