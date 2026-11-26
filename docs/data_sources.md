# Data sources and known issues

This repository reads four kinds of data: the Dolibarr marts in the Snowflake data warehouse (master data), the Dolibarr REST API (read-only supplement), LinkedIn company pages scraped with Apify, and HubSpot (contact model, planned). Credential locations are in the root README.

## 1. Snowflake: Dolibarr marts

Database `UBI_DATAHUB_TEST`, schema `DBT__3_MARTS`. `pull.py` pulls whole tables at their original grain and stores them as `data/raw/<snap>/*.parquet` plus `manifest.json`, read-only afterwards.

| Table | Grain | Main use |
|---|---|---|
| `mart_orders_to_date` | Order line | Customer, amount, category, product; basis of the customer list |
| `mart_invoicing_to_date` | Invoice line | Order vs invoice reconciliation |
| `mart_contracts_to_date` | Contract line | Whether there is a contract |
| `mart_product_catalog` | Product (SKU) | Product name (business-line determination) |
| `mart_third_parties` | Third-party record | Name, country, town, SIREN, customer / prospect / supplier / intercompany flags |
| `mart_supplier_orders_to_date` | Purchase order line | Whether a customer is also a supplier |
| `mart_revenues_per_customer` | Customer × period | Not used yet |
| `mart_element_links` | Document links | Not used yet |

### Known issues

| Issue | Impact | Handling |
|---|---|---|
| The order `CUSTOMER_ID` is a 32-character hash. For some customers it equals md5(THIRD_PARTY_ID); the rest are unknown keys merging several third parties | Cannot be mapped directly to third-party records | `CUSTOMER_ID = THIRD_PARTY_ID` is **forbidden**. Prefer the Dolibarr API to find the third party each order was actually invoiced to (socid); fall back to name matching when not found |
| `ENTITY_ID` maps to legal entities: 1 = Ubi Solutions, 2 = Page Up, 3 = Ubi Smart, 5 = Ubi Impact | | `companies.ENTITY_ID_TO_NAME` |
| Page Up / Ubi Smart / Ubi Impact orders only entered the data warehouse in 2023–2024 | For customers ordering only through these entities, first-order date and years active may be too short; part of the jump in new customers from 2024 is a data artefact | Flag `history_truncated`; recorded as `truncated` in the value tier |
| Group intercompany entities (`IS_INTERCOMPANY`) also appear as "customers" in orders | Inflated amounts | Customers whose orders are all invoiced to intercompany entities are excluded; for partial cases, those orders are deducted |
| `ITEM_CATEGORY` cannot separate BLE geolocation from RFID: most of "Traceurs et objets connectés" is RFID textile tags | Business line cannot be determined from the category | Use Dolibarr product tags + product name rules (`product_lines.py`) |
| The NAF fields (`SECTION`…`CLASSE`) have names only, no codes, and cover only about 292 customers, almost all in France | Cannot be used as model features (would become a country proxy) | Analysis only |
| The record `SIREN` column mixes SIREN, SIRET and foreign tax numbers | | Kept as is; validate the number of digits when using it |
| Record names sometimes carry internal codes (`FR01 FAURECIA …`); the customer name on orders is sometimes a merged label (`S Transport` is actually BOVIS Transport) | Wrong name used for search | `lookup_name` prefers the invoiced record name; when the two are unrelated, `lookup_name_conflict=true` and both are searched |

## 2. Dolibarr REST API (read-only)

GET only. Header `DOLAPIKEY`, plus `DOLAPIENTITY` per legal entity (1 / 2 / 3 / 5). The API user is an admin account, so the code has **no write methods at all**.

| Module | Endpoint | What it fetches | Output |
|---|---|---|---|
| `erp_socid.py` | `GET /orders` (paginated) | Order id, number, socid, legal entity | `erp_orders.csv`, `erp_order_socid.csv` |
| `erp_thirdparties.py` | `GET /thirdparties`, `GET /contacts` | Name, SIREN, website, company email **domain**, contact email **domains** and counts, employee-count tier | `erp_thirdparties.csv` |
| `product_lines.py` | `GET /categories?type=product`, `GET /categories/{id}/objects` | Product tags and their products | `erp_product_tags.csv` |

### Known issues

- **The API instance and the data warehouse source diverge from ORDER_ID ≈ 9704 (early September 2026)**: newer orders are missing from the API or have different numbers. The socid returned by the API is used only when the order id **and** the number both match (8,408 of 8,860); which instance is production has not been confirmed by IT.
- Contacts returned under each legal entity are the same set; deduplicated by id.
- The product tag endpoint returns 401 for entity 2 (Page Up) and 5 (Ubi Impact); all tags seen so far belong to Ubi Solutions.
- The GPSBLE tag only exists from about 2024; older geolocation products have no tag.
- Our own employees are often attached as contacts of customers: group domains such as `ubisolutions.net` and `pageup.fr` are never treated as customer domains.

### Personal data

Contact names, full email addresses, phone numbers and personal LinkedIn profiles are **used only in memory and never written to any file**; only email domains and their counts are kept.

## 3. LinkedIn (Apify)

- actor: `harvestapi/linkedin-company`, input `{"searches": [...]}` (search by name, returns the first result) or `{"companies": [url, ...]}`.
- Company pages only, never personal profiles.
- Measured in the pilot: billed per returned item, about $0.0012 / item; no charge when nothing is found.
- The first result of a name search is often a foreign company with the same name, a group page or a trade-union page; matching rules are in section 3 of `docs/labeling/linkedin_scrape_contract.md`.

## 4. HubSpot (planned, contact model)

The web app already has a read-only integration (`~/web_app_refactoring/backEnd/src/services/hubspot/`): it reads contacts / companies / deals and their associations, and matches people to HubSpot contacts by email and `lemlistlinkedinurl`. Fields used include:

- Contacts: `email`, `jobtitle`, `lifecyclestage`, `hs_lead_status`, `notes_last_contacted`, `num_associated_deals`, `hubspot_owner_id`, `lemlistlinkedinurl`
- Deals: `dealstage`, `closedate`
- Companies: `name`, `domain`

The web app also has a read-only field probe tool (`field_probe.py`) that records only field names, enum values and fill counts, no personal information. The first step of the contact model is to use it to confirm which fields have data; see `docs/models/contact_model.md`.

Note: the web app itself also writes companies and contacts to HubSpot, so some HubSpot records were themselves selected by the web app.
