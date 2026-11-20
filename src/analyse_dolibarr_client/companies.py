"""Build the list of companies with valid customer orders (CO) from a raw snapshot.

Reads data/raw/<snapshot>/*.parquet (read-only) and writes data/processed/<snapshot>/:
companies.parquet/.csv, unmatched.csv, duplicates.csv, issues.csv,
orders_by_category.csv, orders_by_entity.csv, category_cooccurrence.csv, README.md.

Customers (CUSTOMER_ID, a hash) are linked to the third-party registry by NAME only:
CUSTOMER_ID and THIRD_PARTY_ID live in different key spaces and must never be joined.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from pathlib import Path

import pandas as pd

from analyse_dolibarr_client.names import (
    basic_key,
    core_key,
    country_iso,
    domain_matches_name,
    exact_key,
    group_free_key,
    integrator_keywords,
    lookup_name,
    name_notes,
    names_unrelated,
)
from analyse_dolibarr_client.product_lines import TAGS_NAME, add_product_lines, customer_product_lines

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = "2026-11-18"

# ENTITY_ID in MART_THIRD_PARTIES -> ENTITY_NAME in the orders mart. Derived from the
# 2026-11-18 snapshot: among customers with a single exact name match, Ubi Solutions
# orders land on ENTITY_ID 1 (602), Page Up on 2 (64), Ubi Smart on 3 (38), Ubi Impact on 5.
ENTITY_ID_TO_NAME = {"1": "Ubi Solutions", "2": "Page Up", "3": "Ubi Smart", "5": "Ubi Impact"}

# Entities whose orders and invoices in the datahub only start in 2023-2024 (Page Up: 4 orders
# in 2023, then 425 in 2024), while Ubi Solutions goes back to 2016. A customer seen only in
# these entities may have older history that was never loaded, so its first_order_date,
# n_years_active and "new customer" status are not reliable.
LATE_HISTORY_ENTITIES = frozenset({"Page Up", "Ubi Smart", "Ubi Impact"})

# Window for amount_first_24m_ht_eur.
FIRST_SPEND_MONTHS = 24

HARDWARE_CATEGORIES = frozenset(
    {
        "Composants RFID & IoT",
        "Terminaux mobiles & tablettes",
        "Consommables",
        "Imprimantes",
        "Batteries",
    }
)
PROJECT_SERVICE_CATEGORIES = frozenset(
    {
        "Projets & Intégration",
        "Maintenance & Support",
        "Licences & Abonnements",
        "Formation",
    }
)
LICENSE_MAINTENANCE_CATEGORIES = frozenset({"Licences & Abonnements", "Maintenance & Support"})
# ITEM_CATEGORY values that mean "no category" (the mart stores the string "NULL").
MISSING_CATEGORY = frozenset({"NULL", ""})

ONE_SHOT_MAX_ORDERS = 1
REPEAT_PRODUCT_MIN_SHARE = 0.7
LICENSE_MAINTENANCE_MIN_SHARE = 0.5
MIX_MIN_SIDE_SHARE = 0.05

MATCH_ERP = "erp_socid"  # the order's own third party (socid) read from the ERP API
MATCH_EXACT = "exact"
MATCH_NORMALIZED = "normalized"
MATCH_AMBIGUOUS = "ambiguous"
MATCH_UNMATCHED = "unmatched"

_REG_ID_JUNK = re.compile(r"^(IMPORT|VTIGER)", re.IGNORECASE)


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def clean_company_id(siren: object, siret: object = None) -> str | None:
    """Return a usable company registration id from the SIREN/SIRET fields, or None.

    Accepts a French SIREN (9 digits), the SIREN part of a 14-digit SIRET, a Spanish
    CIF/NIF (letter + 7 digits + check char) and EU VAT numbers. Rejects CRM import
    artefacts such as "import110" / "Vtiger672" and short codes such as "PL121".
    """
    for raw in (siren, siret):
        if not isinstance(raw, str) or _REG_ID_JUNK.match(raw.strip()):
            continue
        val = re.sub(r"[\s.\-/]", "", raw).upper()
        if re.fullmatch(r"\d{9}", val):
            return val
        if re.fullmatch(r"\d{14}", val):
            return val[:9]
        if raw is siren:
            if re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", val):
                return val
            if re.fullmatch(r"[A-Z]{2}[0-9A-Z]{8,12}", val) and sum(c.isdigit() for c in val) >= 8:
                return val
    return None


def _join(values) -> str:
    return ";".join(str(v) for v in values if v is not None and v == v and str(v) != "")


def _first_notna(series: pd.Series):
    s = series.dropna()
    return s.iloc[0] if len(s) else None


def _is_true(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------


@dataclass
class Snapshot:
    snapshot: str
    orders: pd.DataFrame  # valid order lines only
    orders_all_rows: int
    third_parties: pd.DataFrame
    supplier_orders: pd.DataFrame
    invoices: pd.DataFrame  # valid invoice lines only
    contracts: pd.DataFrame  # valid contract lines only
    # Per valid order: ORDER_ID, erp_socid, socid_trusted (from erp_socid.py); optional.
    erp_order_socid: pd.DataFrame | None = None
    # Per third party: website / email domain / LinkedIn from erp_thirdparties.py; optional.
    erp_thirdparties: pd.DataFrame | None = None
    # Product catalog (names) and Dolibarr product tags (product_lines.py); optional.
    product_catalog: pd.DataFrame | None = None
    product_tags: pd.DataFrame | None = None


def load_snapshot(
    raw_dir: Path,
    snapshot: str,
    erp_socid_path: Path | None = None,
    erp_tp_path: Path | None = None,
    product_tags_path: Path | None = None,
) -> Snapshot:
    d = raw_dir / snapshot
    erp = None
    if erp_socid_path is not None and erp_socid_path.exists():
        erp = pd.read_csv(erp_socid_path, dtype=str)
        erp["socid_trusted"] = erp["socid_trusted"].eq("True")
    web = None
    if erp_tp_path is not None and erp_tp_path.exists():
        web = pd.read_csv(erp_tp_path, dtype=str)
        web = web[web["tp_name_matches"].eq("True")]
    orders = pd.read_parquet(d / "mart_orders_to_date.parquet")
    valid = orders[_is_true(orders["IS_VALID_ORDER"])].copy()
    invoices = pd.read_parquet(d / "mart_invoicing_to_date.parquet")
    contracts = pd.read_parquet(d / "mart_contracts_to_date.parquet")
    return Snapshot(
        snapshot=snapshot,
        orders=valid,
        orders_all_rows=len(orders),
        third_parties=pd.read_parquet(d / "mart_third_parties.parquet"),
        supplier_orders=pd.read_parquet(d / "mart_supplier_orders_to_date.parquet"),
        invoices=invoices[_is_true(invoices["IS_VALID_INVOICE"])].copy(),
        contracts=contracts[_is_true(contracts["IS_VALID_CONTRACT"])].copy(),
        erp_order_socid=erp,
        erp_thirdparties=web,
        product_catalog=pd.read_parquet(d / "mart_product_catalog.parquet")
        if (d / "mart_product_catalog.parquet").exists()
        else None,
        product_tags=pd.read_csv(product_tags_path, dtype=str)
        if product_tags_path is not None and product_tags_path.exists()
        else None,
    )


# --------------------------------------------------------------------------------------
# Name matching
# --------------------------------------------------------------------------------------


@dataclass
class MatchResult:
    status: str
    rule: str | None = None  # exact | basic | core
    third_party_id: str | None = None
    candidate_ids: list[str] = field(default_factory=list)  # all same-name registry rows
    chosen_ids: list[str] = field(default_factory=list)  # after tie-break filters
    is_intercompany: bool = False
    tie_break: str | None = None


def prepare_third_parties(tp: pd.DataFrame) -> pd.DataFrame:
    tp = tp.copy()
    tp["THIRD_PARTY_ID"] = tp["THIRD_PARTY_ID"].astype(str)
    tp["ENTITY_ID"] = tp["ENTITY_ID"].astype(str)
    for col in ("IS_CLIENT", "IS_SUPPLIER", "IS_INTERCOMPANY"):
        tp[col] = _is_true(tp[col])
    tp["k_exact"] = tp["THIRD_PARTY_NAME"].map(exact_key)
    tp["k_basic"] = tp["THIRD_PARTY_NAME"].map(basic_key)
    tp["k_core"] = tp["THIRD_PARTY_NAME"].map(core_key)
    tp["k_group_free"] = tp["THIRD_PARTY_NAME"].map(group_free_key)
    tp["company_id"] = [clean_company_id(a, b) for a, b in zip(tp["SIREN"], tp["SIRET"])]
    tp["entity_name"] = tp["ENTITY_ID"].map(ENTITY_ID_TO_NAME)
    return tp.set_index("THIRD_PARTY_ID", drop=False)


def _index_by(tp: pd.DataFrame, col: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for key, tid in zip(tp[col], tp["THIRD_PARTY_ID"]):
        if key:
            out.setdefault(key, []).append(tid)
    return out


class NameMatcher:
    def __init__(self, tp: pd.DataFrame):
        self.tp = tp
        self.by_exact = _index_by(tp, "k_exact")
        self.by_basic = _index_by(tp, "k_basic")
        self.by_core = _index_by(tp, "k_core")
        self.intercompany_group_free = set(tp.loc[tp["IS_INTERCOMPANY"], "k_group_free"].dropna())

    def match(self, name: object, entities: set[str]) -> MatchResult:
        cands: list[str] = []
        rule = None
        for rule_name, index, keyfn in (
            ("exact", self.by_exact, exact_key),
            ("basic", self.by_basic, basic_key),
            ("core", self.by_core, core_key),
        ):
            key = keyfn(name)
            if key and key in index:
                cands, rule = index[key], rule_name
                break

        rows = self.tp.loc[cands] if cands else self.tp.iloc[0:0]
        intercompany = bool(rows["IS_INTERCOMPANY"].any()) or (
            group_free_key(name) in self.intercompany_group_free
        )
        if not cands:
            return MatchResult(MATCH_UNMATCHED, is_intercompany=intercompany)

        status = MATCH_EXACT if rule == "exact" else MATCH_NORMALIZED
        chosen, steps = rows, []
        # Rule 4: prefer IS_CLIENT and not intercompany.
        if len(chosen) > 1:
            pref = chosen[chosen["IS_CLIENT"] & ~chosen["IS_INTERCOMPANY"]]
            if 0 < len(pref) < len(chosen):
                chosen, steps = pref, steps + ["is_client"]
        # Extra tie-break: registry rows belonging to the legal entity the customer ordered from.
        if len(chosen) > 1:
            pref = chosen[chosen["entity_name"].isin(entities)]
            if 0 < len(pref) < len(chosen):
                chosen, steps = pref, steps + ["entity"]
        chosen_ids = list(chosen["THIRD_PARTY_ID"])
        if len(chosen_ids) == 1:
            return MatchResult(
                status, rule, chosen_ids[0], list(cands), chosen_ids, intercompany,
                "+".join(steps) or None,
            )
        return MatchResult(
            MATCH_AMBIGUOUS, rule, None, list(cands), chosen_ids, intercompany,
            "+".join(steps) or None,
        )

    def hints(self, name: object, limit: int = 5) -> list[str]:
        """Candidate registry names for manual review of unmatched customers.

        NOT used as a match: whole-token prefix of the core key, or a " - " segment.
        """
        key = core_key(name)
        if not key:
            return []
        found: list[str] = []
        raw = name if isinstance(name, str) else ""
        for seg in re.split(r"\s[-–/]\s|,", raw):
            seg_key = core_key(seg)
            if seg_key and seg_key != key and len(seg_key) >= 4 and seg_key in self.by_core:
                found += self.by_core[seg_key]
        if len(key) >= 5:
            for k, ids in self.by_core.items():
                if k.startswith(key + " ") or (len(k) >= 6 and " " in k and key.startswith(k + " ")):
                    found += ids
        out, seen = [], set()
        for tid in found:
            if tid not in seen:
                seen.add(tid)
                out.append(f"{tid}:{self.tp.at[tid, 'THIRD_PARTY_NAME']}")
            if len(out) >= limit:
                break
        return out


# --------------------------------------------------------------------------------------
# Order metrics
# --------------------------------------------------------------------------------------


def _category(series: pd.Series) -> pd.Series:
    return series.where(~series.isin(MISSING_CATEGORY) & series.notna(), None)


def classify_buyer(n_orders: int, amount: float, cat_amounts: dict[str, float]) -> str:
    """See README 'buyer_pattern' for the rules; precedence is top to bottom."""
    if n_orders <= ONE_SHOT_MAX_ORDERS:
        return "one_shot"
    if not amount or amount <= 0:
        return "other"
    share = {k: v / amount for k, v in cat_amounts.items()}
    if sum(share.get(c, 0.0) for c in LICENSE_MAINTENANCE_CATEGORIES) >= LICENSE_MAINTENANCE_MIN_SHARE:
        return "license_or_maintenance"
    if share and max(share.values()) >= REPEAT_PRODUCT_MIN_SHARE:
        return "repeat_product"
    hw = sum(v for k, v in share.items() if k in HARDWARE_CATEGORIES)
    ps = sum(v for k, v in share.items() if k in PROJECT_SERVICE_CATEGORIES)
    if hw >= MIX_MIN_SIDE_SHARE and ps >= MIX_MIN_SIDE_SHARE:
        return "mix_hardware_project"
    return "other"


def order_metrics(lines: pd.DataFrame, snapshot_date: date) -> pd.DataFrame:
    """Per-CUSTOMER_ID order aggregates. `lines` are valid order lines."""
    lines = lines.copy()
    lines["is_real"] = ~_is_true(lines["IS_NOT_REAL_ITEM"])
    lines["amount_real"] = lines["ITEM_ORDERED_AMOUNT_HT_EUR"].where(lines["is_real"], 0.0)
    lines["amount_recurring"] = lines["amount_real"].where(_is_true(lines["IS_RECURRING_REVENUE"]), 0.0)
    lines["category"] = _category(lines["ITEM_CATEGORY"])
    lines["year"] = pd.to_datetime(lines["ORDER_DATE"]).dt.year

    g = lines.groupby("CUSTOMER_ID", sort=False)
    m = pd.DataFrame(
        {
            "customer_name": g["CUSTOMER_NAME"].agg(_first_notna),
            "entity_names": g["ENTITY_NAME"].agg(lambda s: _join(sorted(s.dropna().unique()))),
            "order_country_raw": g["COUNTRY_CODE"].agg(_first_notna),
            "first_order_date": g["ORDER_DATE"].min(),
            "last_order_date": g["ORDER_DATE"].max(),
            "n_orders": g["ORDER_ID"].nunique(),
            "n_order_lines": g.size(),
            "n_not_real_lines": g["is_real"].agg(lambda s: int((~s).sum())),
            "amount_ht_eur": g["amount_real"].sum(),
            "amount_recurring_ht_eur": g["amount_recurring"].sum(),
            "n_years_active": g["year"].nunique(),
            "naf_section": g["SECTION"].agg(_first_notna),
            "naf_classe": g["CLASSE"].agg(_first_notna),
        }
    )
    snap = pd.Timestamp(snapshot_date)
    m["recency_days"] = (snap - pd.to_datetime(m["last_order_date"])).dt.days.astype("Int64")
    # Spend in the first 24 months after the first order: comparable between old and new
    # customers (lifetime totals favour old ones). Only meaningful when months_since_first_order >= 24.
    odate = pd.to_datetime(lines["ORDER_DATE"])
    first = odate.groupby(lines["CUSTOMER_ID"]).transform("min")
    in_window = odate < first + pd.DateOffset(months=FIRST_SPEND_MONTHS)
    m["amount_first_24m_ht_eur"] = lines["amount_real"].where(in_window, 0.0).groupby(lines["CUSTOMER_ID"]).sum()
    first_ts = pd.to_datetime(m["first_order_date"])
    m["months_since_first_order"] = ((snap.year - first_ts.dt.year) * 12 + (snap.month - first_ts.dt.month)).astype("Int64")
    m["share_recurring"] = m["amount_recurring_ht_eur"] / m["amount_ht_eur"].where(m["amount_ht_eur"] != 0)

    real = lines[lines["is_real"]]
    cat_amt = real.dropna(subset=["category"]).groupby(["CUSTOMER_ID", "category"])["amount_real"].sum()
    ref_amt = (
        real.assign(ref=real["PRODUCT_REF"].fillna("(sans ref)"))
        .loc[real["category"].notna() | real["PRODUCT_REF"].notna()]
        .groupby(["CUSTOMER_ID", "ref"])["amount_real"]
        .sum()
    )

    cat_rows = []
    for cid, row in m.iterrows():
        cats = cat_amt.get(cid, pd.Series(dtype=float))
        cats = cats.sort_values(ascending=False, kind="stable") if len(cats) else cats
        amount = row["amount_ht_eur"]
        cat_dict = {k: float(v) for k, v in cats.items()}
        top_cat = cats.index[0] if len(cats) and cats.iloc[0] > 0 else None
        refs = ref_amt.get(cid, pd.Series(dtype=float))
        refs = refs[refs != 0].sort_values(ascending=False, kind="stable").head(5)

        def share(keys, cat_dict=cat_dict, amount=amount):
            if not amount:
                return None
            return sum(v for k, v in cat_dict.items() if k in keys) / amount

        cat_rows.append(
            {
                "CUSTOMER_ID": cid,
                "item_categories": _join(cats.index),
                "top_item_category": top_cat,
                "top_item_category_share": (cat_dict[top_cat] / amount) if top_cat and amount else None,
                "hardware_share": share(HARDWARE_CATEGORIES),
                "project_service_share": share(PROJECT_SERVICE_CATEGORIES),
                "license_maintenance_share": share(LICENSE_MAINTENANCE_CATEGORIES),
                "top_product_refs": ";".join(f"{r}:{a:.2f}" for r, a in refs.items()),
                "category_mix": ";".join(
                    f"{k}:{v / amount:.0%}" for k, v in list(cat_dict.items())[:3]
                )
                if amount
                else "",
                "buyer_pattern": classify_buyer(int(row["n_orders"]), amount, cat_dict),
            }
        )
    m = m.join(pd.DataFrame(cat_rows).set_index("CUSTOMER_ID"))
    if "product_line" in lines.columns:
        m = m.join(customer_product_lines(lines, "amount_real"))
        m["amount_geoloc_ht_eur"] = m["amount_geoloc_ht_eur"].fillna(0.0)
        m["amount_rfid_ht_eur"] = m["amount_rfid_ht_eur"].fillna(0.0)
        m["amount_ubi_cloud_ht_eur"] = m["amount_ubi_cloud_ht_eur"].fillna(0.0)
        m["product_lines"] = m["product_lines"].fillna("")
    return m


def invoice_metrics(invoices: pd.DataFrame) -> pd.DataFrame:
    headers = invoices.drop_duplicates("INVOICE_ID")
    g = headers.groupby("CUSTOMER_ID")
    out = pd.DataFrame(
        {
            "n_invoices": g["INVOICE_ID"].nunique(),
            "invoice_amount_ht_eur": g["INVOICE_AMOUNT_HT_EUR"].sum(),
        }
    )
    flagged = invoices[_is_true(invoices["IS_INTERCOMPANY"])].groupby("CUSTOMER_ID")["INVOICE_ID"].nunique()
    out["n_invoices_flagged_intercompany"] = flagged
    return out


def contract_metrics(contracts: pd.DataFrame) -> pd.DataFrame:
    g = contracts.groupby("CUSTOMER_ID")
    return pd.DataFrame({"n_contracts": g["CONTRACT_ID"].nunique()})


# --------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------

@dataclass
class ErpThirdParties:
    """Trusted ERP socids of one CUSTOMER_ID, primary first."""

    ids: list[str]
    amounts: list[float]
    n_orders_verified: int
    all_intercompany: bool
    any_intercompany: bool


def erp_third_parties(orders: pd.DataFrame, erp: pd.DataFrame | None, tp: pd.DataFrame) -> dict[str, ErpThirdParties]:
    """Group each customer's orders by their ERP socid (only orders whose id and ref agree).

    The primary third party is the non-intercompany socid with the largest real order
    amount (then the most orders); the others are kept in order of amount.
    """
    if erp is None or not len(erp):
        return {}
    trusted = erp.loc[erp["socid_trusted"], ["ORDER_ID", "erp_socid"]].drop_duplicates("ORDER_ID")
    lines = orders.merge(trusted, on="ORDER_ID", how="inner")
    lines = lines[lines["erp_socid"].isin(tp.index)]
    amount = lines["ITEM_ORDERED_AMOUNT_HT_EUR"].where(~_is_true(lines["IS_NOT_REAL_ITEM"]), 0.0)
    agg = (
        lines.assign(amount=amount)
        .groupby(["CUSTOMER_ID", "erp_socid"])
        .agg(amount=("amount", "sum"), n_orders=("ORDER_ID", "nunique"))
        .reset_index()
    )
    agg["interco"] = agg["erp_socid"].map(tp["IS_INTERCOMPANY"]).fillna(False).astype(bool)
    agg = agg.sort_values(["CUSTOMER_ID", "interco", "amount", "n_orders"], ascending=[True, True, False, False], kind="stable")
    out = {}
    for cid, g in agg.groupby("CUSTOMER_ID", sort=False):
        out[cid] = ErpThirdParties(
            ids=list(g["erp_socid"]),
            amounts=[float(a) for a in g["amount"]],
            n_orders_verified=int(g["n_orders"].sum()),
            all_intercompany=bool(g["interco"].all()),
            any_intercompany=bool(g["interco"].any()),
        )
    return out


def intercompany_order_ids(erp: pd.DataFrame | None, tp: pd.DataFrame) -> set[str]:
    """ORDER_IDs whose trusted ERP socid is an internal company (IS_INTERCOMPANY)."""
    if erp is None or not len(erp):
        return set()
    t = erp[erp["socid_trusted"]]
    interco = set(tp.index[tp["IS_INTERCOMPANY"]])
    return set(t.loc[t["erp_socid"].isin(interco), "ORDER_ID"])


def _name_vs_erp(name_res: "MatchResult", primary: str, tp: pd.DataFrame) -> str:
    if name_res.status == MATCH_UNMATCHED:
        return "name_unmatched"
    if name_res.status == MATCH_AMBIGUOUS:
        return "erp_in_name_candidates" if primary in name_res.chosen_ids else "name_ambiguous_other"
    if name_res.third_party_id == primary:
        return "same"
    if tp.at[name_res.third_party_id, "k_core"] == tp.at[primary, "k_core"]:
        return "same_name_other_row"
    return "different"


COMPANY_COLUMNS = [
    "customer_id", "customer_name", "lookup_name", "lookup_name_source", "order_lookup_name", "lookup_name_conflict", "lookup_query",
    "entity_names",
    "country_code", "order_country_raw", "town", "zip_code", "siren", "siret", "tax_number",
    "company_reg_id", "web_domain", "web_domain_source", "web_domain_matches_name", "website", "web_domain_alternatives",
    "linkedin_url", "headcount_band",
    "third_party_id", "third_party_ids", "third_party_name", "match_status",
    "match_rule", "tie_break", "erp_third_parties", "erp_orders_verified", "name_match_status",
    "name_match_third_party_id", "name_vs_erp", "tp_is_client", "is_also_supplier", "supplier_evidence",
    "is_intercompany", "suspect_integrator", "suspect_integrator_reason",
    "first_order_date", "history_truncated", "last_order_date", "recency_days", "n_years_active", "n_orders",
    "n_order_lines", "amount_ht_eur", "amount_first_24m_ht_eur", "months_since_first_order", "intercompany_excluded_ht_eur", "amount_recurring_ht_eur", "share_recurring",
    "n_invoices", "invoice_amount_ht_eur", "order_minus_invoice_ht_eur", "has_contract",
    "n_contracts", "item_categories", "category_mix", "top_item_category",
    "top_item_category_share", "hardware_share", "project_service_share",
    "license_maintenance_share", "top_product_refs", "buyer_pattern",
    "product_lines", "amount_geoloc_ht_eur", "amount_rfid_ht_eur", "amount_ubi_cloud_ht_eur", "geoloc_source", "naf_section",
    "naf_classe", "candidate_third_parties", "notes",
]


@dataclass
class BuildResult:
    companies: pd.DataFrame  # main list, intercompany excluded
    all_customers: pd.DataFrame  # every CUSTOMER_ID with a valid order
    duplicates: pd.DataFrame
    issues: pd.DataFrame
    orders_by_category: pd.DataFrame
    orders_by_entity: pd.DataFrame
    category_cooccurrence: pd.DataFrame
    main_lines: pd.DataFrame  # valid order lines of main-list customers
    # Valid order lines billed to an internal company, removed from main-list amounts.
    intercompany_lines: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Name-matching result for every customer, kept even when the ERP socid wins.
    name_matches: pd.DataFrame = field(default_factory=pd.DataFrame)


WEB_COLUMNS = [
    "web_domain", "web_domain_source", "web_domain_matches_name", "website", "web_domain_alternatives",
    "linkedin_url", "headcount_band",
]
# The group's own domains: a customer record carrying one was filled in with our address.
GROUP_DOMAINS = frozenset({"ubisolutions.net", "ubi-solutions.com", "ubisolutions.fr", "pageup.fr", "ubismart.fr", "ubi-impact.com"})


def attach_web_hints(cust: pd.DataFrame, web: pd.DataFrame | None, tp: pd.DataFrame) -> pd.DataFrame:
    """Add a company web domain per customer, from the ERP third-party records.

    Tiers, best first: the customer's own third parties (primary first), then any third
    party with the same SIREN, then one with the same normalized name in the same country
    (names of 3 characters or less are skipped: acronyms collide). Within a tier a website
    beats the company email domain, which beats the domains of its contacts' emails
    (``*_contact_email``; among those, one that matches the company name first, then the
    most frequent). ``web_domain_source`` says which tier and kind won, e.g. ``own_website``
    or ``same_siren_contact_email``; other domains seen are kept as alternatives.
    ``web_domain_matches_name`` says whether the domain visibly belongs to the name.
    The group's own domains (and any on an intercompany record) are never used.
    """
    out = cust.copy()
    for col in WEB_COLUMNS:
        out[col] = None
    if web is None or web.empty:
        return out
    w = web.merge(
        tp[["THIRD_PARTY_ID", "COUNTRY_CODE", "IS_INTERCOMPANY"]].astype({"THIRD_PARTY_ID": str}),
        how="left",
        on="THIRD_PARTY_ID",
    ).set_index("THIRD_PARTY_ID", drop=False)
    group = set(GROUP_DOMAINS) | set(
        w.loc[w["IS_INTERCOMPANY"].fillna(False).astype(bool), ["website_domain", "email_domain"]].stack().dropna()
    )
    for col in ("website_domain", "email_domain"):
        w[col] = w[col].where(~w[col].isin(group))
    w["website"] = w["website"].where(w["website_domain"].notna())
    if "contact_email_domains" not in w.columns:
        w["contact_email_domains"] = None
    # "a.com:3;b.fr:1" -> ["a.com", "b.fr"] (most frequent first), group domains removed.
    w["contact_list"] = [
        [d for d in (part.rsplit(":", 1)[0] for part in v.split(";")) if d not in group] if isinstance(v, str) else []
        for v in w["contact_email_domains"]
    ]
    w["has_contact"] = w["contact_list"].map(bool)
    w["siren9"] = w["SIREN"].fillna("").str.replace(" ", "", regex=False)
    w["name_key"] = w["THIRD_PARTY_NAME"].map(core_key)
    has_dom = w["website_domain"].notna() | w["email_domain"].notna() | w["has_contact"]
    by_siren = {k: g for k, g in w[has_dom & w["siren9"].str.fullmatch(r"\d{9}")].groupby("siren9")}
    by_name = {k: g for k, g in w[has_dom & w["name_key"].notna()].groupby(["name_key", "COUNTRY_CODE"])}

    def candidates(rows: pd.DataFrame, tier: str, names: tuple) -> list[tuple[str, str, str | None]]:
        found = []
        for kind, col in (("website", "website_domain"), ("email", "email_domain")):
            for _, r in rows.iterrows():
                if isinstance(r[col], str):
                    found.append((r[col], f"{tier}_{kind}", r["website"] if kind == "website" else None))
        contact = [d for lst in rows["contact_list"] for d in lst]
        contact.sort(key=lambda d: not domain_matches_name(d, *names))  # stable: keeps frequency order
        found += [(d, f"{tier}_contact_email", None) for d in contact]
        return found

    for i, c in out.iterrows():
        # Order name left out when it conflicts with the registry name (likely the end customer).
        names = (c["lookup_name"], c.get("third_party_name")) + (() if c["lookup_name_conflict"] else (c["order_lookup_name"],))
        own_ids = [x for x in str(c["third_party_ids"] or "").split(";") if x]
        if isinstance(c["third_party_id"], str) and c["third_party_id"] in own_ids:
            own_ids.remove(c["third_party_id"])
            own_ids.insert(0, c["third_party_id"])
        own = w.loc[[x for x in own_ids if x in w.index]]
        found = candidates(own, "own", names)
        siren = str(c["siren"] or "").replace(" ", "")
        if siren in by_siren:
            found += candidates(by_siren[siren].drop(index=own.index, errors="ignore"), "same_siren", names)
        # When the order name and the registry name are unrelated, the order name is often
        # the end customer (EXERTIS AZENN ordering "for Orange"): borrow by registry name only.
        names = [c["lookup_name"]] if c["lookup_name_conflict"] else [c["lookup_name"], c["order_lookup_name"]]
        for nm in names:
            key = core_key(nm)
            if key and len(key) > 3 and (key, c["country_code"]) in by_name:
                found += candidates(by_name[(key, c["country_code"])].drop(index=own.index, errors="ignore"), "same_name", names)
        linkedin = own["linkedin_url"].dropna()
        heads = own["headcount_band"].dropna()
        out.at[i, "linkedin_url"] = linkedin.iloc[0] if len(linkedin) else None
        out.at[i, "headcount_band"] = heads.iloc[0] if len(heads) else None
        if not found:
            continue
        dom, source, site = found[0]
        out.at[i, "web_domain"] = dom
        out.at[i, "web_domain_source"] = source
        out.at[i, "web_domain_matches_name"] = domain_matches_name(dom, *names)
        out.at[i, "website"] = site
        out.at[i, "web_domain_alternatives"] = _join(dict.fromkeys(d for d, _, _ in found if d != dom)) or None

    shared = out["web_domain"].map(out["web_domain"].value_counts())
    note = "域名与其他客户共用"
    out["notes"] = [
        _join([n, note]) if isinstance(d, str) and s > 1 else n
        for n, d, s in zip(out["notes"], out["web_domain"], shared)
    ]
    return out


def _agree(rows: pd.DataFrame, col: str):
    """The value all candidate rows agree on (ignoring case/accents/blanks), else None."""
    vals = [v for v in rows[col] if isinstance(v, str) and v.strip()]
    keys = {basic_key(v) for v in vals}
    return vals[0] if len(keys) == 1 else None


def build(snap: Snapshot, snapshot_date: date) -> BuildResult:
    tp = prepare_third_parties(snap.third_parties)
    matcher = NameMatcher(tp)
    orders = snap.orders
    erp_map = erp_third_parties(orders, snap.erp_order_socid, tp)

    # Orders the ERP bills to an internal company are intercompany sales, not sales to the
    # customer. Customers whose orders are *all* intercompany are excluded as a whole further
    # down; for the others, drop just those orders so they do not inflate the amounts.
    partial = {cid for cid, e in erp_map.items() if e.any_intercompany and not e.all_intercompany}
    interco_ids = intercompany_order_ids(snap.erp_order_socid, tp)
    drop = orders["ORDER_ID"].isin(interco_ids) & orders["CUSTOMER_ID"].isin(partial)
    interco_lines = orders[drop]
    interco_excluded = (
        interco_lines["ITEM_ORDERED_AMOUNT_HT_EUR"]
        .where(~_is_true(interco_lines["IS_NOT_REAL_ITEM"]), 0.0)
        .groupby(interco_lines["CUSTOMER_ID"])
        .sum()
    )
    interco_orders_n = interco_lines.groupby("CUSTOMER_ID")["ORDER_ID"].nunique()
    orders = orders[~drop]

    orders = add_product_lines(orders, snap.product_catalog, snap.product_tags)
    metrics = order_metrics(orders, snapshot_date)
    metrics = metrics.join(invoice_metrics(snap.invoices)).join(contract_metrics(snap.contracts))

    sup = snap.supplier_orders
    sup = sup[~_is_true(sup["IS_DRAFT_ORDER"])]
    supplier_keys = set(sup["SUPPLIER_NAME"].map(core_key).dropna())
    supplier_tp_ids = set(sup["THIRD_PARTY_ID"].dropna().astype(str))

    rows, issues, name_rows = [], [], []
    for cid, m in metrics.iterrows():
        name = m["customer_name"]
        entities = set(m["entity_names"].split(";")) if m["entity_names"] else set()
        name_res = matcher.match(name, entities)
        name_rows.append(
            {"customer_id": cid, "status": name_res.status, "rule": name_res.rule, "tie_break": name_res.tie_break}
        )
        erp = erp_map.get(cid)
        if erp is not None:
            res = MatchResult(
                MATCH_ERP, "erp_socid", erp.ids[0], list(erp.ids), list(erp.ids), erp.all_intercompany,
                "largest_amount" if len(erp.ids) > 1 else None,
            )
            name_vs_erp = _name_vs_erp(name_res, erp.ids[0], tp)
        else:
            res, name_vs_erp = name_res, None
        evidence_ids = list(dict.fromkeys(name_res.candidate_ids + res.candidate_ids))
        cand_rows = tp.loc[evidence_ids] if evidence_ids else tp.iloc[0:0]
        chosen_rows = tp.loc[res.chosen_ids] if res.chosen_ids else tp.iloc[0:0]
        tp_row = tp.loc[res.third_party_id] if res.third_party_id else None

        def pick(col, tp_row=tp_row, chosen_rows=chosen_rows):
            if tp_row is not None:
                v = tp_row[col]
                return None if pd.isna(v) else v
            return _agree(chosen_rows, col) if len(chosen_rows) else None

        country = pick("COUNTRY_CODE") or country_iso(m["order_country_raw"])
        order_iso = country_iso(m["order_country_raw"])

        evidence = []
        if bool(cand_rows["IS_SUPPLIER"].any()):
            evidence.append("third_party.IS_SUPPLIER")
        if supplier_tp_ids & set(evidence_ids):
            evidence.append("supplier_orders.THIRD_PARTY_ID")
        if core_key(name) in supplier_keys:
            evidence.append("supplier_orders.SUPPLIER_NAME")

        kw = integrator_keywords(name)
        hw = m["hardware_share"] if pd.notna(m["hardware_share"]) else 0.0
        reasons = []
        if kw:
            reasons.append("name:" + ",".join(kw))
        if evidence and hw >= 0.5:
            reasons.append("also_supplier+hardware")

        notes = name_notes(name)
        if reasons:
            notes.append("疑似集成商/同行")
        if evidence:
            notes.append("也是供应商")
        if not m["amount_ht_eur"]:
            notes.append("有效订单金额为0")
        if tp_row is not None and not tp_row["IS_CLIENT"]:
            notes.append("档案IS_CLIENT=false")
        tp_country = pick("COUNTRY_CODE")
        if tp_country and order_iso and tp_country != order_iso:
            notes.append(f"档案国家{tp_country}≠订单国家{order_iso}")
        if pd.notna(m.get("n_invoices_flagged_intercompany")) and m["n_invoices_flagged_intercompany"] > 0:
            notes.append("发票含内部公司标记")
        history_truncated = bool(entities) and entities <= LATE_HISTORY_ENTITIES
        if history_truncated:
            notes.append("订单历史可能不全(仅Page Up/Ubi Smart/Ubi Impact)")
        if res.status == MATCH_NORMALIZED:
            notes.append(f"规范化匹配({res.rule})")
        if erp is not None and len(erp.ids) > 1:
            notes.append(f"订单分属{len(erp.ids)}个第三方")
        if cid in interco_excluded.index:
            notes.append("已扣除开给内部公司的订单")
        if name_vs_erp == "different":
            notes.append("名称匹配与ERP不一致")
        if res.status == MATCH_AMBIGUOUS:
            notes.append(f"一对多({len(res.chosen_ids)})")

        # The order mart's CUSTOMER_NAME is sometimes a merged label ("S Transport",
        # "TCS - GROUPE STERNE"); when the ERP says which third party was billed, search by
        # that registry name instead and keep the order-name version alongside.
        order_lname = lookup_name(name)
        lname, lname_source = order_lname, "customer_name" if order_lname else None
        if res.status == MATCH_ERP and tp_row is not None:
            tp_lname = lookup_name(tp_row["THIRD_PARTY_NAME"])
            if tp_lname:
                lname, lname_source = tp_lname, "third_party_name"
        # Order name and billed registry name share no significant word: they may be
        # different companies (reseller, brand vs legal name, group vs subsidiary), so the
        # web app should search both lookup_name and order_lookup_name.
        lname_conflict = lname_source == "third_party_name" and names_unrelated(order_lname, lname)
        if lname_conflict:
            notes.append("订单名与档案名不同(两个都搜)")
        town = pick("TOWN")
        siren, siret = pick("SIREN"), pick("SIRET")
        reg_id = (
            tp_row["company_id"] if tp_row is not None else _agree(chosen_rows, "company_id")
        )
        rows.append(
            {
                "customer_id": cid,
                "customer_name": name,
                "lookup_name": lname,
                "lookup_name_source": lname_source,
                "order_lookup_name": order_lname,
                "lookup_name_conflict": lname_conflict,
                "lookup_query": " ".join(x for x in (lname, town, country) if x),
                "entity_names": m["entity_names"],
                "history_truncated": history_truncated,
                "country_code": country,
                "order_country_raw": m["order_country_raw"],
                "town": town,
                "zip_code": pick("ZIP_CODE"),
                "siren": siren,
                "siret": siret,
                "tax_number": pick("TAX_NUMBER"),
                "company_reg_id": reg_id if isinstance(reg_id, str) else None,
                "third_party_id": res.third_party_id,
                "third_party_ids": _join(res.chosen_ids),
                "third_party_name": pick("THIRD_PARTY_NAME"),
                "match_status": res.status,
                "match_rule": res.rule,
                "tie_break": res.tie_break,
                "erp_third_parties": _join(
                    f"{i}:{a:.2f}" + ("(interco)" if tp.at[i, "IS_INTERCOMPANY"] else "")
                    for i, a in zip(erp.ids, erp.amounts)
                )
                if erp
                else "",
                "intercompany_excluded_ht_eur": float(interco_excluded.get(cid, 0.0)),
                "erp_orders_verified": erp.n_orders_verified if erp else 0,
                "name_match_status": name_res.status,
                "name_match_third_party_id": name_res.third_party_id
                if name_res.third_party_id
                else (_join(name_res.chosen_ids) or None),
                "name_vs_erp": name_vs_erp,
                "tp_is_client": bool(tp_row["IS_CLIENT"]) if tp_row is not None else None,
                "is_also_supplier": bool(evidence),
                "supplier_evidence": _join(evidence),
                "is_intercompany": res.is_intercompany,
                "suspect_integrator": bool(reasons),
                "suspect_integrator_reason": _join(reasons),
                "candidate_third_parties": _join(matcher.hints(name))
                if res.status == MATCH_UNMATCHED
                else "",
                "notes": _join(notes),
            }
        )

        base = {"customer_id": cid, "customer_name": name, "amount_ht_eur": m["amount_ht_eur"]}
        if res.status == MATCH_AMBIGUOUS:
            ids = chosen_rows["company_id"].dropna().unique()
            same_id = len(ids) == 1 and chosen_rows["company_id"].notna().all()
            issues.append(
                base
                | {
                    "issue_type": "ambiguous_match",
                    "third_party_ids": _join(res.chosen_ids),
                    "detail": ("[候选注册号一致，档案重复录入] " if same_id else "")
                    + "; ".join(
                        f"{r.THIRD_PARTY_ID}:{r.THIRD_PARTY_NAME} [entity={r.entity_name}, "
                        f"client={r.IS_CLIENT}, siren={r.SIREN}, town={r.TOWN}]"
                        for r in chosen_rows.itertuples()
                    ),
                }
            )
            if len(ids) > 1:
                issues.append(
                    base
                    | {
                        "issue_type": "siren_conflict_candidates",
                        "third_party_ids": _join(res.chosen_ids),
                        "detail": "同名档案的公司注册号不同: " + ", ".join(ids),
                    }
                )
        if erp is not None and len(erp.ids) > 1:
            issues.append(
                base
                | {
                    "issue_type": "erp_multiple_third_parties",
                    "third_party_ids": _join(erp.ids),
                    "detail": f"订单开在 {len(erp.ids)} 个第三方上，主名单取金额最大的非内部公司: "
                    + "; ".join(
                        f"{i}:{tp.at[i, 'THIRD_PARTY_NAME']} ({a:,.2f}€"
                        + (", 内部公司" if tp.at[i, "IS_INTERCOMPANY"] else "")
                        + ")"
                        for i, a in zip(erp.ids, erp.amounts)
                    ),
                }
            )
        if erp is not None and erp.any_intercompany and not erp.all_intercompany:
            issues.append(
                base
                | {
                    "issue_type": "erp_includes_intercompany",
                    "third_party_ids": _join(i for i in erp.ids if tp.at[i, "IS_INTERCOMPANY"]),
                    "detail": f"{int(interco_orders_n.get(cid, 0))} 张订单开给了内部公司，"
                    f"已从金额中扣除 {interco_excluded.get(cid, 0.0):,.2f}€；客户保留在主名单",
                }
            )
        if name_vs_erp == "different":
            issues.append(
                base
                | {
                    "issue_type": "name_match_differs_from_erp",
                    "third_party_ids": f"{name_res.third_party_id}->{erp.ids[0]}",
                    "detail": f"名称匹配到 {name_res.third_party_id}:{tp.at[name_res.third_party_id, 'THIRD_PARTY_NAME']}，"
                    f"ERP 订单实际开在 {erp.ids[0]}:{tp.at[erp.ids[0], 'THIRD_PARTY_NAME']}；采用 ERP",
                }
            )
        if res.is_intercompany:
            issues.append(
                base
                | {
                    "issue_type": "intercompany_customer",
                    "third_party_ids": _join(res.candidate_ids),
                    "detail": "订单客户对上内部公司(IS_INTERCOMPANY)，已从主名单排除",
                }
            )
        if not res.is_intercompany and "发票含内部公司标记" in notes:
            issues.append(
                base
                | {
                    "issue_type": "invoice_intercompany_flag",
                    "third_party_ids": _join(res.chosen_ids),
                    "detail": f"{int(m['n_invoices_flagged_intercompany'])}/{int(m['n_invoices'])} "
                    "张有效发票 IS_INTERCOMPANY=true；名称未对上内部公司，保留在主名单",
                }
            )
        if not isinstance(name, str) or not name.strip():
            issues.append(
                base
                | {
                    "issue_type": "no_customer_name",
                    "third_party_ids": "",
                    "detail": "订单上 CUSTOMER_NAME 为空，无法按名称匹配" + ("；已由 ERP socid 补上" if erp is not None else ""),
                }
            )
        if tp_row is not None and not tp_row["IS_CLIENT"]:
            issues.append(
                base
                | {
                    "issue_type": "matched_registry_not_client",
                    "third_party_ids": res.third_party_id,
                    "detail": "唯一匹配的档案 IS_CLIENT=false",
                }
            )

    cust = pd.DataFrame(rows).set_index("customer_id", drop=False)
    metric_cols = [c for c in COMPANY_COLUMNS if c in metrics.columns and c not in cust.columns]
    cust = cust.join(metrics[metric_cols])
    cust["n_contracts"] = cust["n_contracts"].fillna(0).astype(int)
    cust["has_contract"] = cust["n_contracts"] > 0
    cust["n_invoices"] = cust["n_invoices"].fillna(0).astype(int)
    cust["invoice_amount_ht_eur"] = cust["invoice_amount_ht_eur"].fillna(0.0)
    cust["order_minus_invoice_ht_eur"] = cust["amount_ht_eur"] - cust["invoice_amount_ht_eur"]
    cust = attach_web_hints(cust, snap.erp_thirdparties, snap.third_parties)
    cust = cust[COMPANY_COLUMNS].sort_values("amount_ht_eur", ascending=False, kind="stable")
    cust = cust.reset_index(drop=True)

    issues += registry_siren_issues(cust, tp)
    issues_df = pd.DataFrame(
        issues, columns=["issue_type", "customer_id", "customer_name", "amount_ht_eur", "third_party_ids", "detail"]
    ).sort_values(["issue_type", "amount_ht_eur"], ascending=[True, False], kind="stable")

    companies = cust[~cust["is_intercompany"]].reset_index(drop=True)
    main_lines = orders[orders["CUSTOMER_ID"].isin(set(companies["customer_id"]))]

    return BuildResult(
        companies=companies,
        all_customers=cust,
        duplicates=find_duplicates(companies),
        issues=issues_df.reset_index(drop=True),
        orders_by_category=summarise_by_category(main_lines),
        orders_by_entity=summarise_by_entity(main_lines),
        category_cooccurrence=category_cooccurrence(main_lines),
        main_lines=main_lines,
        intercompany_lines=interco_lines,
        name_matches=pd.DataFrame(name_rows, columns=["customer_id", "status", "rule", "tie_break"]),
    )


def registry_siren_issues(cust: pd.DataFrame, tp: pd.DataFrame) -> list[dict]:
    """SIREN checks after name matching: one registration id should be one company."""
    out = []
    matched = cust[cust["company_reg_id"].notna() & ~cust["is_intercompany"]]
    for reg_id, grp in matched.groupby("company_reg_id"):
        cores = {core_key(n) for n in grp["customer_name"]}
        if len(grp) > 1 and len(cores) > 1:
            for r in grp.itertuples():
                out.append(
                    {
                        "issue_type": "siren_shared_by_different_names",
                        "customer_id": r.customer_id,
                        "customer_name": r.customer_name,
                        "amount_ht_eur": r.amount_ht_eur,
                        "third_party_ids": r.third_party_ids,
                        "detail": f"注册号 {reg_id} 对应多个不同名称的下单客户: "
                        + " | ".join(sorted(str(n) for n in grp["customer_name"])),
                    }
                )
    # The matched registry row shares its id with registry rows of a different name.
    by_id = tp.dropna(subset=["company_id"]).groupby("company_id")["k_core"].agg(lambda s: set(s.dropna()))
    for r in matched.itertuples():
        if not isinstance(r.third_party_id, str):
            continue  # ambiguous: covered by siren_conflict_candidates
        others = by_id.get(r.company_reg_id, set()) - {tp.at[r.third_party_id, "k_core"]}
        if others:
            out.append(
                {
                    "issue_type": "siren_registry_conflict",
                    "customer_id": r.customer_id,
                    "customer_name": r.customer_name,
                    "amount_ht_eur": r.amount_ht_eur,
                    "third_party_ids": r.third_party_id,
                    "detail": f"档案中注册号 {r.company_reg_id} 还对应: " + " | ".join(sorted(others)[:5]),
                }
            )
    return out


def find_duplicates(companies: pd.DataFrame) -> pd.DataFrame:
    df = companies.assign(core=companies["customer_name"].map(core_key))
    cols = [
        "customer_id", "customer_name", "entity_names", "country_code", "town",
        "company_reg_id", "third_party_id", "match_status", "amount_ht_eur", "n_orders",
        "first_order_date", "last_order_date",
    ]
    parts = []
    for gtype, key in (
        ("same_normalized_name", "core"),
        ("same_company_reg_id", "company_reg_id"),
        ("same_third_party_id", "third_party_id"),
    ):
        sub = df[df[key].notna()]
        dup = sub[sub.duplicated(key, keep=False)]
        if len(dup):
            parts.append(dup.assign(group_type=gtype, group_key=dup[key])[["group_type", "group_key"] + cols])
    if not parts:
        return pd.DataFrame(columns=["group_type", "group_key", "group_size", "group_amount_ht_eur"] + cols)
    out = pd.concat(parts, ignore_index=True)
    grp = out.groupby(["group_type", "group_key"])
    out.insert(2, "group_size", grp["customer_id"].transform("size"))
    out.insert(3, "group_amount_ht_eur", grp["amount_ht_eur"].transform("sum"))
    return out.sort_values(
        ["group_type", "group_amount_ht_eur", "group_key", "amount_ht_eur"],
        ascending=[True, False, True, False],
        kind="stable",
    ).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Summary tables
# --------------------------------------------------------------------------------------


def _real_lines(lines: pd.DataFrame) -> pd.DataFrame:
    real = lines[~_is_true(lines["IS_NOT_REAL_ITEM"])].copy()
    # A few valid lines have no ORDER_DATE; keep them (year = <NA>) so totals reconcile.
    real["year"] = pd.to_datetime(real["ORDER_DATE"]).dt.year.astype("Int64")
    real["item_category"] = real["ITEM_CATEGORY"].fillna("NULL")
    return real


def summarise_by_category(lines: pd.DataFrame) -> pd.DataFrame:
    real = _real_lines(lines)
    out = (
        real.groupby(["item_category", "year"], dropna=False)
        .agg(
            n_customers=("CUSTOMER_ID", "nunique"),
            n_orders=("ORDER_ID", "nunique"),
            n_order_lines=("ORDER_ITEM_ID", "size"),
            amount_ht_eur=("ITEM_ORDERED_AMOUNT_HT_EUR", "sum"),
        )
        .reset_index()
    )
    return out.sort_values(["item_category", "year"]).reset_index(drop=True)


def summarise_by_entity(lines: pd.DataFrame) -> pd.DataFrame:
    real = _real_lines(lines)
    out = (
        real.groupby("ENTITY_NAME")
        .agg(
            n_customers=("CUSTOMER_ID", "nunique"),
            n_orders=("ORDER_ID", "nunique"),
            n_order_lines=("ORDER_ITEM_ID", "size"),
            amount_ht_eur=("ITEM_ORDERED_AMOUNT_HT_EUR", "sum"),
            first_order_date=("ORDER_DATE", "min"),
            last_order_date=("ORDER_DATE", "max"),
        )
        .reset_index()
        .rename(columns={"ENTITY_NAME": "entity_name"})
    )
    out["amount_share"] = out["amount_ht_eur"] / out["amount_ht_eur"].sum()
    return out.sort_values("amount_ht_eur", ascending=False).reset_index(drop=True)


def category_cooccurrence(lines: pd.DataFrame) -> pd.DataFrame:
    """Pairs of ITEM_CATEGORY bought by the same CUSTOMER_ID.

    A customer "bought" a category when its net amount in that category is > 0.
    Diagonal rows (category_a == category_b) give single-category counts; their
    `amount_ht_eur` is the category's total amount over all customers, so the diagonal
    sums to the main-list order total.
    """
    real = _real_lines(lines)
    real = real[~real["item_category"].isin(MISSING_CATEGORY)]
    per = real.groupby(["CUSTOMER_ID", "item_category"])["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    totals = real.groupby("item_category")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    bought = per[per > 0]
    cats_by_cust = bought.reset_index().groupby("CUSTOMER_ID")["item_category"].agg(lambda s: sorted(set(s)))
    n_cat = bought.reset_index().groupby("item_category")["CUSTOMER_ID"].nunique()

    rows = []
    for cat in sorted(totals.index):
        rows.append(
            {
                "category_a": cat,
                "category_b": cat,
                "n_customers_both": int(n_cat.get(cat, 0)),
                "n_customers_a": int(n_cat.get(cat, 0)),
                "n_customers_b": int(n_cat.get(cat, 0)),
                "share_of_a_also_b": 1.0 if n_cat.get(cat, 0) else None,
                "share_of_b_also_a": 1.0 if n_cat.get(cat, 0) else None,
                "amount_ht_eur": float(totals[cat]),
                "amount_a_by_both_ht_eur": None,
                "amount_b_by_both_ht_eur": None,
            }
        )
    pair_customers: dict[tuple[str, str], list[str]] = {}
    for cid, cats in cats_by_cust.items():
        for a, b in combinations(cats, 2):
            pair_customers.setdefault((a, b), []).append(cid)
    for (a, b), cids in sorted(pair_customers.items()):
        na, nb = int(n_cat[a]), int(n_cat[b])
        idx_a = pd.MultiIndex.from_product([cids, [a]])
        idx_b = pd.MultiIndex.from_product([cids, [b]])
        rows.append(
            {
                "category_a": a,
                "category_b": b,
                "n_customers_both": len(cids),
                "n_customers_a": na,
                "n_customers_b": nb,
                "share_of_a_also_b": len(cids) / na,
                "share_of_b_also_a": len(cids) / nb,
                "amount_ht_eur": None,
                "amount_a_by_both_ht_eur": float(per.loc[idx_a].sum()),
                "amount_b_by_both_ht_eur": float(per.loc[idx_b].sum()),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------


def write_outputs(result: BuildResult, out_dir: Path, readme: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    c = result.companies
    c.to_parquet(out_dir / "companies.parquet", index=False)
    csv = {"index": False, "encoding": "utf-8-sig"}
    c.to_csv(out_dir / "companies.csv", **csv)
    c[c["match_status"] == MATCH_UNMATCHED].to_csv(out_dir / "unmatched.csv", **csv)
    result.duplicates.to_csv(out_dir / "duplicates.csv", **csv)
    result.issues.to_csv(out_dir / "issues.csv", **csv)
    result.orders_by_category.to_csv(out_dir / "orders_by_category.csv", **csv)
    result.orders_by_entity.to_csv(out_dir / "orders_by_entity.csv", **csv)
    result.category_cooccurrence.to_csv(out_dir / "category_cooccurrence.csv", **csv)
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="snapshot folder name (YYYY-MM-DD)")
    parser.add_argument("--raw-root", type=Path, default=PROJECT_ROOT / "data" / "raw")
    parser.add_argument("--out-root", type=Path, default=PROJECT_ROOT / "data" / "processed")
    parser.add_argument(
        "--erp-socid", type=Path, default=None,
        help="erp_order_socid.csv from erp_socid.py (default: <out-root>/<snapshot>/erp_order_socid.csv if present)",
    )
    parser.add_argument(
        "--erp-thirdparties", type=Path, default=None,
        help="erp_thirdparties.csv from erp_thirdparties.py (default: <out-root>/<snapshot>/erp_thirdparties.csv if present)",
    )
    args = parser.parse_args(argv)

    from analyse_dolibarr_client.report import render_readme

    snapshot_date = date.fromisoformat(args.snapshot)
    erp_path = args.erp_socid or args.out_root / args.snapshot / "erp_order_socid.csv"
    web_path = args.erp_thirdparties or args.out_root / args.snapshot / "erp_thirdparties.csv"
    tags_path = args.out_root / args.snapshot / TAGS_NAME
    snap = load_snapshot(args.raw_root, args.snapshot, erp_path, web_path, tags_path)
    print(f"ERP socids: {'used ' + str(erp_path) if snap.erp_order_socid is not None else 'not found, name matching only'}")
    print(f"ERP web fields: {'used ' + str(web_path) if snap.erp_thirdparties is not None else 'not found, no web domains'}")
    print(f"ERP product tags: {'used ' + str(tags_path) if snap.product_tags is not None else 'not found, name rules only'}")
    result = build(snap, snapshot_date)
    out_dir = args.out_root / args.snapshot
    write_outputs(result, out_dir, render_readme(snap, result, snapshot_date))
    c = result.companies
    print(f"companies: {len(c)} rows -> {out_dir}")
    print(c["match_status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
