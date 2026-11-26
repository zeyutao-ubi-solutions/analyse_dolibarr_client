# Labelling guide: customer type (customer_type)

Used for the lookalike (ICP similarity) model: only **end users** go into the positive samples. If integrators, resellers or peers get mixed into the positives, the model learns to "find integrators".

- Labelling sheet: `data/processed/<snapshot>/labeling/customer_type_labels.csv` (UTF-8 BOM, opens directly in Excel)
- Regenerate: `uv run python -m analyse_dolibarr_client.lookalike --snapshot <snapshot>`
  - Only refreshes the context columns and adds new customers; **labelling columns already filled in are never overwritten**, and the old file is first backed up to `labeling/history/`.
  - Invalid values raise an error listing the row numbers; they are never silently ignored.

## Columns to fill in

| Column | Values | Notes |
|---|---|---|
| `customer_type` | See table below | Required; if unsure, enter `unsure`, do not guess |
| `confidence` | `high` / `medium` / `low` | |
| `evidence_url` | URL | Basis for the judgement: website "About us", LinkedIn page, societe.com, etc. |
| `annotator` | Initials | |
| `labeled_at` | `YYYY-MM-DD` | |
| `comment` | Free text | Especially for `unsure`, state where you got stuck |

The other columns (`priority`, `suggested_type`, amounts, categories, `notes`…) are reference information; do not change them.

## customer_type values

| Value | Definition | Examples / clues |
|---|---|---|
| `end_user` | Uses our products/services itself (laundries, logistics warehouses, factories, hospitals, hotels, retail…) | `GEODIS LOGISTICS`, `ILUNION TEXTIL` |
| `integrator_reseller` | Buys to resell or integrate for its own customers: IT integrators, resellers, system vendors, solution providers | Name contains SYSTEMS / INFORMATIQUE / DISTRIBUTION and the business is IT; the order name is another company (`lookup_name_conflict`); also one of our suppliers |
| `competitor` | Sells the same kind of RFID / IoT / traceability solutions as we do | Website mainly sells RFID tags, readers, traceability software |
| `intercompany` | Group intercompany entity (Ubi Solutions, Page Up, Ubi Smart, Ubi Impact and their subsidiaries) | Usually excluded automatically; label any that slipped through here |
| `not_a_company` | Individuals, test accounts, internal placeholder customers | "DIVERS", "CLIENT TEST", personal names |
| `unsure` | Still undecidable after checking | Treated as unlabelled, handled per `suggested_type` |

Decision rules:

1. **Look at what they do with our products, not at who they are.** The IT subsidiary of a large group counts as `end_user` if it uses them for the group itself.
2. **When the order name and the third-party record name differ (`order_name_differs`)**, the record name is the invoiced party:
   - The invoiced party is an IT/solutions company and the order name is the end customer (`EXERTIS AZENN` invoiced, order name "Orange") → `integrator_reseller`
   - Just brand name vs legal name (`SECANETA` → JOSÉ ALBERO PUERTO) or group vs subsidiary (`S Transport` → BOVIS Transport) → `end_user`
3. **Also being a supplier (`also_supplier`)** does not mean integrator: we also buy services from customers. Look at the core business.
4. Mixed cases (both own use and resale): decide by the part with the larger amount, and explain in `comment`.

## What to label first

Sort by `priority`, top to bottom:

- **P1**: suspected integrators, also suppliers, order name differs from record name: the most likely to not be end users, must be reviewed manually
- **P2**: customers in the top 90% by amount, or whose domain and company name do not match
- **P3**: the rest: default to `suggested_type`, spot checks are enough

## Quality control

- Before starting for real, two people independently label the same batch of **all P1 + 30 random P2**, and compute agreement (Cohen's kappa). Below 0.7, first align the rules and update this guide, then continue.
- After that, cross-check a random 10% of every 200 rows.
- When the rules change, update this file and note the affected rows in `comment`.
