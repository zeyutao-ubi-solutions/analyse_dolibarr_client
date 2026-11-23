"""Scrape LinkedIn company pages for lookalike units via Apify ``harvestapi/linkedin-company``.

Reads ``labeling/linkedin_scrape_list.csv`` (no labels) and writes raw actor datasets plus
one row per unit under ``labeling/``. Matching follows docs/labeling/linkedin_scrape_contract.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv

from analyse_dolibarr_client.companies import DEFAULT_SNAPSHOT, PROJECT_ROOT
from analyse_dolibarr_client.erp_thirdparties import FREE_MAIL_DOMAINS
from analyse_dolibarr_client.names import basic_key, core_key, country_iso, names_unrelated
from analyse_dolibarr_client.scrape_list import LIST_NAME

ACTOR_ID = "harvestapi/linkedin-company"
DEFAULT_APIFY_ENV = Path.home() / "web_app_refactoring" / "backEnd" / ".env"
DEFAULT_BATCH_SIZE = 25
DEFAULT_WAIT_SECS = 600
DEFAULT_TIMEOUT_SECS = 720
DEFAULT_RETRIES = 2
PILOT_N = 20
CANDIDATE_CAP = 5
TERMINAL = frozenset({"matched", "not_found", "ambiguous", "error"})
RESULT_COLUMNS = [
    "unit_id", "match_status", "match_method", "linkedin_url", "linkedin_public_id",
    "candidates", "scraped_at", "description", "tagline", "specialties", "industry",
    "employee_count", "employee_count_range", "company_type", "founded_year", "followers",
    "locations_count", "has_parent_or_affiliated", "parent_linkedin_url", "name", "website",
    "hq_country", "hq_city", "group_page", "thin_page", "query_used",
]
REVIEW_COLUMNS = [
    "unit_id", "search_name", "web_domain", "country_code", "town",
    "candidate_url", "candidate_name", "candidate_website", "candidate_hq_country", "candidate_hq_city",
]
_MULTI_SUFFIX = frozenset({
    "co.uk", "org.uk", "ac.uk", "gov.uk", "net.uk", "me.uk",
    "com.au", "net.au", "org.au", "co.jp", "co.nz", "co.za", "co.in", "co.kr",
    "com.br", "com.mx", "com.ar", "com.tr", "com.cn", "com.tw", "com.hk",
    "co.id", "com.sg", "com.my",
    # Government namespaces: each ministry / agency under them is its own organisation.
    "gouv.fr", "gob.es", "gov.it", "gov.pl", "gov.pt", "gov.br", "gov.tr", "gob.mx",
    "gc.ca", "gv.at", "admin.ch", "gov.au", "gov.in",
})
_REJECT_NAME = re.compile(
    r"\b(SYNDICAT|CGT|CFDT|CSE|ALUMNI|CAMPUS|FANPAGE|FAN[ -]?PAGE|"
    r"COMITE SOCIAL|COMITE D[' ]ENTREPRISE|WORKS COUNCIL)\b",
    re.I,
)
PROGRESS_COLUMNS = [
    "unit_id", "status", "attempts", "last_error", "match_method", "search_used",
    "tried_searches", "run_ids", "updated_at",
]
RUNS_COLUMNS = [
    "run_id", "dataset_id", "unit_ids", "status", "started_at", "finished_at",
    "item_count", "usage_usd", "usage_raw", "input_mode", "n_input",
]
PARENT_KEYS = (
    "parentCompany", "parent", "affiliatedCompanies",
    "affiliatedCompaniesByEmployees", "affiliatedCompaniesByJobs",
    "affiliatedPages",
)
STUB_KEYS = frozenset({"linkedinUrl", "universalName", "name", "originalQuery", "id", "query", "search"})

log = logging.getLogger("analyse_dolibarr_client.linkedin_scrape")


class ApifyRunError(RuntimeError):
    """Actor run did not succeed or returned no dataset."""


class ScrapePaused(RuntimeError):
    """Stop the scrape: high error rate, rate limit/quota, or too many ambiguous rows."""


class _RedactFormatter(logging.Formatter):
    def __init__(self, fmt: str, token: str = "") -> None:
        super().__init__(fmt)
        self._token = token

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self._token)


def redact(text: object, token: str) -> str:
    s = "" if text is None else str(text)
    if token:
        s = s.replace(token, "***")
    return re.sub(r"(?i)Bearer\s+\S+", "Bearer ***", s)


def load_apify_token(env_file: Path | None = None) -> str:
    load_dotenv(env_file or DEFAULT_APIFY_ENV, override=True)
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        raise ValueError("APIFY_TOKEN missing in environment or env file")
    return token


def normalize_domain(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().lower()
    if raw.startswith("mailto:"):
        return None
    if "://" not in raw:
        raw = "https://" + raw
    host = urlparse(raw).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return host or None


def as_country_iso(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    mapped = country_iso(raw)
    if mapped:
        return mapped
    s = raw.strip().upper()
    return s if len(s) == 2 and s.isalpha() else None


def registrable_domain(value: object) -> str | None:
    """eTLD+1: ``fr.scc.com`` → ``scc.com``, ``www.acme.co.uk`` → ``acme.co.uk``."""
    host = normalize_domain(value)
    if not host:
        return None
    parts = host.split(".")
    if len(parts) < 2:
        return host
    last2 = ".".join(parts[-2:])
    if last2 in _MULTI_SUFFIX and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last2


def company_domain(web_domain: object) -> str | None:
    """Registrable domain usable as company evidence; mailbox providers (inwind.it…) say nothing."""
    host = registrable_domain(web_domain)
    return None if host in FREE_MAIL_DOMAINS else host


def domain_brand(web_domain: object) -> str | None:
    host = company_domain(web_domain)
    if not host:
        return None
    return host.split(".")[0] or None


def website_host(item: dict[str, Any]) -> str | None:
    return normalize_domain(item.get("website") or item.get("websiteUrl"))


def website_registrable(item: dict[str, Any]) -> str | None:
    return registrable_domain(item.get("website") or item.get("websiteUrl"))


def linkedin_url(item: dict[str, Any]) -> str | None:
    u = item.get("linkedinUrl")
    if isinstance(u, str) and u.strip():
        return u.strip().rstrip("/")
    return None


def linkedin_pid(item: dict[str, Any]) -> str | None:
    uni = item.get("universalName")
    if isinstance(uni, str) and uni.strip():
        return uni.strip().lower()
    url = linkedin_url(item)
    return url.rsplit("/", 1)[-1].lower() if url else None


def original_query(item: dict[str, Any]) -> str:
    oq = item.get("originalQuery")
    if isinstance(oq, dict):
        for key in ("search", "company", "url", "query"):
            raw = oq.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    for key in ("query", "search"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def item_hq_country(item: dict[str, Any]) -> str | None:
    loc = _hq_location(item)
    if not loc:
        return None
    parsed = loc.get("parsed") if isinstance(loc.get("parsed"), dict) else {}
    for raw in (parsed.get("countryCode"), loc.get("country"), parsed.get("country"), parsed.get("countryFull")):
        iso = as_country_iso(raw)
        if iso:
            return iso
    return None


def item_hq_city(item: dict[str, Any]) -> str | None:
    loc = _hq_location(item)
    if not loc:
        return None
    parsed = loc.get("parsed") if isinstance(loc.get("parsed"), dict) else {}
    for raw in (parsed.get("city"), loc.get("city")):
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _hq_location(item: dict[str, Any]) -> dict[str, Any] | None:
    locs = item.get("locations")
    if not isinstance(locs, list):
        return None
    for loc in locs:
        if isinstance(loc, dict) and loc.get("headquarter"):
            return loc
    return locs[0] if locs and isinstance(locs[0], dict) else None


def unit_compare_names(unit: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for raw in [unit.get("search_name"), *(unit.get("alt_search_names") or [])]:
        if isinstance(raw, str) and raw.strip() and raw.strip() not in names:
            names.append(raw.strip())
    brand = domain_brand(unit.get("web_domain"))
    if brand and brand not in names:
        names.append(brand)
    return names


def name_exact(unit: dict[str, Any], item: dict[str, Any]) -> bool:
    page = core_key(item.get("name"))
    if not page:
        return False
    return any(core_key(n) == page for n in unit_compare_names(unit) if core_key(n))


def name_partial(unit: dict[str, Any], item: dict[str, Any]) -> bool:
    if name_exact(unit, item):
        return False
    page = item.get("name")
    if not core_key(page):
        return False
    return any(not names_unrelated(n, page) for n in unit_compare_names(unit) if core_key(n))


def country_ok(unit_country: object, item: dict[str, Any]) -> bool:
    left, right = as_country_iso(unit_country), item_hq_country(item)
    return bool(left and right and left == right)


def town_ok(unit_town: object, item: dict[str, Any]) -> bool:
    if not isinstance(unit_town, str) or not unit_town.strip():
        return False
    city = item_hq_city(item)
    if not city:
        return False
    a, b = basic_key(unit_town), basic_key(city)
    return bool(a and b and (a == b or a in b or b in a))


def is_rejected_page(item: dict[str, Any]) -> bool:
    raw = " ".join(x for x in (item.get("name"), item.get("tagline")) if isinstance(x, str))
    if raw and _REJECT_NAME.search(raw):
        return True
    keyed = basic_key(raw) or ""
    if keyed and _REJECT_NAME.search(keyed):
        return True
    tokens = set((core_key(item.get("name")) or "").split())
    if "FO" in tokens:
        return True
    page_type = str(item.get("pageType") or "").lower()
    return page_type in {"school"}


def thin_page(item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    words = len(item["description"].split()) if isinstance(item.get("description"), str) else 0
    if words < 20:
        return True
    emp = item.get("employeeCount")
    no_site = website_registrable(item) is None
    return isinstance(emp, (int, float)) and emp <= 1 and no_site


def group_page_flag(unit: dict[str, Any], item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    names = [n for n in [unit.get("search_name"), *(unit.get("alt_search_names") or [])] if isinstance(n, str) and n.strip()]
    if not names:
        return False
    return all(names_unrelated(n, item.get("name")) for n in names)


def unique_by_url(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = linkedin_url(item) or f"anon:{id(item)}"
        seen.setdefault(key, item)
    return list(seen.values())


def needs_detail_fetch(item: dict[str, Any] | None) -> bool:
    if not item or not linkedin_url(item):
        return False
    return not any(k not in STUB_KEYS for k in item)


def parent_fields(item: dict[str, Any]) -> tuple[bool | None, str | None]:
    url = None
    flag = False
    parent = item.get("parentCompany") or item.get("parent")
    if isinstance(parent, dict):
        raw = parent.get("linkedinUrl") or parent.get("url")
        if isinstance(raw, str) and raw.strip():
            url = raw.strip()
        flag = True
    elif isinstance(parent, str) and parent.strip():
        url, flag = parent.strip(), True
    for key in PARENT_KEYS:
        val = item.get(key)
        if val:
            flag = True
            if url is None and isinstance(val, list) and val and isinstance(val[0], dict):
                raw = val[0].get("linkedinUrl") or val[0].get("url")
                if isinstance(raw, str) and raw.strip():
                    url = raw.strip()
    return (True if flag else False if item else None), url


def _join_list(value: object, *, from_dicts: tuple[str, ...] = ("title", "name")) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if not isinstance(value, list):
        return None
    parts: list[str] = []
    for entry in value:
        if isinstance(entry, dict):
            for k in from_dicts:
                raw = entry.get(k)
                if isinstance(raw, str) and raw.strip():
                    parts.append(raw.strip())
                    break
        elif entry is not None and str(entry).strip():
            parts.append(str(entry).strip())
    return ";".join(parts) or None


def employee_range(item: dict[str, Any]) -> str | None:
    rng = item.get("employeeCountRange")
    if not isinstance(rng, dict):
        return None
    start, end = rng.get("start"), rng.get("end")
    if start is not None and end is not None:
        return f"{start}-{end}"
    if start is not None:
        return f"{start}+"
    return None


def founded_year(item: dict[str, Any]) -> int | None:
    fo = item.get("foundedOn")
    if isinstance(fo, dict) and isinstance(fo.get("year"), int):
        return fo["year"]
    year = item.get("founded")
    return year if isinstance(year, int) else None


@dataclass
class MatchDecision:
    match_status: str
    match_method: str | None = None
    item: dict[str, Any] | None = None
    candidates: list[str] = field(default_factory=list)
    candidate_items: list[dict[str, Any]] = field(default_factory=list)
    needs_more: bool = False
    group_page: bool | None = None
    thin_page: bool | None = None
    query_used: str | None = None


def _urls(items: list[dict[str, Any]]) -> list[str]:
    return [u for u in (linkedin_url(i) for i in items) if u]


def _matched(unit: dict[str, Any], method: str, item: dict[str, Any]) -> MatchDecision:
    return MatchDecision(
        "matched", method, item,
        group_page=group_page_flag(unit, item) if method == "domain" else False,
        thin_page=thin_page(item),
        query_used=original_query(item) or None,
    )


def _ambiguous(items: list[dict[str, Any]], method: str | None = None) -> MatchDecision:
    uniq = unique_by_url(items)
    urls = _urls(uniq)
    return MatchDecision("ambiguous", method, None, urls, uniq)


def classify(unit: dict[str, Any], items: list[dict[str, Any]], *, has_remaining: bool) -> MatchDecision:
    """Decide match_status for one unit from collected actor items. Never reads labels."""
    pool = [i for i in unique_by_url(items) if not is_rejected_page(i)]
    unit_domain = company_domain(unit.get("web_domain"))
    unit_country = as_country_iso(unit.get("country_code"))
    town = unit.get("town") if isinstance(unit.get("town"), str) and unit["town"].strip() else None

    domain_hits: list[dict[str, Any]] = []
    name_country_hits: list[dict[str, Any]] = []
    ambiguous_hits: list[dict[str, Any]] = []

    for item in pool:
        page_domain = website_registrable(item)
        exact, partial = name_exact(unit, item), name_partial(unit, item)
        hq = item_hq_country(item)
        same_country = bool(unit_country and hq and unit_country == hq)
        city_ok = (not town) or town_ok(town, item)

        if unit_domain and page_domain and page_domain == unit_domain:
            domain_hits.append(item)
            continue
        if unit_domain and page_domain and page_domain != unit_domain:
            if exact and (same_country or not unit_country):
                ambiguous_hits.append(item)
            elif exact and unit_country and hq and hq != unit_country:
                ambiguous_hits.append(item)
            elif partial:
                ambiguous_hits.append(item)
            continue

        if not unit_country:
            if exact or partial:
                ambiguous_hits.append(item)
            continue
        if hq and hq != unit_country:
            if exact:
                ambiguous_hits.append(item)
            continue
        if exact and same_country and city_ok:
            name_country_hits.append(item)
            continue
        if exact or partial:
            ambiguous_hits.append(item)

    domain_urls = list(dict.fromkeys(_urls(domain_hits)))
    if len(domain_urls) == 1:
        item = next(i for i in domain_hits if linkedin_url(i) == domain_urls[0])
        return _matched(unit, "domain", item)
    if len(domain_urls) > 1:
        return _ambiguous(domain_hits, "domain")

    nc_urls = list(dict.fromkeys(_urls(name_country_hits)))
    if len(nc_urls) == 1:
        item = next(i for i in name_country_hits if linkedin_url(i) == nc_urls[0])
        return _matched(unit, "name_country", item)
    if len(nc_urls) > 1:
        return _ambiguous(name_country_hits, "name_country")

    if ambiguous_hits and (not has_remaining or any(name_exact(unit, i) for i in ambiguous_hits)):
        return _ambiguous(ambiguous_hits)
    if has_remaining:
        return MatchDecision("pending", needs_more=True)
    if ambiguous_hits:
        return _ambiguous(ambiguous_hits)
    return MatchDecision("not_found")


def search_sequence(unit: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    brand = domain_brand(unit.get("web_domain"))
    for raw in [brand, unit.get("search_name"), *(unit.get("alt_search_names") or [])]:
        if not isinstance(raw, str) or not raw.strip():
            continue
        key = raw.strip()
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        names.append(key)
    return names


def next_search(unit: dict[str, Any], tried: set[str]) -> str | None:
    tried_l = {s.lower() for s in tried}
    for name in search_sequence(unit):
        if name.lower() not in tried_l:
            return name
    return None


def parse_alts(raw: object) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [p.strip() for p in raw.split(";") if p.strip()]


def has_domain_mask(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def select_pilot(df: pd.DataFrame, n: int = PILOT_N, exclude: set[str] | None = None) -> pd.DataFrame:
    """~half with domain, ~half without; several non-FR in each half. Deterministic."""
    main = df[df["batch"].astype(str) == "main"].copy()
    if exclude:
        main = main[~main["unit_id"].astype(str).isin(exclude)]
    main["_rank"] = main["unit_id"].map(lambda x: hashlib.sha1(str(x).encode()).hexdigest())
    n_domain = n // 2
    n_nodomain = n - n_domain
    with_d = main[has_domain_mask(main["has_domain"])].sort_values("_rank")
    without = main[~has_domain_mask(main["has_domain"])].sort_values("_rank")

    def take_mix(pool: pd.DataFrame, k: int, min_non_fr: int) -> pd.DataFrame:
        non_fr = pool[pool["country_code"].fillna("") != "FR"]
        fr = pool[pool["country_code"].fillna("") == "FR"]
        n_non = min(len(non_fr), max(min_non_fr, k // 3), k)
        picked = pd.concat([non_fr.head(n_non), fr.head(k - n_non)])
        return picked.head(k)

    out = pd.concat([take_mix(with_d, n_domain, 4), take_mix(without, n_nodomain, 3)])
    return out.drop(columns="_rank").reset_index(drop=True)


def select_pilot2(df: pd.DataFrame, n_first: int = PILOT_N, n_extra: int = 30) -> pd.DataFrame:
    first = select_pilot(df, n_first)
    extra = select_pilot(df, n_extra, exclude=set(first["unit_id"].astype(str)))
    return pd.concat([first, extra], ignore_index=True)


def units_from_frame(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rec in df.to_dict(orient="records"):
        uid = str(rec["unit_id"])
        domain = rec.get("web_domain")
        hd = rec.get("has_domain")
        if isinstance(hd, str):
            hd = hd.strip().lower() in {"true", "1", "yes"}
        elif not isinstance(hd, bool):
            hd = bool(domain)
        out[uid] = {
            "unit_id": uid,
            "search_name": rec.get("search_name") if isinstance(rec.get("search_name"), str) else None,
            "alt_search_names": parse_alts(rec.get("alt_search_names")),
            "web_domain": domain if isinstance(domain, str) and domain.strip() else None,
            "country_code": rec.get("country_code") if isinstance(rec.get("country_code"), str) else None,
            "town": rec.get("town") if isinstance(rec.get("town"), str) else None,
            "has_domain": bool(hd),
        }
    return out


def row_from_decision(unit_id: str, decision: MatchDecision, scraped_at: str) -> dict[str, Any]:
    item = decision.item if decision.match_status == "matched" and decision.item else {}
    locs = item.get("locations") if item else None
    has_parent, parent_url = parent_fields(item) if item else (None, None)
    empty = decision.match_status != "matched"
    return {
        "unit_id": unit_id,
        "match_status": decision.match_status,
        "match_method": decision.match_method,
        "linkedin_url": None if empty else linkedin_url(item),
        "linkedin_public_id": None if empty else linkedin_pid(item),
        "candidates": ";".join(decision.candidates) if decision.candidates else None,
        "scraped_at": scraped_at,
        "description": None if empty else (item.get("description") if isinstance(item.get("description"), str) else None),
        "tagline": None if empty else (item.get("tagline") if isinstance(item.get("tagline"), str) else None),
        "specialties": None if empty else _join_list(item.get("specialities") or item.get("speciality")),
        "industry": None if empty else _join_list(item.get("industries") or item.get("industry")),
        "employee_count": None if empty else item.get("employeeCount"),
        "employee_count_range": None if empty else employee_range(item),
        "company_type": None if empty else item.get("companyType"),
        "founded_year": None if empty else founded_year(item),
        "followers": None if empty else item.get("followerCount"),
        "locations_count": None if empty else (len(locs) if isinstance(locs, list) else None),
        "has_parent_or_affiliated": None if empty else has_parent,
        "parent_linkedin_url": None if empty else parent_url,
        "name": None if empty else item.get("name"),
        "website": None if empty else (item.get("website") or item.get("websiteUrl")),
        "hq_country": None if empty else item_hq_country(item),
        "hq_city": None if empty else item_hq_city(item),
        "group_page": None if empty else decision.group_page,
        "thin_page": None if empty else decision.thin_page,
        "query_used": None if empty else (decision.query_used or original_query(item) or None),
    }


def review_rows_for(unit: dict[str, Any], decision: MatchDecision) -> list[dict[str, Any]]:
    if decision.match_status != "ambiguous":
        return []
    items = decision.candidate_items or []
    if not items and decision.candidates:
        items = [{"linkedinUrl": u} for u in decision.candidates]
    rows = []
    for item in items:
        rows.append({
            "unit_id": unit.get("unit_id"),
            "search_name": unit.get("search_name"),
            "web_domain": unit.get("web_domain"),
            "country_code": unit.get("country_code"),
            "town": unit.get("town"),
            "candidate_url": linkedin_url(item),
            "candidate_name": item.get("name"),
            "candidate_website": item.get("website") or item.get("websiteUrl"),
            "candidate_hq_country": item_hq_country(item),
            "candidate_hq_city": item_hq_city(item),
        })
    return rows


def write_review_queue(path: Path, rows: list[dict[str, Any]], resolved_ids: set[str] | frozenset[str] = frozenset()) -> None:
    """Upsert candidate rows; drop stale rows of every unit re-decided this run (``resolved_ids``)."""
    new = pd.DataFrame(rows, columns=REVIEW_COLUMNS) if rows else pd.DataFrame(columns=REVIEW_COLUMNS)
    if path.exists() and path.stat().st_size:
        old = pd.read_csv(path, dtype={"unit_id": str}, encoding="utf-8-sig")
        drop = set(resolved_ids) | set(new["unit_id"].astype(str))
        old = old[~old["unit_id"].astype(str).isin(drop)]
        out = pd.concat([old, new], ignore_index=True) if not new.empty else old
    else:
        out = new
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def setup_log(path: Path, token: str) -> None:
    log.handlers.clear()
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = _RedactFormatter("%(asctime)s %(levelname)s %(message)s", token=token)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)


def run_record(run: Any) -> dict[str, Any]:
    """Normalize apify-client v3 Run objects and test doubles to a dict."""
    if run is None:
        raise ApifyRunError("actor returned no run record")
    if isinstance(run, dict):
        rec = dict(run)
    elif hasattr(run, "model_dump"):
        dump = run.model_dump()
        rec = {
            "id": dump.get("id"),
            "defaultDatasetId": dump.get("default_dataset_id"),
            "status": dump.get("status"),
            "usageTotalUsd": dump.get("usage_total_usd"),
            "chargedEventCounts": dump.get("charged_event_counts"),
            "event_usage": dump.get("event_usage"),
            "stats": dump.get("stats"),
            "usage": dump.get("usage"),
        }
    else:
        raise ApifyRunError(f"unexpected run type {type(run).__name__}")
    status = rec.get("status")
    rec["status"] = str(getattr(status, "value", status) or "").upper()
    if rec["status"].endswith("SUCCEEDED"):
        rec["status"] = "SUCCEEDED"
    return rec


def usage_from_run(run: dict[str, Any]) -> tuple[float | None, str]:
    platform = run.get("usageTotalUsd")
    ppe = 0.0
    event_usage = run.get("event_usage") or run.get("eventUsage")
    if isinstance(event_usage, dict):
        for val in event_usage.values():
            if isinstance(val, dict):
                amount = val.get("event_total_usd") or val.get("eventTotalUsd")
                if isinstance(amount, (int, float)):
                    ppe += float(amount)
    total = None
    if isinstance(platform, (int, float)) and float(platform) > 0:
        total = float(platform)
    elif ppe:
        total = ppe
    elif isinstance(platform, (int, float)):
        total = float(platform)
    payload = {
        k: run.get(k)
        for k in ("usageTotalUsd", "usageUsd", "usage", "chargedEventCounts", "event_usage", "stats")
        if run.get(k) is not None
    }
    return total, json.dumps(payload, default=str)


def run_actor(
    client: Any,
    run_input: dict[str, Any],
    *,
    wait_secs: int,
    timeout_secs: int,
    retries: int,
    token: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = client.actor(ACTOR_ID).call(
                run_input=run_input,
                wait_duration=timedelta(seconds=wait_secs),
                run_timeout=timedelta(seconds=timeout_secs),
                logger=None,
            )
            run = run_record(raw)
            if run.get("status") != "SUCCEEDED":
                raise ApifyRunError(f"status={run.get('status')} run_id={run.get('id')}")
            dataset_id = str(run.get("defaultDatasetId") or "").strip()
            if not dataset_id:
                raise ApifyRunError("missing defaultDatasetId")
            items = [it for it in client.dataset(dataset_id).iterate_items() if isinstance(it, dict)]
            return items, run
        except TypeError as exc:
            raise ApifyRunError(redact(exc, token)) from exc
        except Exception as exc:  # noqa: BLE001 — retry then record
            last_err = ApifyRunError(redact(exc, token))
            log.warning("actor attempt %s/%s failed: %s", attempt + 1, retries + 1, last_err)
            if _quota_error(str(last_err)):
                raise last_err
            if attempt < retries:
                time.sleep(min(5 * (attempt + 1), 20))
    raise last_err or ApifyRunError("actor failed")


def partition_items(
    items: list[dict[str, Any]], queries: list[str],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_q: dict[str, list[dict[str, Any]]] = {q: [] for q in queries}
    lookup = {q.strip().lower(): q for q in queries if q.strip()}
    leftover: list[dict[str, Any]] = []
    any_query = False
    for item in items:
        oq = original_query(item)
        if oq:
            any_query = True
            key = lookup.get(oq.strip().lower())
            if key:
                if len(by_q[key]) < CANDIDATE_CAP:
                    by_q[key].append(item)
            else:
                leftover.append(item)
        else:
            leftover.append(item)
    unique = list(dict.fromkeys(queries))
    if not any_query and len(items) == len(unique):
        for q, item in zip(unique, items):
            by_q[q].append(item)
        leftover = []
    return by_q, leftover


def load_progress(path: Path, unit_ids: list[str]) -> dict[str, dict[str, Any]]:
    now = _now()
    rows = {uid: {
        "unit_id": uid, "status": "pending", "attempts": 0, "last_error": None,
        "match_method": None, "search_used": None, "tried_searches": "",
        "run_ids": "", "updated_at": now,
    } for uid in unit_ids}
    if path.exists():
        existing = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        for rec in existing.to_dict(orient="records"):
            uid = str(rec.get("unit_id") or "")
            if uid in rows:
                rec["attempts"] = _as_int(rec.get("attempts"))
                if rec.get("status") == "in_progress":
                    rec["status"] = "pending"
                rows[uid].update({k: rec.get(k, rows[uid][k]) for k in PROGRESS_COLUMNS})
                rows[uid]["attempts"] = _as_int(rec.get("attempts"))
    return rows


def save_progress(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    existing: dict[str, dict[str, Any]] = {}
    if path.exists() and path.stat().st_size:
        for rec in pd.read_csv(path, dtype=str, encoding="utf-8-sig").to_dict(orient="records"):
            uid = str(rec.get("unit_id") or "")
            if uid:
                existing[uid] = rec
    existing.update(rows)
    df = pd.DataFrame([existing[k] for k in existing], columns=PROGRESS_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_partial(path: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid, item = rec.get("unit_id"), rec.get("item")
            if isinstance(uid, str) and isinstance(item, dict):
                out.setdefault(uid, []).append(item)
    return out


def append_partial(path: Path, unit_id: str, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps({"unit_id": unit_id, "item": item}, ensure_ascii=False, default=str) + "\n")


def write_raw(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")


def append_run(path: Path, row: dict[str, Any]) -> None:
    df = pd.DataFrame([row], columns=RUNS_COLUMNS)
    header = not path.exists()
    df.to_csv(path, mode="a", header=header, index=False, encoding="utf-8-sig")


def upsert_results(path: Path, rows: list[dict[str, Any]]) -> None:
    new = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    if path.exists() and path.stat().st_size:
        old = pd.read_csv(path, dtype={"unit_id": str}, encoding="utf-8-sig")
        old = old[~old["unit_id"].astype(str).isin(new["unit_id"])]
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_int(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return int(number)


def _is_done(row: dict[str, Any], *, refetch: bool) -> bool:
    if refetch:
        return False
    return row.get("status") in TERMINAL


def _quota_error(err: str) -> bool:
    low = err.lower()
    return any(s in low for s in (
        "rate limit", "ratelimit", "quota", "limit exceeded", "429",
        "out of credit", "payment required", "monthly usage", "free plan",
        "usage cycle", "upgrade at",
    ))


def merge_raw_into_partial(
    raw_dir: Path,
    units: dict[str, dict[str, Any]],
    partial: dict[str, list[dict[str, Any]]],
) -> None:
    query_to_uids: dict[str, list[str]] = {}
    for uid, unit in units.items():
        for query in search_sequence(unit):
            query_to_uids.setdefault(query.lower(), []).append(uid)
    seen = {uid: {linkedin_url(i) for i in items if linkedin_url(i)} for uid, items in partial.items()}
    if not raw_dir.exists():
        return
    for path in raw_dir.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            oq = original_query(item)
            if not oq:
                continue
            url = linkedin_url(item)
            for uid in query_to_uids.get(oq.strip().lower(), []):
                if url and url in seen.get(uid, set()):
                    continue
                partial.setdefault(uid, []).append(item)
                if url:
                    seen.setdefault(uid, set()).add(url)


def scrape(
    units_df: pd.DataFrame,
    out_dir: Path,
    *,
    client: Any | None = None,
    env_file: Path | None = None,
    refetch: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    wait_secs: int = DEFAULT_WAIT_SECS,
    timeout_secs: int = DEFAULT_TIMEOUT_SECS,
    retries: int = DEFAULT_RETRIES,
    results_path: Path | None = None,
    review_path: Path | None = None,
    token: str | None = None,
    check_stops: bool = True,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw").mkdir(exist_ok=True)
    if token is None:
        token = load_apify_token(env_file) if client is None else os.environ.get("APIFY_TOKEN", "").strip()
    setup_log(out_dir / "scrape.log", token)
    if client is None:
        from apify_client import ApifyClient
        client = ApifyClient(token)

    units = units_from_frame(units_df)
    unit_ids = list(units)
    progress = load_progress(out_dir / "progress.csv", unit_ids)
    partial: dict[str, list[dict[str, Any]]]
    if refetch:
        blank = {
            "status": "pending", "attempts": 0, "last_error": None, "match_method": None,
            "search_used": None, "tried_searches": "", "run_ids": "", "updated_at": _now(),
        }
        for uid in unit_ids:
            progress[uid] = {"unit_id": uid, **blank}
        partial = {uid: [] for uid in unit_ids}
        partial_path = out_dir / "partial.jsonl"
        if partial_path.exists():
            partial_path.unlink()
    else:
        partial = load_partial(out_dir / "partial.jsonl")
        merge_raw_into_partial(out_dir / "raw", units, partial)
        for uid in unit_ids:
            progress[uid]["status"] = "pending"

    results_path = results_path or (
        out_dir.parent / f"linkedin_companies_{datetime.now(timezone.utc).date().isoformat()}.csv"
    )
    review_path = review_path or (out_dir.parent / "linkedin_review_queue.csv")
    pause_path = out_dir / "pause_reason.txt"
    if pause_path.exists():
        pause_path.unlink()
    tried = {
        uid: {s for s in str(progress[uid].get("tried_searches") or "").split(";") if s}
        for uid in unit_ids
    }
    result_rows: dict[str, dict[str, Any]] = {}
    review_acc: list[dict[str, Any]] = []
    decided_ids: set[str] = set()

    def pending_ids() -> list[str]:
        return [uid for uid in unit_ids if not _is_done(progress[uid], refetch=False)]

    def persist_outputs() -> None:
        save_progress(out_dir / "progress.csv", progress)
        if result_rows:
            upsert_results(results_path, list(result_rows.values()))
        if review_acc or decided_ids:
            write_review_queue(review_path, review_acc, decided_ids)

    def maybe_pause(reason: str) -> None:
        if not check_stops:
            return
        pause_path.write_text(reason + "\n", encoding="utf-8")
        log.warning("paused: %s", reason)
        persist_outputs()
        raise ScrapePaused(reason)

    def check_ratios(batch_uids: list[str] | None = None) -> None:
        if not check_stops:
            return
        if batch_uids:
            n_err = sum(1 for uid in batch_uids if progress[uid].get("status") == "error")
            if batch_uids and n_err / len(batch_uids) > 0.20:
                maybe_pause(f"error rate {n_err}/{len(batch_uids)} > 20% in one batch")

    def finalize(uid: str, decision: MatchDecision, run_id: str | None, search_used: str | None) -> None:
        scraped_at = _now()
        if decision.match_status == "matched" and not decision.query_used:
            decision.query_used = search_used
        row = row_from_decision(uid, decision, scraped_at)
        result_rows[uid] = row
        decided_ids.add(uid)
        progress[uid].update({
            "status": decision.match_status,
            "match_method": decision.match_method,
            "search_used": search_used or decision.query_used,
            "last_error": None,
            "updated_at": scraped_at,
        })
        if run_id:
            prev = [x for x in str(progress[uid].get("run_ids") or "").split(";") if x]
            if run_id not in prev:
                prev.append(run_id)
            progress[uid]["run_ids"] = ";".join(prev)
        if decision.match_status == "ambiguous":
            review_acc.extend(review_rows_for(units[uid], decision))
        log.info(
            "unit %s -> %s method=%s url=%s",
            uid, decision.match_status, decision.match_method, row.get("linkedin_url"),
        )

    def mark_error(uids: list[str], err: str, run_id: str | None = None) -> None:
        for uid in uids:
            progress[uid]["status"] = "error"
            progress[uid]["attempts"] = int(progress[uid].get("attempts") or 0) + 1
            progress[uid]["last_error"] = redact(err, token)
            progress[uid]["updated_at"] = _now()
            if run_id:
                prev = [x for x in str(progress[uid].get("run_ids") or "").split(";") if x]
                if run_id not in prev:
                    prev.append(run_id)
                progress[uid]["run_ids"] = ";".join(prev)
            result_rows[uid] = row_from_decision(uid, MatchDecision("error"), _now())

    try:
        while True:
            for uid in list(pending_ids()):
                remaining = next_search(units[uid], tried[uid]) is not None
                decision = classify(units[uid], partial.get(uid, []), has_remaining=remaining)
                if decision.needs_more:
                    continue
                finalize(uid, decision, None, None)

            batch: list[tuple[str, str]] = []
            for uid in pending_ids():
                nxt = next_search(units[uid], tried[uid])
                if nxt is None:
                    continue
                batch.append((uid, nxt))
                if len(batch) >= batch_size:
                    break
            if not batch:
                break

            for uid, _ in batch:
                progress[uid]["status"] = "in_progress"
                progress[uid]["updated_at"] = _now()
            save_progress(out_dir / "progress.csv", progress)

            unique_searches = list(dict.fromkeys(s for _, s in batch))
            started = _now()
            log.info("actor searches=%s units=%s", len(unique_searches), [u for u, _ in batch])
            try:
                items, run = run_actor(
                    client, {"searches": unique_searches},
                    wait_secs=wait_secs, timeout_secs=timeout_secs, retries=retries, token=token,
                )
            except ApifyRunError as exc:
                if _quota_error(str(exc)):
                    for uid, _ in batch:
                        progress[uid]["status"] = "pending"
                        progress[uid]["updated_at"] = _now()
                    persist_outputs()
                    maybe_pause(f"Apify rate limit or quota: {exc}")
                mark_error([u for u, _ in batch], str(exc))
                append_run(out_dir / "runs.csv", {
                    "run_id": None, "dataset_id": None,
                    "unit_ids": ";".join(u for u, _ in batch), "status": "error",
                    "started_at": started, "finished_at": _now(), "item_count": 0,
                    "usage_usd": None, "usage_raw": "{}", "input_mode": "searches",
                    "n_input": len(unique_searches),
                })
                persist_outputs()
                check_ratios([u for u, _ in batch])
                continue

            run_id = str(run.get("id") or f"run-{started}")
            dataset_id = str(run.get("defaultDatasetId") or "")
            write_raw(out_dir / "raw" / f"{run_id}.jsonl", items)
            usd, usage_raw = usage_from_run(run)
            append_run(out_dir / "runs.csv", {
                "run_id": run_id, "dataset_id": dataset_id,
                "unit_ids": ";".join(u for u, _ in batch), "status": run.get("status"),
                "started_at": started, "finished_at": _now(), "item_count": len(items),
                "usage_usd": usd, "usage_raw": usage_raw, "input_mode": "searches",
                "n_input": len(unique_searches),
            })
            log.info("run %s items=%s usage_usd=%s", run_id, len(items), usd)

            by_q, leftover = partition_items(items, unique_searches)
            assigned: dict[str, list[dict[str, Any]]] = {uid: list(by_q.get(s, [])) for uid, s in batch}
            still_empty = {uid for uid, got in assigned.items() if not got}
            for item in leftover:
                host = website_registrable(item)
                if not host:
                    continue
                for uid in still_empty:
                    if company_domain(units[uid].get("web_domain")) == host:
                        assigned[uid].append(item)
                        break

            need_detail: list[tuple[str, str, MatchDecision, str]] = []
            for uid, search in batch:
                tried[uid].add(search)
                progress[uid]["tried_searches"] = ";".join(sorted(tried[uid]))
                progress[uid]["attempts"] = int(progress[uid].get("attempts") or 0) + 1
                got = assigned.get(uid, [])
                partial.setdefault(uid, []).extend(got)
                append_partial(out_dir / "partial.jsonl", uid, got)
                remaining = next_search(units[uid], tried[uid]) is not None
                decision = classify(units[uid], partial[uid], has_remaining=remaining)
                if decision.needs_more:
                    progress[uid]["status"] = "pending"
                    progress[uid]["updated_at"] = _now()
                    continue
                if decision.match_status == "matched" and needs_detail_fetch(decision.item):
                    url = linkedin_url(decision.item or {})
                    if url:
                        need_detail.append((uid, url, decision, search))
                        continue
                finalize(uid, decision, run_id, search)

            if need_detail:
                urls = [u for _, u, _, _ in need_detail]
                started_d = _now()
                try:
                    d_items, d_run = run_actor(
                        client, {"companies": urls},
                        wait_secs=wait_secs, timeout_secs=timeout_secs, retries=retries, token=token,
                    )
                    d_id = str(d_run.get("id") or f"run-{started_d}")
                    write_raw(out_dir / "raw" / f"{d_id}.jsonl", d_items)
                    d_usd, d_usage = usage_from_run(d_run)
                    append_run(out_dir / "runs.csv", {
                        "run_id": d_id, "dataset_id": d_run.get("defaultDatasetId"),
                        "unit_ids": ";".join(u for u, _, _, _ in need_detail),
                        "status": d_run.get("status"), "started_at": started_d, "finished_at": _now(),
                        "item_count": len(d_items), "usage_usd": d_usd, "usage_raw": d_usage,
                        "input_mode": "companies", "n_input": len(urls),
                    })
                    by_url = {linkedin_url(i): i for i in d_items if linkedin_url(i)}
                    for uid, url, decision, search in need_detail:
                        if url in by_url:
                            decision.item = by_url[url]
                        finalize(uid, decision, d_id, search)
                except ApifyRunError as exc:
                    log.warning("detail fetch failed (%s); keeping search items", redact(exc, token))
                    for uid, _url, decision, search in need_detail:
                        finalize(uid, decision, run_id, search)

            persist_outputs()
            check_ratios([u for u, _ in batch])
    except ScrapePaused:
        persist_outputs()

    persist_outputs()
    if results_path.exists():
        done = pd.read_csv(results_path, dtype={"unit_id": str}, encoding="utf-8-sig")
        return done[done["unit_id"].astype(str).isin(unit_ids)].reset_index(drop=True)
    return pd.DataFrame(columns=RESULT_COLUMNS)


def summarize(results: pd.DataFrame) -> str:
    if results.empty:
        return "no results"
    status = results["match_status"].astype("string").fillna("").value_counts().to_dict()
    method = results["match_method"].astype("string").fillna("").value_counts().to_dict()
    n = len(results)
    domain_n = int((results["match_method"] == "domain").sum())
    lines = [
        f"units={n} status={status} methods={method}",
        f"domain_share={domain_n}/{n} ({domain_n / n:.0%})",
    ]
    matched = results[results["match_status"] == "matched"]
    if not matched.empty:
        for col in ("description", "industry", "employee_count", "website"):
            filled = int(matched[col].notna().sum()) if col in matched else 0
            lines.append(f"coverage_{col}={filled}/{len(matched)}")
    return "\n".join(lines)


REVIEW_METHODS = frozenset({"claude_review", "human_review"})


def items_by_url(raw_dir: Path) -> dict[str, dict[str, Any]]:
    """Every actor item seen, keyed by LinkedIn URL; a full page beats a thin search hit."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(raw_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line) if line.strip() else None
            except json.JSONDecodeError:
                continue
            url = linkedin_url(item) if isinstance(item, dict) else None
            if url and (url not in out or not needs_detail_fetch(item)):
                out[url] = item
    return out


