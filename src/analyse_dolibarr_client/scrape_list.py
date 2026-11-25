"""LinkedIn scrape list for the web app: which company pages to fetch for the lookalike model.

Reads ``labeling/lookalike_units.csv`` (plus companies and the third-party mart for search
names and towns) and writes ``labeling/linkedin_scrape_list.csv``. The contract for what the
web app sends back is docs/labeling/linkedin_scrape_contract.md.

Who is on the list:

- every ``positive`` unit (all customers we learn from);
- ``unlabeled`` units sampled per country bucket so that, *after* sampling, each bucket holds
  about the same number of unlabeled units per positive unit as France (the reference, where
  every unlabeled unit is kept). The country-balancing weights then come out roughly equal,
  so ~2,400 pages give the information of the full 8,648 weighted pool. The draw is stratified
  and deterministic (hash of unit_id), so re-running keeps the same units.
- an ``oversample`` margin of extra unlabeled units per bucket (``batch=reserve``) to replace
  pages that cannot be found.

The list deliberately carries **no label**: the scraper and any LLM matching step must not
know which companies are customers. ``unit_id`` is the join key back to the labels.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

import pandas as pd

from analyse_dolibarr_client.companies import DEFAULT_SNAPSHOT, PROJECT_ROOT
from analyse_dolibarr_client.lookalike import UNITS_NAME
from analyse_dolibarr_client.names import lookup_name

LIST_NAME = "linkedin_scrape_list.csv"
REFERENCE_BUCKET = "FR"
DEFAULT_OVERSAMPLE = 0.3
COLUMNS = [
    "unit_id", "batch", "search_name", "alt_search_names", "web_domain", "country_code", "town", "registry_id",
    "has_domain",
]


def _stable_rank(unit_id: str) -> str:
    return hashlib.sha1(unit_id.encode()).hexdigest()


def sample_unlabeled(units: pd.DataFrame, oversample: float = DEFAULT_OVERSAMPLE) -> pd.DataFrame:
    """Unlabeled units to scrape, with ``batch`` = main / reserve, stratified by country bucket."""
    pos = units[units["label"] == "positive"]["country_bucket"].value_counts()
    unl = units[units["label"] == "unlabeled"].copy()
    ref_ratio = len(unl[unl["country_bucket"] == REFERENCE_BUCKET]) / pos.get(REFERENCE_BUCKET, 1)
    unl["_rank"] = unl["unit_id"].map(_stable_rank)
    picked = []
    for bucket, g in unl.groupby("country_bucket"):
        g = g.sort_values("_rank")
        if bucket == REFERENCE_BUCKET:
            main, reserve = len(g), 0
        else:
            main = min(len(g), math.ceil(ref_ratio * pos.get(bucket, 0)))
            reserve = min(len(g) - main, math.ceil(main * oversample))
        picked.append(g.iloc[:main].assign(batch="main"))
        picked.append(g.iloc[main : main + reserve].assign(batch="reserve"))
    return pd.concat(picked).drop(columns="_rank")


def search_names(units: pd.DataFrame, companies: pd.DataFrame, tp: pd.DataFrame) -> pd.DataFrame:
    """Main and alternative search names, town and SIREN per unit (no amounts, no labels)."""
    comp = companies.set_index("customer_id")
    t = tp.assign(THIRD_PARTY_ID=tp["THIRD_PARTY_ID"].astype(str)).set_index("THIRD_PARTY_ID")
    rows = []
    for _, u in units.iterrows():
        names, towns, sirens = [], [], []
        for cid in str(u["customer_ids"]).split(";") if isinstance(u["customer_ids"], str) else []:
            if cid in comp.index:
                r = comp.loc[cid]
                names += [r["lookup_name"], r["order_lookup_name"]]
                towns.append(r["town"])
                sirens.append(r["siren"])
        for tid in str(u["third_party_ids"]).split(";") if isinstance(u["third_party_ids"], str) else []:
            if tid in t.index:
                r = t.loc[tid]
                names.append(lookup_name(r["THIRD_PARTY_NAME"]))
                towns.append(r["TOWN"])
                sirens.append(r["SIREN"])
        clean = [n for n in dict.fromkeys(n for n in names if isinstance(n, str) and n.strip())]
        main = u["lookup_name"] if isinstance(u["lookup_name"], str) and u["lookup_name"] else (clean[0] if clean else None)
        rows.append(
            {
                "unit_id": u["unit_id"],
                "search_name": main,
                "alt_search_names": ";".join(n for n in clean if n != main)[:300] or None,
                "town": next((x for x in towns if isinstance(x, str) and x.strip()), None),
                # As typed in the registry: SIREN, SIRET or a foreign tax id (e.g. Spanish CIF).
                "registry_id": next((str(x).replace(" ", "") for x in sirens if isinstance(x, str) and x.strip()), None),
            }
        )
    return pd.DataFrame(rows)


def build_list(units: pd.DataFrame, companies: pd.DataFrame, tp: pd.DataFrame, oversample: float = DEFAULT_OVERSAMPLE) -> pd.DataFrame:
    pos = units[units["label"] == "positive"].assign(batch="main")
    chosen = pd.concat([pos, sample_unlabeled(units, oversample)], ignore_index=True)
    out = chosen[["unit_id", "batch", "web_domain", "country_code", "has_domain"]].merge(
        search_names(chosen, companies, tp), on="unit_id", how="left"
    )
    # Shuffle deterministically so customers and prospects are interleaved (no label by position).
    out["_rank"] = out["unit_id"].map(_stable_rank)
    out = out.sort_values(["batch", "_rank"]).drop(columns="_rank")
    return out[COLUMNS].reset_index(drop=True)


def run(snapshot: str, raw_root: Path, out_root: Path, oversample: float) -> pd.DataFrame:
    out = out_root / snapshot
    units = pd.read_csv(out / "labeling" / UNITS_NAME, dtype={"unit_id": str, "customer_ids": str, "third_party_ids": str},
                        encoding="utf-8-sig")
    companies = pd.read_parquet(out / "companies.parquet")
    tp = pd.read_parquet(raw_root / snapshot / "mart_third_parties.parquet")
    lst = build_list(units, companies, tp, oversample)
    lst.to_csv(out / "labeling" / LIST_NAME, index=False, encoding="utf-8-sig")
    return lst


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument("--raw-root", type=Path, default=PROJECT_ROOT / "data" / "raw")
    p.add_argument("--out-root", type=Path, default=PROJECT_ROOT / "data" / "processed")
    p.add_argument("--oversample", type=float, default=DEFAULT_OVERSAMPLE, help="reserve share for non-FR buckets")
    a = p.parse_args(argv)
    lst = run(a.snapshot, a.raw_root, a.out_root, a.oversample)
    print(f"scrape list: {len(lst)} units; batch {lst['batch'].value_counts().to_dict()}; "
          f"with domain {int(lst['has_domain'].sum())}")
    print(lst.groupby(["country_code"]).size().sort_values(ascending=False).head(8).to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
