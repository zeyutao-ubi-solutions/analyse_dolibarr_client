"""Labels and units for the lookalike (ICP similarity) model.

Target, decided 2026-11-20: from a company's public LinkedIn profile alone, score how much
it looks like our end-user customers. Two models (decided the same day):

1. overall model (PU): positives vs unlabeled prospects -> ``fit_overall``;
2. allocation model (multi-label, customers only, ``in_allocation_set``): which business
   lines a customer-like company buys -> ``p_geoloc`` / ``p_rfid`` / ``p_ubi_cloud``.

Score of a line = fit_overall x p_line; ranking priority additionally x country_factor. Positives are end-user customers; Dolibarr prospects
that never ordered are *unlabeled* (PU learning), not negatives. Features must come from
LinkedIn only; everything here (orders, amounts) is label or bookkeeping, never a feature.

The unit is a company group as LinkedIn sees it: one web domain (or, without a domain, one
third party), so subsidiaries sharing a group page never land on both sides of a split.

Reads ``data/processed/<snap>/companies.parquet`` and ``erp_thirdparties.csv`` plus the raw
third-party mart; writes under ``data/processed/<snap>/labeling/``:

- ``customer_type_labels.csv``: the manual labeling sheet (one row per customer with
  orders). Re-running refreshes the context columns and adds new customers but never
  touches what annotators typed; the previous file is copied to ``history/`` first.
- ``lookalike_units.csv``: one row per unit with ``label`` = positive / unlabeled / excluded,
  ``country_bucket`` and ``sample_weight`` (country-balancing, see ``add_country_weights``),
  and ``country_factor`` for ranking: priority = model score (country-blind) x country_factor.
- ``country_factors.csv``: per country, historical win rate and a suggested factor relative to
  FR; ``manual_factor`` typed in by sales/management overrides it and survives re-runs.

Country is deliberately not a feature; see docs/labeling/feature_policy.md for the proxies
that must be left out as well.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analyse_dolibarr_client.companies import DEFAULT_SNAPSHOT, PROJECT_ROOT, _is_true, attach_web_hints
from analyse_dolibarr_client.names import lookup_name

CUSTOMER_TYPES = ("end_user", "integrator_reseller", "competitor", "intercompany", "not_a_company", "unsure")
CONFIDENCES = ("high", "medium", "low")
LABEL_COLUMNS = ["customer_type", "confidence", "evidence_url", "annotator", "labeled_at", "comment"]
CONTEXT_COLUMNS = [
    "customer_id", "priority", "review_reasons", "suggested_type", "lookup_name", "order_lookup_name",
    "third_party_name", "country_code", "town", "web_domain", "web_domain_matches_name", "amount_ht_eur",
    "n_orders", "first_order_date", "last_order_date", "top_item_category", "category_mix", "buyer_pattern",
    "product_lines", "suspect_integrator_reason", "supplier_evidence", "notes",
]
SHEET_NAME = "customer_type_labels.csv"
UNITS_NAME = "lookalike_units.csv"

# value_tier (for weighting and the later value model), on mature, untruncated units only.
CORE_FIRST_24M_EUR = 25_000
MATURE_MONTHS = 24


# ------------------------------------------------------------------------------ sheet


def review_priority(c: pd.DataFrame) -> pd.DataFrame:
    """P1: a signal that the customer may not be an end user; P2: large or odd domain; P3: rest."""
    reasons = pd.Series([[] for _ in range(len(c))], index=c.index)
    flags = {
        "suspect_integrator": c["suspect_integrator"].fillna(False).astype(bool),
        "also_supplier": c["is_also_supplier"].fillna(False).astype(bool),
        "order_name_differs": c["lookup_name_conflict"].fillna(False).astype(bool),
    }
    weak = {
        "domain_not_name": c["web_domain"].notna() & ~c["web_domain_matches_name"].fillna(False).astype(bool),
    }
    amount = c["amount_ht_eur"].sort_values(ascending=False)
    top90 = set(amount.index[(amount.cumsum() / amount.sum()).shift(fill_value=0) < 0.9])
    weak["top_90pct_amount"] = c.index.to_series().isin(top90)
    for name, mask in {**flags, **weak}.items():
        for i in c.index[mask]:
            reasons[i].append(name)
    p1 = pd.concat(flags, axis=1).any(axis=1)
    p2 = pd.concat(weak, axis=1).any(axis=1)
    return pd.DataFrame(
        {
            "priority": ["P1" if a else "P2" if b else "P3" for a, b in zip(p1, p2)],
            "review_reasons": [";".join(r) for r in reasons],
        },
        index=c.index,
    )


def suggested_type(c: pd.DataFrame) -> pd.Series:
    return pd.Series(
        ["integrator_reseller" if s else "end_user" for s in c["suspect_integrator"].fillna(False).astype(bool)],
        index=c.index,
    )


def build_sheet(companies: pd.DataFrame, existing: pd.DataFrame | None) -> pd.DataFrame:
    """Context columns from the current build; label columns carried over by customer_id."""
    c = companies[companies["amount_ht_eur"] > 0].copy()
    c = c.join(review_priority(c))
    c["suggested_type"] = suggested_type(c)
    for col in CONTEXT_COLUMNS:  # older builds may lack newer context columns
        if col not in c.columns:
            c[col] = None
    sheet = c[CONTEXT_COLUMNS].copy()
    for col in LABEL_COLUMNS:
        sheet[col] = None
    if existing is not None and len(existing):
        kept = existing.set_index("customer_id")[LABEL_COLUMNS]
        sheet = sheet.set_index("customer_id")
        common = sheet.index.intersection(kept.index)
        sheet.loc[common, LABEL_COLUMNS] = kept.loc[common, LABEL_COLUMNS]
        # Customers that disappeared from the build keep their labels at the bottom, so no work is lost.
        gone = kept.index.difference(sheet.index)
        labeled_gone = kept.loc[gone][kept.loc[gone, "customer_type"].notna()]
        if len(labeled_gone):
            extra = existing.set_index("customer_id").loc[labeled_gone.index].assign(priority="gone")
            sheet = pd.concat([sheet, extra[[col for col in sheet.columns if col in extra.columns]]])
        sheet = sheet.reset_index()
    order = {"P1": 0, "P2": 1, "P3": 2, "gone": 3}
    sheet["_o"] = sheet["priority"].map(order)
    sheet = sheet.sort_values(["_o", "amount_ht_eur"], ascending=[True, False], kind="stable").drop(columns="_o")
    return sheet.reset_index(drop=True)


def validate_labels(sheet: pd.DataFrame) -> list[str]:
    errors = []
    for _, r in sheet.iterrows():
        t, conf = r["customer_type"], r["confidence"]
        if isinstance(t, str) and t.strip() and t.strip() not in CUSTOMER_TYPES:
            errors.append(f"{r['customer_id']}: customer_type '{t}' not in {CUSTOMER_TYPES}")
        if isinstance(conf, str) and conf.strip() and conf.strip() not in CONFIDENCES:
            errors.append(f"{r['customer_id']}: confidence '{conf}' not in {CONFIDENCES}")
    return errors


def effective_types(sheet: pd.DataFrame) -> pd.DataFrame:
    """Manual label when given (and not 'unsure'), else the suggestion."""
    manual = sheet["customer_type"].where(sheet["customer_type"].astype("string").str.strip().isin(CUSTOMER_TYPES))
    manual = manual.where(manual != "unsure")
    return pd.DataFrame(
        {
            "customer_id": sheet["customer_id"],
            "effective_type": manual.fillna(sheet["suggested_type"]),
            "type_source": ["manual" if isinstance(m, str) else "auto" for m in manual],
            "priority": sheet["priority"],
        }
    )


# ------------------------------------------------------------------------------ units


def _unit_key(domain, tp_id, fallback) -> str:
    if isinstance(domain, str) and domain:
        return domain
    if isinstance(tp_id, str) and tp_id:
        return f"tp:{tp_id}"
    return f"cust:{fallback}"


def prospect_rows(tp: pd.DataFrame, web: pd.DataFrame | None) -> pd.DataFrame:
    """Prospects that never became clients, with a web domain derived like the customers'."""
    t = tp.copy()
    t["THIRD_PARTY_ID"] = t["THIRD_PARTY_ID"].astype(str)
    keep = _is_true(t["IS_PROSPECT"]) & ~_is_true(t["IS_CLIENT"]) & ~_is_true(t["IS_INTERCOMPANY"])
    supplier = _is_true(t["IS_SUPPLIER"])
    t = t[keep]
    names = t["THIRD_PARTY_NAME"].map(lookup_name)
    rows = pd.DataFrame(
        {
            "customer_id": "tp:" + t["THIRD_PARTY_ID"],
            "lookup_name": names,
            "order_lookup_name": names,
            "lookup_name_conflict": False,
            "country_code": t["COUNTRY_CODE"],
            "siren": t["SIREN"],
            "third_party_id": t["THIRD_PARTY_ID"],
            "third_party_ids": t["THIRD_PARTY_ID"],
            "third_party_name": t["THIRD_PARTY_NAME"],
            "is_supplier": supplier[keep].to_numpy(),
            "notes": "",
        }
    ).reset_index(drop=True)
    return attach_web_hints(rows, web, tp)