def apply_review(
    decisions_path: Path,
    out_dir: Path,
    *,
    results_path: Path,
    units_df: pd.DataFrame,
    review_path: Path | None = None,
) -> list[str]:
    """Turn accepted review candidates into ``matched`` rows.

    A row's decision is ``human_decision`` when filled, else ``claude_decision``; ``match_method``
    records which (``human_review`` / ``claude_review``) so training can filter on it. Only units
    still ``ambiguous`` with exactly one accepted candidate are changed. Returns their unit_ids."""
    review_path = review_path or (out_dir.parent / "linkedin_review_queue.csv")
    dec = pd.read_csv(decisions_path, dtype=str, encoding="utf-8-sig")
    human = dec.get("human_decision", pd.Series(index=dec.index, dtype=str)).fillna("").str.strip().str.lower()
    claude = dec.get("claude_decision", pd.Series(index=dec.index, dtype=str)).fillna("").str.strip().str.lower()
    dec["final"] = human.where(human != "", claude)
    dec["method"] = ["human_review" if h else "claude_review" for h in human]
    acc = dec[dec["final"] == "accept"]
    n_acc = acc.groupby("unit_id").size()
    acc = acc[acc["unit_id"].isin(n_acc.index[n_acc == 1])]

    res = pd.read_csv(results_path, dtype={"unit_id": str}, encoding="utf-8-sig").set_index("unit_id", drop=False)
    units = units_from_frame(units_df)
    by_url = items_by_url(out_dir / "raw")
    for items in load_partial(out_dir / "partial.jsonl").values():  # older runs kept items only here
        for item in items:
            url = linkedin_url(item)
            if url and (url not in by_url or (needs_detail_fetch(by_url[url]) and not needs_detail_fetch(item))):
                by_url[url] = item
    rows: list[dict[str, Any]] = []
    now = _now()
    for rec in acc.to_dict(orient="records"):
        uid, url = rec["unit_id"], rec["candidate_url"]
        if uid not in res.index or res.at[uid, "match_status"] != "ambiguous" or uid not in units:
            continue
        item = by_url.get(url)
        if item is None:
            log.warning("apply_review %s: no stored item for %s", uid, url)
            continue
        decision = _matched(units[uid], rec["method"], item)
        decision.group_page = group_page_flag(units[uid], item)
        rows.append(row_from_decision(uid, decision, now))
        log.info("apply_review %s -> matched (%s) url=%s", uid, rec["method"], url)
    if not rows:
        return []
    upsert_results(results_path, rows)
    done = {r["unit_id"] for r in rows}
    write_review_queue(review_path, [], done)
    progress_path = out_dir / "progress.csv"
    if progress_path.exists():
        prog = pd.read_csv(progress_path, dtype=str, encoding="utf-8-sig")
        hit = prog["unit_id"].isin(done)
        prog.loc[hit, "status"] = "matched"
        prog.loc[hit, "match_method"] = prog.loc[hit, "unit_id"].map({r["unit_id"]: r["match_method"] for r in rows})
        prog.loc[hit, "updated_at"] = now
        prog.to_csv(progress_path, index=False, encoding="utf-8-sig")
    return sorted(done)


