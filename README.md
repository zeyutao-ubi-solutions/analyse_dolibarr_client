# analyse_dolibarr_client

Starting from the historical orders in Dolibarr, work out **who our customers are and what they bought**, then use that to train models that score the companies and contacts found by the web app (Sales Intelligence Workbench, `~/web_app_refactoring`).

## What it does

| Stage | Output | Status (2026-11-20) |
|---|---|---|
| 1. Customer list | List of companies with customer orders (CO), analysis by order / category / business line, README report | Done |
| 2. Labels and samples for the company lookalike model | Customer-type labelling sheet, sample units (positive / unlabeled), country weights and country factors, business-line labels | Done; P1 customer types awaiting manual review |
| 3. LinkedIn features | Company page scraping (Apify), manual matching queue | In progress |
| 4. Company model training and scoring | Overall model + business-line allocation model, model files, scoring CLI | Planned (branch `lookalike-training`) |
| 5. Integration with the web app | Scoring service or batch exchange, feedback of sales outcomes | Planned |
| 6. Contact model | Classification / scoring model based on HubSpot contact data | Planned |

## Documentation

| Document | Content |
|---|---|
| [docs/data_sources.md](docs/data_sources.md) | Data sources, credential locations, known data pitfalls |
| [docs/models/company_lookalike.md](docs/models/company_lookalike.md) | Company model: goal, labels, structure, technology, validation, usage and operations |
| [docs/models/contact_model.md](docs/models/contact_model.md) | Plan for the contact model (HubSpot) |
| [docs/labeling/feature_policy.md](docs/labeling/feature_policy.md) | Company model feature policy, business lines, country handling, pre-launch checks |
| [docs/labeling/customer_type.md](docs/labeling/customer_type.md) | Manual labelling guide for customer type |
| [docs/labeling/linkedin_scrape_contract.md](docs/labeling/linkedin_scrape_contract.md) | LinkedIn scraping input / output / matching rules |
| [docs/decisions.md](docs/decisions.md) | Decision log (who, when, why) |
| `docs/handoff/` | Task briefs handed to other agents |
| `data/processed/<snapshot>/README.md` | Customer-list analysis report generated automatically by each build (not in git) |

## Installation

```bash
uv sync
uv run pytest -q
```

Python ≥ 3.11. Dependencies are managed by `uv` (`pyproject.toml` / `uv.lock`).

## Credentials (only locations and variable names; values never go into this repository)

| Purpose | Location | Variables |
|---|---|---|
| Snowflake data warehouse (read-only) | This repository's `.env` (template `.env.example`) | `SNOWFLAKE_*`, path to the `.p8` private key |
| Dolibarr REST API (read-only GET) | `~/Projects/internal-agent-hub/dolibarr-mcp/.env` | `DOLIBARR_URL`, `DOLIBARR_API_KEY`, `DOLIBARR_SSL_VERIFY` |
| Apify (LinkedIn company pages) | `~/web_app_refactoring/backEnd/.env` | `APIFY_TOKEN` |
| HubSpot (contact model, planned) | `~/web_app_refactoring/backEnd/.env` | `HUBSPOT_PRIVATE_APP_TOKEN` |

The code reads these files only at runtime; it never prints, copies or writes them to any output.

## Pipeline

Run in order; `<snap>` is the snapshot date (e.g. `2026-11-18`).

```bash
# 1. Pull a snapshot from Snowflake into data/raw/<snap>/ (read-only, never modified afterwards)
uv run python -m analyse_dolibarr_client.pull --snapshot <snap>

# 2. Dolibarr API (read-only): the third party each order was actually invoiced to
uv run python -m analyse_dolibarr_client.erp_socid --snapshot <snap> --env-file ~/Projects/internal-agent-hub/dolibarr-mcp/.env

# 3. Dolibarr API (read-only): third-party websites, email domains, contact email domains (domains only)
uv run python -m analyse_dolibarr_client.erp_thirdparties --snapshot <snap> --env-file ~/Projects/internal-agent-hub/dolibarr-mcp/.env

# 4. Dolibarr API (read-only): product tags (to tell business lines apart)
uv run python -m analyse_dolibarr_client.product_lines --snapshot <snap> --env-file ~/Projects/internal-agent-hub/dolibarr-mcp/.env

# 5. Customer list + analysis report
uv run python -m analyse_dolibarr_client.companies --snapshot <snap>

# 6. Company model labels, sample units, country factors, customer-type labelling sheet
uv run python -m analyse_dolibarr_client.lookalike --snapshot <snap>

# 7. LinkedIn scrape list
uv run python -m analyse_dolibarr_client.scrape_list --snapshot <snap>

# 8. LinkedIn scraping (Apify, billed per item; run --pilot first)
uv run python -m analyse_dolibarr_client.linkedin_scrape --snapshot <snap> --pilot

# 9. Training and scoring (planned, see docs/models/company_lookalike.md)
```

If the results of steps 2–4 are missing, step 5 falls back to name matching / name rules only, and says so in the report.

## Outputs (all under `data/`, gitignored)

| Path | Content |
|---|---|
| `data/raw/<snap>/` | Snowflake snapshot (parquet), read-only |
| `data/processed/<snap>/companies.parquet/.csv` | Customer list (one row per CUSTOMER_ID) |
| `data/processed/<snap>/README.md` | Automatically generated analysis report |
| `data/processed/<snap>/{unmatched,duplicates,issues,orders_by_*,category_cooccurrence}.csv` | Auxiliary tables |
| `data/processed/<snap>/erp_*.csv` | Read-only Dolibarr API results |
| `data/processed/<snap>/labeling/` | Labelling sheet, sample units, country factors, scrape list, LinkedIn results, manual queue |
| `data/models/` (planned) | Model files, embedding cache |

## Rules

- `data/`, `.env` and any secrets never go into git.
- `data/raw/` is read-only; all outputs are written to `data/processed/` or `data/models/`.
- The Dolibarr API is used with GET only; nothing is written.
- The order `CUSTOMER_ID` is a hash; joining it directly to `THIRD_PARTY_ID` is **forbidden** (see `docs/data_sources.md`).
- LinkedIn: scrape company pages only, never personal profiles; contact data is handled only under the rules in `docs/models/contact_model.md`.
- Suspected integrators are only flagged, never removed; no subjective scoring in the list, scoring is done by the model.