def value_tier(n_years_active, recurring, first24, months, truncated) -> str:
    if truncated:
        return "truncated"
    if pd.isna(months) or months < MATURE_MONTHS:
        return "immature"
    if first24 >= CORE_FIRST_24M_EUR or (n_years_active >= 2 and recurring > 0):
        return "core"
    return "standard"


def build_units(companies: pd.DataFrame, types: pd.DataFrame, prospects: pd.DataFrame) -> pd.DataFrame:
    c = companies.merge(types, on="customer_id", how="left")
    c["effective_type"] = c["effective_type"].fillna("excluded_zero_amount")
    c["unit_id"] = [
        _unit_key(d, t, cid) for d, t, cid in zip(c["web_domain"], c["third_party_id"], c["customer_id"])
    ]
    c["is_end_user"] = (c["effective_type"] == "end_user") & (c["amount_ht_eur"] > 0)
    siren_to_unit = {
        s: u for s, u in zip(c["siren"].astype("string").str.replace(" ", ""), c["unit_id"]) if isinstance(s, str) and len(s) == 9
    }

    rows = []
    for unit, g in c.groupby("unit_id", sort=False):
        g = g.sort_values("amount_ht_eur", ascending=False)
        ends = g[g["is_end_user"]]
        lead = (ends if len(ends) else g).iloc[0]
        label = "positive" if len(ends) else "excluded"
        reason = None if len(ends) else _join_sorted(g["effective_type"])
        src = set(g["type_source"].dropna())
        e = ends if len(ends) else g
        rows.append(
            {
                "unit_id": unit,
                "label": label,
                "exclusion_reason": reason,
                "lookup_name": lead["lookup_name"],
                "country_code": lead["country_code"],
                "web_domain": lead["web_domain"],
                "web_domain_matches_name": lead["web_domain_matches_name"],
                "n_customers": len(g),
                "n_end_user_customers": len(ends),
                "n_prospect_records": 0,
                "customer_ids": ";".join(g["customer_id"]),
                "third_party_ids": _join_sorted(g["third_party_ids"].str.split(";").explode()),
                "amount_ht_eur": float(e["amount_ht_eur"].sum()),
                "amount_first_24m_ht_eur": float(e["amount_first_24m_ht_eur"].sum()),
                "first_order_date": e["first_order_date"].min(),
                "value_tier": value_tier(
                    e["n_years_active"].max(),
                    e["amount_recurring_ht_eur"].sum(),
                    e["amount_first_24m_ht_eur"].sum(),
                    e["months_since_first_order"].max(),
                    bool(e["history_truncated"].all()),
                )
                if len(ends)
                else None,
                **unit_product_lines(e, bool(len(ends))),
                "type_source": "manual" if src == {"manual"} else "auto" if src <= {"auto"} else "mixed",
                "needs_review": bool(((g["priority"] == "P1") & (g["type_source"] != "manual")).any()),
            }
        )
    units = pd.DataFrame(rows)
    customer_units = set(units["unit_id"])

    p = prospects.copy()
    p["unit_id"] = [_unit_key(d, t, t) for d, t in zip(p["web_domain"], p["third_party_id"])]
    sirens = p["siren"].astype("string").str.replace(" ", "")
    p["unit_id"] = [siren_to_unit.get(s, u) if isinstance(s, str) else u for s, u in zip(sirens, p["unit_id"])]
    in_customer = p["unit_id"].isin(customer_units)
    counts = p[in_customer].groupby("unit_id").size()
    units["n_prospect_records"] = units["unit_id"].map(counts).fillna(0).astype(int)

    prow = []
    for unit, g in p[~in_customer].groupby("unit_id", sort=False):
        lead = g.iloc[0]
        supplier = bool(g["is_supplier"].all())
        prow.append(
            {
                "unit_id": unit,
                "label": "excluded" if supplier else "unlabeled",
                "exclusion_reason": "supplier" if supplier else None,
                "lookup_name": lead["lookup_name"],
                "country_code": lead["country_code"],
                "web_domain": lead["web_domain"],
                "web_domain_matches_name": lead["web_domain_matches_name"],
                "n_customers": 0,
                "n_end_user_customers": 0,
                "n_prospect_records": len(g),
                "customer_ids": None,
                "third_party_ids": _join_sorted(g["third_party_id"]),
                "type_source": None,
                "needs_review": False,
                "positive_geoloc": False,
                "positive_rfid": False,
                "positive_ubi_cloud": False,
            }
        )
    units = pd.concat([units, pd.DataFrame(prow)], ignore_index=True)
    units["has_domain"] = units["web_domain"].notna()
    # Split key: the unit itself (already a domain group). Use it for GroupKFold.
    units["split_group"] = units["unit_id"]
    # Allocation model: trained on customer units only, multi-label targets positive_geoloc /
    # positive_rfid / positive_ubi_cloud. Customers that bought none of the three lines stay
    # in the overall model only.
    line_cols = ["positive_geoloc", "positive_rfid", "positive_ubi_cloud"]
    units[line_cols] = units[line_cols].fillna(False).astype(bool)
    units["in_allocation_set"] = (units["label"] == "positive") & units[line_cols].any(axis=1)
    units["cohort_year"] = pd.to_datetime(units["first_order_date"]).dt.year.astype("Int64")
    return units