def reclassify(
    units_df: pd.DataFrame,
    out_dir: Path,
    *,
    results_path: Path,
    review_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Re-run ``classify`` on already-scraped items (no Apify call) and rewrite only units whose
    status or LinkedIn page changed. Returns one ``{unit_id, old_status, new_status, old_url, new_url}``
    per change."""
    review_path = review_path or (out_dir.parent / "linkedin_review_queue.csv")
    res = pd.read_csv(results_path, dtype={"unit_id": str}, encoding="utf-8-sig").set_index("unit_id", drop=False)
    units = {uid: u for uid, u in units_from_frame(units_df).items() if uid in res.index}
    partial = load_partial(out_dir / "partial.jsonl")
    merge_raw_into_partial(out_dir / "raw", units, partial)
    detail = items_by_url(out_dir / "raw")

    changes: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    now = _now()
    for uid, unit in units.items():
        if res.at[uid, "match_method"] in REVIEW_METHODS:
            continue  # a reviewer's decision is never overridden by the rules
        decision = classify(unit, partial.get(uid, []), has_remaining=False)
        new_url = linkedin_url(decision.item) if decision.item else None
        old_url = res.at[uid, "linkedin_url"] if isinstance(res.at[uid, "linkedin_url"], str) else None
        old_status = res.at[uid, "match_status"]
        if decision.match_status == old_status and new_url == old_url:
            continue
        if new_url and needs_detail_fetch(decision.item) and new_url in detail:
            decision.item = detail[new_url]
        rows.append(row_from_decision(uid, decision, now))
        review.extend(review_rows_for(unit, decision))
        changes.append({
            "unit_id": uid, "old_status": old_status, "new_status": decision.match_status,
            "old_url": old_url, "new_url": new_url,
        })
        log.info("reclassify %s: %s -> %s url=%s", uid, old_status, decision.match_status, new_url)

    # The queue only holds candidates of units still ambiguous: drop leftovers of resolved ones.
    not_ambiguous = set(res.index[res["match_status"] != "ambiguous"]) | {c["unit_id"] for c in changes}
    write_review_queue(review_path, review, not_ambiguous)
    if rows:
        upsert_results(results_path, rows)
        progress_path = out_dir / "progress.csv"
        if progress_path.exists():
            prog = pd.read_csv(progress_path, dtype=str, encoding="utf-8-sig")
            by_uid = {r["unit_id"]: r for r in rows}
            for i, uid in prog["unit_id"].items():
                if uid in by_uid:
                    prog.at[i, "status"] = by_uid[uid]["match_status"]
                    prog.at[i, "match_method"] = by_uid[uid]["match_method"]
                    prog.at[i, "updated_at"] = now
            prog.to_csv(progress_path, index=False, encoding="utf-8-sig")
    return changes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument("--out-root", type=Path, default=PROJECT_ROOT / "data" / "processed")
    p.add_argument("--list-path", type=Path, default=None)
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--env-file", type=Path, default=DEFAULT_APIFY_ENV)
    p.add_argument("--pilot", action="store_true", help="20 mixed main units")
    p.add_argument("--pilot2", action="store_true", help="original 20 plus 30 new mixed main units")
    p.add_argument("--pilot-n", type=int, default=PILOT_N)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--all", action="store_true", help="scrape every pending unit in --batch")
    p.add_argument("--batch", default="main", choices=["main", "reserve", "all"])
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--wait-secs", type=int, default=DEFAULT_WAIT_SECS)
    p.add_argument("--timeout-secs", type=int, default=DEFAULT_TIMEOUT_SECS)
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    p.add_argument("--refetch", action="store_true")
    p.add_argument("--reclassify", type=Path, default=None, metavar="RESULTS_CSV",
                   help="re-run matching on stored items (no Apify call) and update this results CSV")
    p.add_argument("--apply-review", type=Path, default=None, metavar="DECISIONS_CSV",
                   help="mark accepted review candidates as matched (no Apify call); needs --results")
    p.add_argument("--results", type=Path, default=None, metavar="RESULTS_CSV")
    a = p.parse_args(argv)

    if a.apply_review is not None:
        list_path = a.list_path or (a.out_root / a.snapshot / "labeling" / LIST_NAME)
        lst = pd.read_csv(list_path, dtype={"unit_id": str}, encoding="utf-8-sig")
        out_dir = a.out_dir or (a.out_root / a.snapshot / "labeling" / "linkedin")
        if a.results is None:
            p.error("--apply-review needs --results RESULTS_CSV")
        setup_log(out_dir / "scrape.log", "")
        done = apply_review(a.apply_review, out_dir, results_path=a.results, units_df=lst)
        print(f"matched_from_review={len(done)}")
        return 0

    if a.reclassify is not None:
        list_path = a.list_path or (a.out_root / a.snapshot / "labeling" / LIST_NAME)
        lst = pd.read_csv(list_path, dtype={"unit_id": str}, encoding="utf-8-sig")
        out_dir = a.out_dir or (a.out_root / a.snapshot / "labeling" / "linkedin")
        setup_log(out_dir / "scrape.log", "")
        changes = reclassify(lst, out_dir, results_path=a.reclassify)
        for c in changes:
            print(f"{c['unit_id']}: {c['old_status']} -> {c['new_status']} ({c['old_url']} -> {c['new_url']})")
        print(f"changed={len(changes)}")
        return 0

    if not a.pilot and not a.pilot2 and not a.all and a.limit is None:
        p.error("refusing to scrape the full list; pass --pilot, --pilot2, --limit N, or --all")

    list_path = a.list_path or (a.out_root / a.snapshot / "labeling" / LIST_NAME)
    lst = pd.read_csv(list_path, dtype={"unit_id": str}, encoding="utf-8-sig")
    if a.batch != "all":
        lst = lst[lst["batch"] == a.batch]
    if a.pilot2:
        lst = select_pilot2(lst, a.pilot_n, 30)
    elif a.pilot:
        lst = select_pilot(lst, a.pilot_n)
    if a.limit is not None:
        lst = lst.head(a.limit)
    out_dir = a.out_dir or (a.out_root / a.snapshot / "labeling" / "linkedin")
    try:
        results = scrape(
            lst, out_dir, env_file=a.env_file, refetch=a.refetch, batch_size=a.batch_size,
            wait_secs=a.wait_secs, timeout_secs=a.timeout_secs, retries=a.retries,
        )
    except ScrapePaused as exc:
        print(f"PAUSED: {exc}")
        pause = out_dir / "pause_reason.txt"
        if pause.exists():
            print(pause.read_text(encoding="utf-8").strip())
        return 2
    print(summarize(results))
    print(f"out_dir={out_dir}")
    pause = out_dir / "pause_reason.txt"
    if pause.exists():
        print("PAUSED:", pause.read_text(encoding="utf-8").strip())
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
