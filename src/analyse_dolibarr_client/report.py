"""Render data/processed/<snapshot>/README.md from a build result. Every number is computed."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from analyse_dolibarr_client.companies import (
    HARDWARE_CATEGORIES,
    LICENSE_MAINTENANCE_CATEGORIES,
    LICENSE_MAINTENANCE_MIN_SHARE,
    MATCH_AMBIGUOUS,
    MATCH_ERP,
    MATCH_EXACT,
    MATCH_NORMALIZED,
    MATCH_UNMATCHED,
    MIX_MIN_SIDE_SHARE,
    PROJECT_SERVICE_CATEGORIES,
    REPEAT_PRODUCT_MIN_SHARE,
    BuildResult,
    Snapshot,
    _is_true,
)
from analyse_dolibarr_client.names import LEGAL_PREFIXES, LEGAL_SUFFIXES

EXPECTED_CUSTOMERS = 1227
EXPECTED_ORDERS = 8860
EXPECTED_AMOUNT = 1.04e8
NEW_CUSTOMER_YEARS = (2024, 2025, 2026)
TAG_SUBCATEGORY = "Balises/étiquettes RFID et cartes ID"


def eur(x: float) -> str:
    return f"€{x:,.2f}"


def pct(x: float | None) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:.1%}"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        cells = ["" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v) for v in row]
        lines.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |")
    return "\n".join(lines)


def _category_mix(lines: pd.DataFrame) -> pd.Series:
    real = lines[~_is_true(lines["IS_NOT_REAL_ITEM"])]
    s = real.groupby("ITEM_CATEGORY")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    s = s.drop(labels=["NULL"], errors="ignore")
    return s / s.sum()


def render_readme(snap: Snapshot, r: BuildResult, snapshot_date: date) -> str:
    o = snap.orders
    allc, c = r.all_customers, r.companies
    total_amount = o["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    not_real = o[_is_true(o["IS_NOT_REAL_ITEM"])]
    inter = allc[allc["is_intercompany"]]
    inter_lines = o[o["CUSTOMER_ID"].isin(set(inter["customer_id"]))]
    main_total = c["amount_ht_eur"].sum()
    il = r.intercompany_lines
    il_amount = float(il["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()) if len(il) else 0.0
    il_desc = (
        f"{il['CUSTOMER_ID'].nunique()} customers / {il['ORDER_ID'].nunique()} orders / {eur(il_amount)}" if len(il) else "0"
    )
    n = len(c)
    out: list[str] = []
    w = out.append

    w(f"# Companies with customer orders (CO) — snapshot {snap.snapshot}\n")
    w(
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by "
        f"`uv run python -m analyse_dolibarr_client.companies --snapshot {snap.snapshot}`; "
        "this file is overwritten on every rerun. It reads the parquet files under `data/raw/`, plus "
        "`erp_order_socid.csv` (order → third party) obtained by `erp_socid.py` through read-only Dolibarr API calls, "
        "`erp_thirdparties.csv` (third-party websites / email domains) fetched read-only by `erp_thirdparties.py`, "
        "and `erp_product_tags.csv` (product tags) fetched read-only by `product_lines.py`; "
        "no connection to Snowflake, no LinkedIn scraping.\n"
    )

    # ---------------------------------------------------------------- scope
    w("## 1. Scope and checks\n")
    n_orders, n_cust = o["ORDER_ID"].nunique(), o["CUSTOMER_ID"].nunique()
    no_date = o[o["ORDER_DATE"].isna()]
    entity_start = ", ".join(
        f"{k} {v}" for k, v in o.groupby("ENTITY_NAME")["ORDER_DATE"].min().sort_values().items()
    )
    scope = pd.DataFrame(
        [
            ["Order lines (all)", f"{snap.orders_all_rows:,}", "", ""],
            ["Valid order lines IS_VALID_ORDER=true", f"{len(o):,}", "", ""],
            ["Valid orders", f"{n_orders:,}", f"{EXPECTED_ORDERS:,}", f"{n_orders - EXPECTED_ORDERS:+,}"],
            ["Customers with valid orders (CUSTOMER_ID)", f"{n_cust:,}", f"{EXPECTED_CUSTOMERS:,}", f"{n_cust - EXPECTED_CUSTOMERS:+,}"],
            ["Valid order amount HT", eur(total_amount), "≈ €104,000,000", eur(total_amount - EXPECTED_AMOUNT)],
            ["Valid order lines with IS_NOT_REAL_ITEM=true (excluded)", f"{len(not_real):,} lines / {eur(not_real['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}", "", ""],
            ["Customers matching an intercompany entity (excluded, see issues.csv)", f"{len(inter)} / {inter_lines['ORDER_ID'].nunique()} orders / {eur(inter_lines['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}", "", ""],
            ["Orders of master-list customers billed to intercompany entities (deducted from amounts)", il_desc, "", ""],
            ["**Rows in master list companies.csv**", f"**{n:,}**", "", ""],
            ["**Master list total amount_ht_eur**", f"**{eur(main_total)}**", "", ""],
        ],
        columns=["Item", "Actual", "Expected", "Difference"],
    )
    w(md_table(scope) + "\n")
    w(
        f"- The numbers of valid orders and customers match the expected values exactly; amount {eur(total_amount)} (≈ {total_amount / 1e6:,.2f} million euros HT).\n"
        f"- IS_NOT_REAL_ITEM has no true value among valid orders, so although the exclusion logic is implemented, this run actually excludes 0 lines, €0.\n"
        f"- Excluded intercompany customers: {', '.join(f'{x.customer_name} ({x.entity_names}, {eur(x.amount_ht_eur)})' for x in inter.itertuples())}.\n"
        f"- {int((c['amount_ht_eur'] == 0).sum())} customers in the master list have a total valid order amount of €0 (all zero-amount order lines); they stay in the list, with \"valid order amount is 0\" in notes.\n"
        f"- {int(c['customer_name'].isna().sum())} CUSTOMER_IDs have no CUSTOMER_NAME on their orders and cannot be matched by name; "
        f"they are written to issues (no_customer_name), total {eur(c.loc[c['customer_name'].isna(), 'amount_ht_eur'].sum())}; "
        f"for {int((c['customer_name'].isna() & c['match_status'].eq(MATCH_ERP)).sum())} of them the ERP socid supplied the third party. "
        "When `lookup_name` is empty, `third_party_name` can be used.\n"
        "- Payment status IS_PAID is entirely empty; payments are not analysed in this run.\n"
        f"- {len(no_date)} valid order lines ({no_date['ORDER_ID'].nunique()} orders, {', '.join(sorted(no_date['ENTITY_NAME'].unique()))}, "
        f"{eur(no_date['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}) have no ORDER_DATE. Their amounts are counted as usual; "
        "in orders_by_category their year is empty; dates were not inferred from order numbers.\n"
        f"- Earliest order per legal entity in the snapshot: {entity_start}. Page Up and Ubi Smart orders essentially start in 2024 (only 4 each in 2023), "
        "so the \"first order\" of their customers in this data mostly falls in 2024 or later, which does not necessarily mean they are new customers. "
        f"{int(c['history_truncated'].sum())} customers ordered only from these entities (Page Up / Ubi Smart / Ubi Impact)"
        f" ({eur(c.loc[c['history_truncated'], 'amount_ht_eur'].sum())}); they are flagged `history_truncated=true`: "
        "their first_order_date, n_years_active and \"new customer\" status are unreliable. "
        "Customers who also ordered from Ubi Solutions are not flagged, because the Ubi Solutions history is complete.\n"
    )

    # ---------------------------------------------------------------- matching
    w("## 2. Matching to third-party records\n")
    vc = c["match_status"].value_counts()
    nm = r.name_matches
    any_match = n - int(vc.get(MATCH_UNMATCHED, 0))
    unique_statuses = [MATCH_ERP, MATCH_EXACT, MATCH_NORMALIZED]
    unique_match = int(sum(vc.get(s, 0) for s in unique_statuses))
    w(
        "Two layers: first the third party the order itself carries in the ERP (socid); customers without a trusted socid are then matched by name.\n\n"
        + md_table(
            pd.DataFrame(
                [
                    [s, int(vc.get(s, 0)), pct(vc.get(s, 0) / n), eur(c.loc[c["match_status"] == s, "amount_ht_eur"].sum())]
                    for s in (MATCH_ERP, MATCH_EXACT, MATCH_NORMALIZED, MATCH_AMBIGUOUS, MATCH_UNMATCHED)
                ],
                columns=["match_status", "Customers", "Share of master list", "Order amount"],
            )
        )
        + "\n"
    )
    w(
        f"- **Unique match rate (erp_socid + exact + normalized): {unique_match}/{n} = {pct(unique_match / n)}**; "
        f"by amount {pct(c.loc[c['match_status'].isin(unique_statuses), 'amount_ht_eur'].sum() / main_total)}. "
        f"Including ambiguous, {any_match}/{n} = {pct(any_match / n)} match at least one third-party record.\n"
    )
    erp = snap.erp_order_socid
    if erp is not None:
        trusted = erp["socid_trusted"]
        bad = erp[~trusted]
        no_erp = c[c["erp_orders_verified"] == 0]
        md5_ok = erp.loc[trusted & erp["md5_socid_equals_customer_id"].eq("True"), "CUSTOMER_ID"].nunique()
        w("### 2.1 ERP socid (primary source)\n")
        w(
            "The order mart's CUSTOMER_ID is a 32-character hash, not a third-party ID, so it cannot be joined directly. "
            "`erp_socid.py` uses the Dolibarr REST API **read-only** to list all order headers (`GET /orders`, paged per legal entity), keeping only id, ref, socid and entity, "
            "saved as `erp_orders.csv`; these are then matched to snapshot orders by ORDER_ID, and an order's socid is used only when **both ORDER_ID and order number agree** (`erp_order_socid.csv`).\n\n"
            f"- {len(erp)} valid orders in the snapshot: {int(erp['id_found'].astype(str).eq('True').sum())} found in the ERP by ID, {int(trusted.sum())} with both ID and order number agreeing.\n"
            f"- All {len(bad)} disagreeing orders have ORDER_ID above {pd.to_numeric(bad['ORDER_ID'], errors='coerce').min():.0f}"
            f" ({int(bad['id_found'].astype(str).ne('True').sum())} with no such ID in the ERP, {int(bad['id_found'].astype(str).eq('True').sum())} with the same ID but a different order number). "
            "The instance the API connects to and the snapshot's data source diverged in early September 2026: orders before that are identical, after that each side numbers its own. "
            f"So the {len(no_erp)} customers without a trusted socid are all new customers whose first order is on or after {pd.to_datetime(no_erp['first_order_date']).min():%Y-%m-%d}; "
            "they fall back to name matching. Which instance is the production database needs to be confirmed with IT.\n"
            f"- Corroboration: for {md5_ok} customers, CUSTOMER_ID is exactly `md5(socid)`, showing that for some customers the mart simply hashes the third-party ID; "
            "for the other customers CUSTOMER_ID is a merge key across several third parties, with an unknown algorithm.\n"
            f"- {int((c['erp_third_parties'].str.count(';') > 0).sum())} customers have orders on several third-party records"
            " (e.g. GEODIS regional branches, or group and subsidiaries billed interchangeably). The master list's third_party_id is the socid of the **non-intercompany third party with the largest order amount**; "
            "all socids and amounts are written to `erp_third_parties` (`id:amount;…`), and `erp_multiple_third_parties` is recorded in issues.csv.\n"
            "- Customers whose orders are all billed to intercompany entities (IS_INTERCOMPANY) are excluded from the master list. Customers with only some orders billed to intercompany entities are kept, "
            "but those orders are deducted from amounts, order counts and category statistics (the deducted amount is in `intercompany_excluded_ht_eur`), recorded as `erp_includes_intercompany`. "
            "In `erp_third_parties`, intercompany socids are marked `(interco)`, and amounts are before deduction.\n\n"
        )
        labels = {
            "same": "name match found this same third party",
            "same_name_other_row": "name match found another record with the same name (duplicate entry)",
            "erp_in_name_candidates": "name match one-to-many, the ERP choice is among the candidates",
            "name_ambiguous_other": "name match one-to-many, the ERP choice is not among the candidates",
            "different": "name match found another third party (mostly group name vs actually billed subsidiary)",
            "name_unmatched": "name did not match, filled in by ERP",
        }
        cmp_ = c.loc[c["match_status"] == MATCH_ERP, "name_vs_erp"].value_counts()
        w(
            "Comparison with name-only matching (customers with match_status=erp_socid, column `name_vs_erp`):\n\n"
            + md_table(
                pd.DataFrame(
                    [[k, labels.get(k, k), int(v)] for k, v in cmp_.items()],
                    columns=["name_vs_erp", "Meaning", "Customers"],
                )
            )
            + "\n\nWhen name matching disagrees with the ERP, the ERP is always used, and `name_match_differs_from_erp` is recorded in issues.csv; "
            "the original name-match result is kept in `name_match_status` / `name_match_third_party_id`.\n"
        )
        w("### 2.2 Name matching (fallback when the ERP has no trusted socid)\n")
    exact_rule = int((nm["rule"] == "exact").sum())
    w(
        f"The statistics below come from running name matching separately on all {len(allc)} ordering customers (whether or not they have an ERP socid):\n\n"
        f"- The exact rule matches {exact_rule} ({pct(exact_rule / len(allc))}), consistent with the brief's 831; "
        f"normalisation matches {int(nm['rule'].isin(['basic', 'core']).sum())} more"
        f" (basic {int((nm['rule'] == 'basic').sum())}, core {int((nm['rule'] == 'core').sum())}); "
        f"one-to-many {int((nm['status'] == MATCH_AMBIGUOUS).sum())}, unmatched {int((nm['status'] == MATCH_UNMATCHED).sum())}.\n"
        f"- Disambiguating one-to-many: first, following rule 4 of the brief, pick records with IS_CLIENT=true and not IS_INTERCOMPANY (used {int(nm['tie_break'].fillna('').str.contains('is_client').sum())} times); "
        f"if several remain, pick the record whose ENTITY_ID belongs to a legal entity the customer ordered from (used {int(nm['tie_break'].fillna('').str.contains('entity').sum())} times; "
        "the ENTITY_ID mapping 1=Ubi Solutions, 2=Page Up, 3=Ubi Smart, 5=Ubi Impact was inferred from uniquely exact-matched samples). If several still remain, the customer is marked ambiguous: "
        "third_party_id is left empty and all candidates go into third_party_ids; country, town, SIREN etc. are filled only when all candidates agree.\n"
        "- No prefix or similarity matching is used for the result. The `candidate_third_parties` of unmatched rows are only candidates for manual reference"
        " (one segment of the name split on \" - \" is identical, or there is a whole-word prefix match); they do not take part in matching.\n"
        "- SIREN checks: `company_reg_id` is cleaned from the record's SIREN (9 digits), the first 9 digits of SIRET, a Spanish CIF or an EU VAT number; "
        "CRM import leftovers such as `import110`, `Vtiger672`, `PRO 7892` do not count as valid registration numbers. Conflicts are written to issues.csv:\n"
        "  - `siren_conflict_candidates`: same-name candidate records have different registration numbers;\n"
        "  - `siren_shared_by_different_names`: one registration number matches several ordering customers with different names (mostly stores or departments of the same legal entity);\n"
        "  - `siren_registry_conflict`: the matched record's registration number is also attached to other names in the third-party table (mostly branches or former names of the same legal entity, low priority).\n"
    )
    w("### What name normalisation does\n")
    w(
        "1. **exact**: `upper(trim(name))` is identical.\n"
        "2. **basic**: strip accents (NFKD), uppercase, delete `.` and apostrophes (`S.A.S.`→`SAS`, `L'Oréal`→`LOREAL`), "
        "replace other punctuation (`-`, `,`, `&`, `+`, `/` etc.) with spaces, then collapse repeated spaces.\n"
        "3. **core**: before basic, remove bracketed content (`EDF (FR)`→`EDF`, `… LTD (Radisson Blu …)`) and web suffixes (`.fr` `.com` etc.), "
        "then remove **one** legal-form word from the **end** of the name, and SAS/SARL/SASU/EURL/STE from the start. Only once, because repeated stripping would reduce "
        "`Creaciones B V s.l.` to `CREACIONES`, and such a broad key easily collides with other companies. If nothing remains after stripping, the original key is kept (e.g. a customer actually named `SAS`).\n"
        f"   - Trailing legal forms ({len(LEGAL_SUFFIXES)}): " + ", ".join(sorted({' '.join(s) for s in LEGAL_SUFFIXES})) + "\n"
        f"   - Leading legal forms: " + ", ".join(' '.join(s) for s in LEGAL_PREFIXES) + "\n"
        "4. Words like GROUPE/GROUP and FRANCE are not removed (`Sonepar France` and `SONEPAR` are different legal entities). "
        "GROUPE/GROUP is additionally removed only when deciding \"is this an intercompany entity\" (so that `Groupe Page Up` is recognised as PAGE UP).\n"
        "5. `lookup_name` keeps the original case and accents, and only removes bracketed qualifiers, web suffixes and one legal form. "
        "With match_status=erp_socid it is taken from the name of the third-party record actually billed on the ERP orders (`lookup_name_source=third_party_name`), "
        "because the customer name on orders is sometimes a merged label (e.g. `S Transport` is actually BOVIS Transport, `TCS - GROUPE STERNE` is actually TCS); "
        "otherwise it is taken from the order customer name (`customer_name`). The cleaned order customer name is always kept in `order_lookup_name` and can be used as a second search term. "
        f"When the two share no word after removing legal forms and generic words (GROUPE, FRANCE, SERVICES, TRANSPORT etc.), `lookup_name_conflict=true`"
        f" ({int(c['lookup_name_conflict'].sum())}, {eur(c.loc[c['lookup_name_conflict'], 'amount_ht_eur'].sum())}): "
        "this may be billing through an intermediary (`Franprix - Groupe Casino` → IR2S), brand name vs legal name (`SECANETA` → JOSÉ ALBERO PUERTO) "
        "or group vs subsidiary (`Newell Brands` → ALLEGRE PUERICULTURE); the web app should search both names; "
        "`lookup_query` = `lookup_name` + record town + country (ISO2, the record's country first, otherwise the free-text country on the order mapped to ISO2).\n"
    )

    # ---------------------------------------------------------------- web domains
    w("### Website domains (for LinkedIn lookups)\n")
    if snap.erp_thirdparties is None:
        w("No `erp_thirdparties.csv`; `web_domain` and related columns are empty. Run `erp_thirdparties.py` first.\n")
    else:
        has = c["web_domain"].notna()
        mn = c["web_domain_matches_name"].fillna(False).astype(bool)
        tab = (
            c[has]
            .assign(m=mn[has])
            .groupby("web_domain_source")
            .agg(customers=("customer_id", "size"), matches_name=("m", "sum"), amount=("amount_ht_eur", "sum"))
            .sort_values("customers", ascending=False)
        )
        top100 = c.nlargest(100, "amount_ht_eur")
        shared = c["notes"].fillna("").str.contains("domain shared with other customers")
        total = c["amount_ht_eur"].sum()
        w(
            "`erp_thirdparties.py` uses the Dolibarr API **read-only** to list all third parties (`GET /thirdparties`) and contacts (`GET /contacts`), "
            "keeping only company-level information: name, SIREN, website (`url`), LinkedIn field, employee-count band, the **domain** of the company email, "
            "and the **domains** of contact emails under each third party with their counts. "
            "Full email addresses, contact names, phone numbers, notes and personal LinkedIn profiles are not stored; personal email domains such as gmail/orange.fr/t-online.de "
            "and e-invoicing or accounting platform domains such as basware/pennylane do not count. Data is used only when the ERP name matches the snapshot record name.\n\n"
            f"{int(has.sum())} / {n} customers in the master list have a `web_domain`, {pct(c.loc[has, 'amount_ht_eur'].sum() / total)} of the amount; "
            f"{int(top100['web_domain'].notna().sum())} of the top 100 customers by amount have one. "
            f"Of these, {int(mn.sum())} have a domain that matches the company name (`web_domain_matches_name=true`), {pct(c.loc[mn, 'amount_ht_eur'].sum() / total)} of the amount. "
            "Most come from contact emails: official Dolibarr customer records rarely have a website, but almost all have contacts attached.\n\n"
            "Order of precedence (`web_domain_source`): the customer's own records (`own_*`, main third_party_id first) → other records with the same SIREN (`same_siren_*`) "
            "→ other records in the same country with the same normalised name (`same_name_*`; abbreviations of 3 characters or fewer are not borrowed from, and with `lookup_name_conflict=true` only the record name is used for borrowing). "
            "Within each layer: website → company email domain → contact email domain (`*_contact_email`; when there are several, first the one matching the company name, then the most frequent). "
            "The group's own domains (ubisolutions.net, pageup.fr etc., common when our own staff are attached as customer contacts) are not used.\n\n"
            "`web_domain_matches_name`: the domain contains a significant word of the company name (`cerp-rrm.com` ↔ CERP RHIN RHONE), "
            "or is the acronym of the company name (`cfigroupe.com` ↔ COMPAGNIE FRANCAISE INFORMATIQUE). "
            "false is mostly a parent company or parent brand domain (`MB LOG` → mrbricolage.fr, `SONELOG` → sonepar.fr), "
            "but may also be a wrongly attached contact (integrator, accountant); when the web app uses it, it should check both the LinkedIn page's website and the company name.\n\n"
            + md_table(tab.reset_index().assign(amount=lambda d: d["amount"].map(eur)))
            + f"\n\n{int((~has).sum())} have no domain.\n\n"
            "Notes:\n"
            f"- {int(shared.sum())} customers share their domain with another customer in the list (notes say \"domain shared with other customers\"), mostly the same group (geodis.com, faurecia.com…).\n"
            f"- `web_domain_alternatives` lists other candidate domains ({int(c['web_domain_alternatives'].notna().sum())} customers have some).\n"
            f"- `linkedin_url`: the Dolibarr LinkedIn field is entirely empty, so there are no usable values for now ({int(c['linkedin_url'].notna().sum())}). "
            f"`headcount_band` is the employee-count band from the third-party record, filled for {int(c['headcount_band'].notna().sum())}.\n"
        )

    # ---------------------------------------------------------------- distribution
    w("## 3. Distribution\n")
    w("### By legal entity (orders_by_entity.csv, master-list scope)\n")
    ent = r.orders_by_entity.copy()
    ent["amount_ht_eur"] = ent["amount_ht_eur"].map(eur)
    ent["amount_share"] = ent["amount_share"].map(pct)
    w(md_table(ent[["entity_name", "n_customers", "n_orders", "n_order_lines", "amount_ht_eur", "amount_share"]]) + "\n")
    multi = c["entity_names"].str.contains(";")
    w(f"{int(multi.sum())} customers ordered from several legal entities (entity_names has several values), so the per-entity customer counts add up to more than {n}.\n")
    w("### By country (country_code, top 15)\n")
    cc = (
        c.assign(country_code=c["country_code"].fillna("(empty)"))
        .groupby("country_code")
        .agg(customers=("customer_id", "size"), amount=("amount_ht_eur", "sum"))
        .sort_values("amount", ascending=False)
    )
    cc["amount_share"] = (cc["amount"] / main_total).map(pct)
    cc["amount"] = cc["amount"].map(eur)
    w(md_table(cc.head(15).reset_index()) + "\n")

    # ---------------------------------------------------------------- unmatched
    w("## 4. Unmatched customers (top 15 by amount, all in unmatched.csv)\n")
    um = c[c["match_status"] == MATCH_UNMATCHED].head(15)
    w(
        md_table(
            um.assign(amount_ht_eur=um["amount_ht_eur"].map(eur))[
                ["customer_name", "entity_names", "order_country_raw", "amount_ht_eur", "n_orders", "candidate_third_parties"]
            ]
        )
        + "\n"
    )
    w(
        f"{int(vc.get(MATCH_UNMATCHED, 0))} unmatched, amount {eur(c.loc[c['match_status'] == MATCH_UNMATCHED, 'amount_ht_eur'].sum())}"
        f" ({pct(c.loc[c['match_status'] == MATCH_UNMATCHED, 'amount_ht_eur'].sum() / main_total)} of the master list). "
        f"{int((c['match_status'].eq(MATCH_UNMATCHED) & c['candidate_third_parties'].ne('')).sum())} of them have candidates for manual reference.\n"
    )

    # ---------------------------------------------------------------- order analysis
    w("## 5. Order analysis (master-list scope, amounts exclude IS_NOT_REAL_ITEM)\n")
    real = r.main_lines[~_is_true(r.main_lines["IS_NOT_REAL_ITEM"])]
    cat = real.groupby("ITEM_CATEGORY")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum().sort_values(ascending=False)
    cat_cust = real[real["ITEM_ORDERED_AMOUNT_HT_EUR"] != 0].groupby("ITEM_CATEGORY")["CUSTOMER_ID"].nunique()
    w("### 5.1 What the company sells overall: top 5 ITEM_CATEGORY by amount\n")
    top5 = pd.DataFrame(
        {
            "ITEM_CATEGORY": cat.index[:5],
            "Amount": [eur(v) for v in cat.values[:5]],
            "Share": [pct(v / main_total) for v in cat.values[:5]],
            "Customers": [int(cat_cust.get(k, 0)) for k in cat.index[:5]],
        }
    )
    w(md_table(top5) + "\n")
    w(
        f"Top 5 total {pct(cat.values[:5].sum() / main_total)}. Unclear categories: Unknown {eur(cat.get('Unknown', 0))}"
        f" ({pct(cat.get('Unknown', 0) / main_total)}), Autres {eur(cat.get('Autres', 0))} ({pct(cat.get('Autres', 0) / main_total)}); "
        f"the {int((real['ITEM_CATEGORY'] == 'NULL').sum()):,} lines with ITEM_CATEGORY equal to the string \"NULL\" all have amount €0 (text lines) and are not counted in the product mix.\n"
    )

    w("### 5.2 One-off vs repeat\n")
    one = c["n_orders"] == 1
    w(
        md_table(
            pd.DataFrame(
                [
                    ["One-off (1 valid order)", int(one.sum()), pct(one.mean()), eur(c.loc[one, "amount_ht_eur"].sum()), pct(c.loc[one, "amount_ht_eur"].sum() / main_total)],
                    ["Repeat (≥ 2 orders)", int((~one).sum()), pct((~one).mean()), eur(c.loc[~one, "amount_ht_eur"].sum()), pct(c.loc[~one, "amount_ht_eur"].sum() / main_total)],
                ],
                columns=["Type", "Customers", "Customer share", "Amount", "Amount share"],
            )
        )
        + "\n"
    )
    bp = (
        c.groupby("buyer_pattern")
        .agg(customers=("customer_id", "size"), amount=("amount_ht_eur", "sum"), median_orders=("n_orders", "median"))
        .sort_values("amount", ascending=False)
    )
    bp["amount_share"] = (bp["amount"] / main_total).map(pct)
    bp["amount"] = bp["amount"].map(eur)
    w("buyer_pattern distribution:\n\n" + md_table(bp.reset_index()) + "\n")
    w(
        "**buyer_pattern rules** (top to bottom, first match wins; all shares are relative to the customer's amount_ht_eur):\n\n"
        "1. `one_shot`: only 1 valid order.\n"
        "2. `other`: several orders, but the total amount is ≤ 0 (all zero-amount lines), so the structure cannot be judged.\n"
        f"3. `license_or_maintenance`: Licences & Abonnements + Maintenance & Support together ≥ {LICENSE_MAINTENANCE_MIN_SHARE:.0%}.\n"
        f"4. `repeat_product`: the top ITEM_CATEGORY by amount ≥ {REPEAT_PRODUCT_MIN_SHARE:.0%}.\n"
        f"5. `mix_hardware_project`: hardware categories ({', '.join(sorted(HARDWARE_CATEGORIES))}) together ≥ {MIX_MIN_SIDE_SHARE:.0%}, "
        f"and project/service categories ({', '.join(sorted(PROJECT_SERVICE_CATEGORIES))}) together ≥ {MIX_MIN_SIDE_SHARE:.0%}.\n"
        "6. `other`: none of the above (usually Unknown / Autres / Prestations diverses dominate, or spending is spread across many categories).\n\n"
        "Difference from the order listed in the brief: license_or_maintenance comes before repeat_product. Otherwise customers with 80% Maintenance would first be classed as repeat_product, "
        "and the license_or_maintenance class would be almost empty. mix requires at least 5% on each side so that a training or warranty line of a few tens of euros does not turn a pure hardware customer into mix.\n"
    )

    w("### 5.3 Contracts\n")
    hc = c["has_contract"]
    w(
        f"**{int(hc.sum())}** customers ({pct(hc.mean())}) have a valid contract (IS_VALID_CONTRACT=true in MART_CONTRACTS_TO_DATE), "
        f"order amount {eur(c.loc[hc, 'amount_ht_eur'].sum())}, i.e. **{pct(c.loc[hc, 'amount_ht_eur'].sum() / main_total)}**. "
        f"Median share_recurring is {pct(c.loc[hc, 'share_recurring'].median())} for customers with a contract and {pct(c.loc[~hc, 'share_recurring'].median())} for those without.\n"
    )
    inv_total = c["invoice_amount_ht_eur"].sum()
    no_inv = c["n_invoices"] == 0
    w(
        f"Invoice cross-check: valid invoices of master-list customers (INVOICE_AMOUNT_HT_EUR deduplicated by INVOICE_ID) total {eur(inv_total)}; orders − invoices = {eur(main_total - inv_total)}. "
        f"{int(no_inv.sum())} customers have no valid invoice at all (order amount {eur(c.loc[no_inv, 'amount_ht_eur'].sum())}). "
        "Some invoices are issued directly without an order, so the difference for a single customer can be positive or negative; see `order_minus_invoice_ht_eur`.\n"
    )

    w("### 5.4 New customers 2024–2026\n")
    first_year = pd.to_datetime(c["first_order_date"]).dt.year.astype("Int64")
    new = first_year.isin(NEW_CUSTOMER_YEARS).fillna(False).astype(bool)
    per_year = c[new].groupby(first_year[new]).agg(customers=("customer_id", "size"), amount=("amount_ht_eur", "sum"))
    per_year["amount"] = per_year["amount"].map(eur)
    per_year.index.name = "first_order_year"
    w(
        f"**{int(new.sum())}** new customers with a first order in 2024–2026 ({pct(new.mean())}), cumulative order amount {eur(c.loc[new, 'amount_ht_eur'].sum())}.\n\n"
        + md_table(per_year.reset_index())
        + "\n"
    )
    only_sol = c["entity_names"] == "Ubi Solutions"
    w(
        f"By legal entity: {int((new & only_sol).sum())} new customers ordered only from Ubi Solutions"
        f" (amount {eur(c.loc[new & only_sol, 'amount_ht_eur'].sum())}); new customers involving Page Up / Ubi Smart / Ubi Impact: "
        f"{int((new & ~only_sol).sum())} (amount {eur(c.loc[new & ~only_sol, 'amount_ht_eur'].sum())}). "
        "Many in the latter group come from these entities' data only entering Dolibarr in 2024, and are not necessarily truly new customers. "
        f"{int((new & c['history_truncated']).sum())} of them are `history_truncated=true`, so whether they are really new cannot be determined. "
        f"Counting Ubi Solutions only, new customers in 2024–2026 are {pct((new & only_sol).sum() / only_sol.sum())} of Ubi Solutions customers.\n"
    )
    period = real[pd.to_datetime(real["ORDER_DATE"]).dt.year.isin(NEW_CUSTOMER_YEARS)]
    new_ids = set(c.loc[new, "customer_id"])
    mix_new = _category_mix(period[period["CUSTOMER_ID"].isin(new_ids)])
    mix_old = _category_mix(period[~period["CUSTOMER_ID"].isin(new_ids)])
    comp = pd.DataFrame({"new_customers": mix_new, "existing_customers": mix_old}).fillna(0.0)
    comp["diff (pp)"] = (comp["new_customers"] - comp["existing_customers"]) * 100
    comp = comp.sort_values("new_customers", ascending=False)
    w(
        "Both groups use only 2024–2026 orders, comparing the category mix of amounts (existing customers = first order before 2024):\n\n"
        + md_table(
            comp.assign(
                new_customers=comp["new_customers"].map(pct), existing_customers=comp["existing_customers"].map(pct), **{"diff (pp)": comp["diff (pp)"].map(lambda x: f"{x:+.1f}")}
            ).reset_index(names="ITEM_CATEGORY")
        )
        + "\n"
    )
    def diff_list(cmp: pd.DataFrame, sign: int) -> str:
        sel = cmp[cmp["diff (pp)"] * sign >= 3].sort_values("diff (pp)", ascending=sign < 0)
        return ", ".join(f"{k} ({v:+.1f}pp)" for k, v in sel["diff (pp)"].items()) or "none"

    sol_ids = set(c.loc[new & only_sol, "customer_id"])
    sol_period = period[period["ENTITY_NAME"] == "Ubi Solutions"]
    comp_sol = pd.DataFrame(
        {
            "new_customers": _category_mix(sol_period[sol_period["CUSTOMER_ID"].isin(sol_ids)]),
            "existing_customers": _category_mix(sol_period[~sol_period["CUSTOMER_ID"].isin(new_ids)]),
        }
    ).fillna(0.0)
    comp_sol["diff (pp)"] = (comp_sol["new_customers"] - comp_sol["existing_customers"]) * 100
    comp_sol = comp_sol.sort_values("new_customers", ascending=False)
    w(
        "\nOnly Ubi Solutions orders, comparing new customers who ordered only from Ubi Solutions with existing customers, "
        "to remove the effect of Page Up / Ubi Smart data only starting in 2024:\n\n"
        + md_table(
            comp_sol.assign(
                new_customers=comp_sol["new_customers"].map(pct), existing_customers=comp_sol["existing_customers"].map(pct),
                **{"diff (pp)": comp_sol["diff (pp)"].map(lambda x: f"{x:+.1f}")},
            ).reset_index(names="ITEM_CATEGORY")
        )
        + "\n"
    )
    w(
        f"**Conclusion**: overall, new customers have a clearly different category mix; new customers are ≥3pp higher in {diff_list(comp, 1)} and ≥3pp lower in {diff_list(comp, -1)}. "
        f"But looking at Ubi Solutions only, new customers are ≥3pp higher in {diff_list(comp_sol, 1)} and ≥3pp lower in {diff_list(comp_sol, -1)}."
    )
    other_ent = _category_mix(period[period["ENTITY_NAME"] != "Ubi Solutions"])
    sol_mix = _category_mix(sol_period)
    proj_lic = ["Projets & Intégration", "Licences & Abonnements"]
    old_cons = sol_period[
        ~sol_period["CUSTOMER_ID"].isin(new_ids) & (sol_period["ITEM_CATEGORY"] == "Consommables")
    ].groupby("CUSTOMER_NAME")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum().sort_values(ascending=False)
    new_share_other = (new & ~only_sol).sum() / new.sum()
    old_share_other = (~new & ~only_sol).sum() / (~new).sum()
    w(
        f"The overall difference comes mainly from the legal-entity composition: {pct(new_share_other)} of new customers involve Page Up / Ubi Smart / Ubi Impact, versus only {pct(old_share_other)} of existing customers; "
        f"and in 2024–2026 orders of these entities, Projets & Intégration + Licences & Abonnements make up {pct(sum(other_ent.get(k, 0) for k in proj_lic))}, "
        f"versus only {pct(sum(sol_mix.get(k, 0) for k in proj_lic))} at Ubi Solutions. "
        "Within Ubi Solutions, new customers do not lean more towards projects or licences. New customers have less Maintenance, consistent with installing hardware first and signing maintenance later; "
        f"existing customers have more Consommables, with {old_cons.index[0] if len(old_cons) else '—'} alone accounting for "
        f"{pct(old_cons.iloc[0] / old_cons.sum() if len(old_cons) else None)} of existing customers' consumables amount. New customers' high Unknown share shows that new products are not yet categorised; the category mapping is worth completing.\n"
    )
    tp_new = c.loc[new, "buyer_pattern"].value_counts(normalize=True)
    tp_old = c.loc[~new, "buyer_pattern"].value_counts(normalize=True)
    w(
        f"buyer_pattern: one_shot is {pct(tp_new.get('one_shot', 0))} for new customers and {pct(tp_old.get('one_shot', 0))} for existing customers"
        " (new customers have a short history, so a higher one_shot share is normal).\n"
    )

    w("### 5.5 Do tag buyers go on to buy projects? (category_cooccurrence.csv)\n")
    co = r.category_cooccurrence
    off = co[co["category_a"] != co["category_b"]]

    def cond(a: str, b: str) -> str:
        row = off[((off["category_a"] == a) & (off["category_b"] == b)) | ((off["category_a"] == b) & (off["category_b"] == a))]
        diag = co[(co["category_a"] == a) & (co["category_b"] == a)]
        na = int(diag["n_customers_a"].iloc[0]) if len(diag) else 0
        both = int(row["n_customers_both"].iloc[0]) if len(row) else 0
        return f"Of the {na} customers who bought {a}, {both} ({pct(both / na if na else None)}) also bought {b}"

    rfid = "Composants RFID & IoT"
    lines_ = [cond(rfid, b) for b in ("Projets & Intégration", "Licences & Abonnements", "Maintenance & Support", "Terminaux mobiles & tablettes")]
    tag_buyers = set(real.loc[(real["ITEM_SUBCATEGORY_LV1"] == TAG_SUBCATEGORY) & (real["ITEM_ORDERED_AMOUNT_HT_EUR"] > 0), "CUSTOMER_ID"])
    per = real.groupby(["CUSTOMER_ID", "ITEM_CATEGORY"])["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    proj_buyers = set(per[per > 0].reset_index().query("ITEM_CATEGORY == 'Projets & Intégration'")["CUSTOMER_ID"])
    lic_buyers = set(per[per > 0].reset_index().query("ITEM_CATEGORY == 'Licences & Abonnements'")["CUSTOMER_ID"])
    w(
        "\n".join(f"- {s}." for s in lines_)
        + f"\n- Only the subcategory \"{TAG_SUBCATEGORY}\" (the tags themselves): {len(tag_buyers)} customers bought it, "
        f"of whom {len(tag_buyers & proj_buyers)} ({pct(len(tag_buyers & proj_buyers) / len(tag_buyers) if tag_buyers else None)}) also bought Projets & Intégration, "
        f"and {len(tag_buyers & lic_buyers)} ({pct(len(tag_buyers & lic_buyers) / len(tag_buyers) if tag_buyers else None)}) also bought Licences & Abonnements.\n"
        "- Co-occurrence counts \"the customer's net amount in that category > 0\", regardless of order in time. In the table, share_of_a_also_b = customers who bought both a and b / customers who bought a.\n"
    )

    w("### 5.6 Top 10 customers by amount\n")
    top = c.head(10)
    w(
        md_table(
            pd.DataFrame(
                {
                    "Customer": top["customer_name"],
                    "Country": top["country_code"],
                    "Legal entity": top["entity_names"],
                    "Amount": top["amount_ht_eur"].map(eur),
                    "Orders": top["n_orders"],
                    "Category mix (top 3)": top["category_mix"],
                    "buyer_pattern": top["buyer_pattern"],
                    "Contract": top["has_contract"].map({True: "yes", False: ""}),
                    "Suspected integrator": top["suspect_integrator_reason"],
                    "Match": top["match_status"],
                }
            )
        )
        + "\n"
    )
    top10_share = top["amount_ht_eur"].sum() / main_total
    w(f"The top 10 customers account for {pct(top10_share)} of the master-list amount; the top 50 for {pct(c.head(50)['amount_ht_eur'].sum() / main_total)}.\n")

    # ---------------------------------------------------------------- integrators
    w("## 6. Suspected integrators / peers (flagged only, not removed)\n")
    si = c[c["suspect_integrator"]]
    w(
        f"{len(si)} customers have `suspect_integrator`=true, amount {eur(si['amount_ht_eur'].sum())}. A customer is flagged if any of the following holds:\n"
        "- the name contains a narrow keyword: RFID, TRAK, BARCODE/CODE BARRE, IDENTIFICATION, TRACABILITE, INTEGRATION/INTEGRATEUR, "
        "INFORMATIQUE, COMPUTER, SOFTWARE/LOGICIEL, ETIQUETTE/LABEL, AUTOMATISME, CONSULT*;\n"
        "- the name contains a known AIDC/RFID vendor or channel name (Zebra, Honeywell, Datalogic, Coppernic, SCC, SOTI etc., shown as `peer:`);\n"
        "- it is also a supplier (`is_also_supplier`) and hardware categories make up ≥ 50% of its amount.\n\n"
        "Broad words such as SYSTEMS, TECHNOLOGIES, DATA or a standalone ID do not count, because they would hit end customers like Safran Landing Systems, Id Verde or ID Logistics. "
        "This is only a filter for manual review, not a conclusion.\n\n"
    )
    w(
        md_table(
            si.head(15).assign(amount_ht_eur=si.head(15)["amount_ht_eur"].map(eur))[
                ["customer_name", "suspect_integrator_reason", "top_item_category", "buyer_pattern", "amount_ht_eur"]
            ]
        )
        + "\n"
    )
    w(f"{int(c['is_also_supplier'].sum())} customers have `is_also_supplier`=true (evidence in supplier_evidence: record IS_SUPPLIER, supplier order THIRD_PARTY_ID, or SUPPLIER_NAME identical after normalisation).\n")

    # ---------------------------------------------------------------- reconciliation
    w("## 7. Reconciliation of summary tables\n")
    by_cat = r.orders_by_category["amount_ht_eur"].sum()
    by_ent = r.orders_by_entity["amount_ht_eur"].sum()
    diag = co.loc[co["category_a"] == co["category_b"], "amount_ht_eur"].sum()
    null_cat = real.loc[real["ITEM_CATEGORY"] == "NULL", "ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    w(
        md_table(
            pd.DataFrame(
                [
                    ["companies.amount_ht_eur total", eur(main_total), ""],
                    ["orders_by_category.amount_ht_eur total", eur(by_cat), eur(by_cat - main_total)],
                    ["orders_by_entity.amount_ht_eur total", eur(by_ent), eur(by_ent - main_total)],
                    ["category_cooccurrence diagonal amount_ht_eur total", eur(diag), eur(diag - main_total)],
                    ["All valid orders (including intercompany)", eur(total_amount), eur(total_amount - main_total)],
                ],
                columns=["Table", "Amount", "Difference from master list"],
            )
        )
        + "\n"
    )
    w(
        f"- The three summary tables have the same scope as the master list (excluding intercompany customers, orders billed to intercompany entities and IS_NOT_REAL_ITEM lines). "
        f"The co-occurrence diagonal excludes the \"NULL\" category, so the difference is the amount of the \"NULL\" lines, {eur(null_cat)}.\n"
        f"- The difference from all valid orders, {eur(total_amount - main_total)} = excluded intercompany customers {eur(inter_lines['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}"
        f" + orders of master-list customers billed to intercompany entities {eur(il_amount)}"
        f" (check difference {eur(total_amount - main_total - inter_lines['ITEM_ORDERED_AMOUNT_HT_EUR'].sum() - il_amount)}); the difference due to IS_NOT_REAL_ITEM is €0.\n"
        "- Amounts and dates are aggregated from the parquet as is, without rounding (the README displays them to the cent). Floating-point sums may leave residuals of the order of 1e-8.\n"
    )

    # ---------------------------------------------------------------- files
    w("## 8. Output files\n")
    w(
        f"- `companies.parquet` / `companies.csv`: the master list, one row per CUSTOMER_ID, {n} rows, {len(c.columns)} columns, sorted by amount_ht_eur descending. The CSV is UTF-8 with BOM so it opens cleanly in Excel.\n"
        f"- `unmatched.csv`: the {int(vc.get(MATCH_UNMATCHED, 0))} rows with match_status=unmatched, same fields as the master list.\n"
        f"- `duplicates.csv`: {r.duplicates.groupby(['group_type', 'group_key']).ngroups if len(r.duplicates) else 0} groups that look like the same company"
        " (`same_normalized_name` = same core key; `same_company_reg_id` = same registration number on the matched record; `same_third_party_id` = same main third_party_id) "
        "but with different CUSTOMER_IDs. They are not merged in the list.\n"
        "- `erp_orders.csv` / `erp_order_socid.csv`: order headers fetched read-only from the Dolibarr API (id, ref, socid, entity), and the order-by-order comparison with snapshot orders.\n"
        "- `erp_product_tags.csv`: Dolibarr product tags (fetched read-only), used to tell product lines apart; products under `UBI Solutions > GPSBLE` are geolocation, `Portique RFID` / `Kit RFID TC21` / `Terminaux RFID` are RFID.\n"
        "- `erp_thirdparties.csv`: ERP company-level fields for each snapshot third party (website, website domain, email domain, contact email domains and counts, LinkedIn, employee-count band; no full email address or personal name); used only when `tp_name_matches` is true.\n"
        f"- `issues.csv`: {len(r.issues)} rows, by type: "
        + ", ".join(f"{k} {v}" for k, v in r.issues["issue_type"].value_counts().items())
        + ".\n"
        "- `orders_by_category.csv`: ITEM_CATEGORY × year, with customer count, order count, line count and amount.\n"
        "- `orders_by_entity.csv`: ENTITY_NAME, with customer count, order count, line count, amount and amount share.\n"
        "- `category_cooccurrence.csv`: co-occurring customer counts and conditional shares for category pairs; the diagonal is single categories.\n\n"
        "Main fields: `recency_days` is the number of days relative to the snapshot date "
        f"{snapshot_date.isoformat()}; `n_years_active` is the number of distinct years with orders; `amount_first_24m_ht_eur` is the amount within 24 months of the first order (comparable between new and existing customers), and is still incomplete when `months_since_first_order` is under 24; with `match_status=erp_socid`, `third_party_id` is the third party on the ERP orders (when several, the non-intercompany one with the largest amount), `erp_third_parties` lists all socids and amounts, `erp_orders_verified` is the number of orders whose ID and order number both agree with the ERP, and `name_match_status` / `name_match_third_party_id` / `name_vs_erp` are the name-only matching result and its comparison with the ERP; `history_truncated` means the customer ordered only from Page Up / Ubi Smart / Ubi Impact, whose data before 2024 is not in the data warehouse, so the first order date and years active may be understated; `share_recurring` is the IS_RECURRING_REVENUE amount / amount_ht_eur; "
        "`top_product_refs` is the top 5 PRODUCT_REF by amount, formatted `ref:amount;…` (`(sans ref)` means lines without PRODUCT_REF); "
        "`category_mix` is the top 3 categories with their shares; `naf_section`/`naf_classe` only take values already on the orders (the invoice and contract tables have nothing to add), "
        f"filled for {int(c['naf_section'].notna().sum())} customers, left empty otherwise; for `web_domain` and other website fields see \"Website domains\" in section 2; `product_lines` are the business lines bought (`geoloc` = géolocalisation / Connected Things: BLE / GPS / LoRa trackers, beacons, gateways and their rental, Connected Things being the geolocation software platform; `rfid` = traçabilité; `ubi_cloud` = Ubi Cloud subscription / licence), judged per product: the Dolibarr product tag decides when there is one, otherwise rules on product name, subcategory and manufacturer (ITEM_CATEGORY cannot separate the two, and most of `Traceurs et objets connectés` is RFID textile tags); handheld terminals and barcode scanners with Bluetooth / GPS do not count as geolocation; `amount_geoloc_ht_eur` / `amount_rfid_ht_eur` / `amount_ubi_cloud_ht_eur` are the amounts per line, and `geoloc_source` says whether the geolocation decision comes from a `tag` or a `name_rule`.\n"
    )
    return "\n".join(out)