MIN_POSITIVES_PER_BUCKET = 10


def add_country_weights(units: pd.DataFrame, min_positives: int = MIN_POSITIVES_PER_BUCKET) -> pd.DataFrame:
    """Country is not a feature, so the unlabeled pool must not differ from positives by country.

    Otherwise the model learns country through proxies (domain TLD, text language, HQ city).
    Countries with fewer than ``min_positives`` positive units share an ``other`` bucket.
    Positives weigh 1; an unlabeled unit in bucket b weighs (pos share of b) / (unlabeled share of b),
    so the weighted unlabeled pool has the positives' country mix and keeps its total size.
    Excluded units weigh 0.
    """
    u = units.copy()
    country = u["country_code"].where(u["country_code"].notna() & (u["country_code"] != ""), "unknown")
    pos_counts = country[u["label"] == "positive"].value_counts()
    big = set(pos_counts[pos_counts >= min_positives].index) - {"unknown"}
    u["country_bucket"] = country.where(country.isin(big), "other")
    pos = u.loc[u["label"] == "positive", "country_bucket"].value_counts(normalize=True)
    unl = u.loc[u["label"] == "unlabeled", "country_bucket"].value_counts(normalize=True)
    ratio = (pos / unl).fillna(0.0)
    u["sample_weight"] = 0.0
    u.loc[u["label"] == "positive", "sample_weight"] = 1.0
    is_unl = u["label"] == "unlabeled"
    u.loc[is_unl, "sample_weight"] = u.loc[is_unl, "country_bucket"].map(ratio).fillna(0.0)
    return u


def effective_sample_size(weights: pd.Series) -> float:
    w = weights[weights > 0]
    return float(w.sum() ** 2 / (w**2).sum()) if len(w) else 0.0


def unit_product_lines(members: pd.DataFrame, positive: bool) -> dict:
    """Product-line summary of a unit's end-user members; per-line positives for the line models."""
    geo = float(members["amount_geoloc_ht_eur"].sum()) if "amount_geoloc_ht_eur" in members else 0.0
    rfid = float(members["amount_rfid_ht_eur"].sum()) if "amount_rfid_ht_eur" in members else 0.0
    cloud = float(members["amount_ubi_cloud_ht_eur"].sum()) if "amount_ubi_cloud_ht_eur" in members else 0.0
    srcs = set(members["geoloc_source"].dropna()) if "geoloc_source" in members else set()
    return {
        "product_lines": ";".join(ln for ln, v in (("geoloc", geo), ("rfid", rfid), ("ubi_cloud", cloud)) if v > 0),
        "amount_geoloc_ht_eur": geo,
        "amount_rfid_ht_eur": rfid,
        "amount_ubi_cloud_ht_eur": cloud,
        "geoloc_source": "tag" if "tag" in srcs else "name_rule" if srcs else None,
        "positive_geoloc": positive and geo > 0,
        "positive_rfid": positive and rfid > 0,
        "positive_ubi_cloud": positive and cloud > 0,
    }


def _join_sorted(values) -> str:
    return ";".join(sorted({str(v) for v in values if isinstance(v, str) and v}))


# ------------------------------------------------------------------------------ country factors

COUNTRY_FACTORS_NAME = "country_factors.csv"
REFERENCE_COUNTRY = "FR"
PRIOR_STRENGTH = 20  # pseudo-units pulling small countries toward the non-reference pooled rate
FACTOR_MANUAL_COLUMNS = ["manual_factor", "manual_note", "set_by", "set_at"]


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / den
    return max(0.0, centre - half), min(1.0, centre + half)


def country_factors(units: pd.DataFrame, existing: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per country: historical win rate of units, a smoothed rate and a suggested factor vs FR.

    ``historical_rate`` = positive / (positive + unlabeled) units. It mixes real difficulty
    (distance, installation) with sales effort (never-worked imported lists), so it is only a
    starting point: ``manual_factor`` (kept across re-runs) overrides ``suggested_factor``.
    Small countries are shrunk toward the pooled rate of all non-FR countries with
    ``PRIOR_STRENGTH`` pseudo-units, so 1 customer out of 3 records does not look like 33%.
    """
    u = units[units["label"].isin(["positive", "unlabeled"])].copy()
    u["country"] = u["country_code"].where(u["country_code"].notna() & (u["country_code"] != ""), "unknown")
    g = u.groupby("country")["label"].agg(
        n_positive_units=lambda s: int((s == "positive").sum()), n_unlabeled_units=lambda s: int((s == "unlabeled").sum())
    )
    g["n_units"] = g["n_positive_units"] + g["n_unlabeled_units"]
    g["historical_rate"] = g["n_positive_units"] / g["n_units"]
    ci = [wilson_interval(int(k), int(n)) for k, n in zip(g["n_positive_units"], g["n_units"])]
    g["rate_ci95_low"] = [c[0] for c in ci]
    g["rate_ci95_high"] = [c[1] for c in ci]
    others = g.drop(index=REFERENCE_COUNTRY, errors="ignore")
    prior = others["n_positive_units"].sum() / others["n_units"].sum() if others["n_units"].sum() else 0.0
    g["smoothed_rate"] = (g["n_positive_units"] + PRIOR_STRENGTH * prior) / (g["n_units"] + PRIOR_STRENGTH)
    g.loc[g.index == REFERENCE_COUNTRY, "smoothed_rate"] = g["historical_rate"]
    ref = g["smoothed_rate"].get(REFERENCE_COUNTRY)
    g["suggested_factor"] = (g["smoothed_rate"] / ref).round(3) if ref else None
    # Customers always carry a country (from the order), so "unknown" holds only prospects and
    # its 0% rate is an artefact, not a signal: no suggestion, it must be set by hand.
    if "unknown" in g.index:
        g.loc["unknown", ["historical_rate", "rate_ci95_low", "rate_ci95_high", "smoothed_rate", "suggested_factor"]] = None
    g["auto_note"] = [
        "country missing (only prospects can lack one), rate is meaningless; fill in the country first or set the factor by hand"
        if c == "unknown"
        else "reference country" if c == REFERENCE_COUNTRY
        else "fewer than 5 positives, the suggested value comes mostly from the prior; set it by hand" if k < 5
        else ""
        for c, k in zip(g.index, g["n_positive_units"])
    ]
    for col in FACTOR_MANUAL_COLUMNS:
        g[col] = None
    if existing is not None and len(existing):
        kept = existing.set_index("country_code")[FACTOR_MANUAL_COLUMNS]
        common = g.index.intersection(kept.index)
        g.loc[common, FACTOR_MANUAL_COLUMNS] = kept.loc[common, FACTOR_MANUAL_COLUMNS].to_numpy()
    manual = pd.to_numeric(g["manual_factor"], errors="coerce")
    g["factor"] = manual.fillna(g["suggested_factor"])
    g["factor_source"] = [
        "manual" if pd.notna(m) else "suggested" if pd.notna(sf) else "missing"
        for m, sf in zip(manual, g["suggested_factor"])
    ]
    g = g.reset_index().rename(columns={"country": "country_code"})
    cols = [
        "country_code", "n_positive_units", "n_unlabeled_units", "n_units", "historical_rate", "rate_ci95_low",
        "rate_ci95_high", "smoothed_rate", "suggested_factor", "manual_factor", "manual_note", "set_by", "set_at",
        "factor", "factor_source", "auto_note",
    ]
    rate_cols = ["historical_rate", "rate_ci95_low", "rate_ci95_high", "smoothed_rate"]
    g[rate_cols] = g[rate_cols].astype(float).round(4)
    return g[cols].sort_values("n_units", ascending=False, kind="stable").reset_index(drop=True)


def validate_factors(df: pd.DataFrame) -> list[str]:
    errors = []
    for _, r in df.iterrows():
        v = r.get("manual_factor")
        if isinstance(v, str) and v.strip():
            try:
                f = float(v)
            except ValueError:
                errors.append(f"{r['country_code']}: manual_factor '{v}' is not a number")
                continue
            if f < 0:
                errors.append(f"{r['country_code']}: manual_factor {f} is negative")
    return errors


def attach_country_factor(units: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    u = units.copy()
    country = u["country_code"].where(u["country_code"].notna() & (u["country_code"] != ""), "unknown")
    u["country_factor"] = country.map(factors.set_index("country_code")["factor"])
    return u


def _backup(path: Path, lab: Path) -> None:
    hist = lab / "history"
    hist.mkdir(exist_ok=True)
    shutil.copy2(path, hist / f"{path.stem}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv")


# ------------------------------------------------------------------------------ run


def run(snapshot: str, raw_root: Path, out_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = out_root / snapshot
    lab = out / "labeling"
    lab.mkdir(parents=True, exist_ok=True)
    companies = pd.read_parquet(out / "companies.parquet")
    tp = pd.read_parquet(raw_root / snapshot / "mart_third_parties.parquet")
    web_path = out / "erp_thirdparties.csv"
    web = None
    if web_path.exists():
        web = pd.read_csv(web_path, dtype=str)
        web = web[web["tp_name_matches"].eq("True")]

    sheet_path = lab / SHEET_NAME
    existing = None
    if sheet_path.exists():
        existing = pd.read_csv(sheet_path, dtype=str, encoding="utf-8-sig")
        errors = validate_labels(existing)
        if errors:
            raise SystemExit("invalid labels in " + str(sheet_path) + ":\n  " + "\n  ".join(errors[:20]))
        _backup(sheet_path, lab)
    sheet = build_sheet(companies, existing)
    sheet.to_csv(sheet_path, index=False, encoding="utf-8-sig")

    units = add_country_weights(build_units(companies, effective_types(sheet), prospect_rows(tp, web)))

    factors_path = lab / COUNTRY_FACTORS_NAME
    existing_f = None
    if factors_path.exists():
        existing_f = pd.read_csv(factors_path, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
        errors = validate_factors(existing_f)
        if errors:
            raise SystemExit("invalid manual factors in " + str(factors_path) + ":\n  " + "\n  ".join(errors))
        _backup(factors_path, lab)
    factors = country_factors(units, existing_f)
    factors.to_csv(factors_path, index=False, encoding="utf-8-sig")

    units = attach_country_factor(units, factors)
    units.to_csv(lab / UNITS_NAME, index=False, encoding="utf-8-sig")
    return sheet, units


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument("--raw-root", type=Path, default=PROJECT_ROOT / "data" / "raw")
    p.add_argument("--out-root", type=Path, default=PROJECT_ROOT / "data" / "processed")
    a = p.parse_args(argv)
    sheet, units = run(a.snapshot, a.raw_root, a.out_root)
    labeled = sheet["customer_type"].notna().sum()
    print(f"sheet: {len(sheet)} customers, {int(labeled)} labeled; priority {sheet['priority'].value_counts().to_dict()}")
    print(f"units: {units['label'].value_counts().to_dict()}")
    pos = units[units["label"] == "positive"]
    print(f"positive value_tier: {pos['value_tier'].value_counts().to_dict()}")
    print(f"positive per line: geoloc {int(pos['positive_geoloc'].sum())} "
          f"(tag {int((pos['positive_geoloc'] & pos['geoloc_source'].eq('tag')).sum())}), "
          f"rfid {int(pos['positive_rfid'].sum())}, ubi_cloud {int(pos['positive_ubi_cloud'].sum())}, geoloc+rfid {int((pos['positive_geoloc'] & pos['positive_rfid']).sum())}, "
          f"none of the three {int((~pos['positive_geoloc'] & ~pos['positive_rfid'] & ~pos['positive_ubi_cloud']).sum())}")
    alloc = units[units["in_allocation_set"]]
    print(f"allocation set: {len(alloc)} customer units; "
          f"geoloc {int(alloc['positive_geoloc'].sum())}, rfid {int(alloc['positive_rfid'].sum())}, "
          f"ubi_cloud {int(alloc['positive_ubi_cloud'].sum())}")
    unl = units[units["label"] == "unlabeled"]
    w = unl.groupby("country_bucket")["sample_weight"].agg(["size", "first"]).round(3)
    print("unlabeled weight by country bucket (n, weight):", w.to_dict("index"))
    print(f"unlabeled effective sample size: {effective_sample_size(unl['sample_weight']):.0f} of {len(unl)}")
    f = pd.read_csv(a.out_root / a.snapshot / "labeling" / COUNTRY_FACTORS_NAME, encoding="utf-8-sig", keep_default_na=False)
    print(f.head(12)[["country_code", "n_positive_units", "n_units", "historical_rate", "suggested_factor", "factor", "factor_source"]].to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
