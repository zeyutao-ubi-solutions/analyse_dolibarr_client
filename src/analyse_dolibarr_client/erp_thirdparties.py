"""Read-only pull of company-level web identifiers for third parties from the Dolibarr API.

Lists ``/thirdparties`` per entity (GET only) and keeps just what helps find a company's
LinkedIn page: name, SIREN (idprof1), website, LinkedIn link, headcount band, the
*domain* of the company email, and the email *domains* of its contacts (``/contacts``).
Full email addresses, phones, notes and contact persons' names are never kept. Output: ``erp_thirdparties.csv`` under ``data/processed/<snapshot>/``.

A row is only trusted for a snapshot third party when the ERP name agrees with the
snapshot name (the API instance diverges from the snapshot source for recent records).
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from analyse_dolibarr_client.companies import ENTITY_ID_TO_NAME
from analyse_dolibarr_client.erp_socid import ErpClient, read_env_file
from analyse_dolibarr_client.names import core_key

OUTPUT_NAME = "erp_thirdparties.csv"

# Mailbox providers: an address there says nothing about the company's own domain.
FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.fr", "outlook.com", "outlook.fr",
    "live.com", "live.fr", "msn.com", "yahoo.com", "yahoo.fr", "yahoo.es", "ymail.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "orange.fr", "wanadoo.fr", "free.fr",
    "sfr.fr", "neuf.fr", "laposte.net", "bbox.fr", "gmx.fr", "gmx.com", "gmx.de", "web.de",
    "protonmail.com", "proton.me", "telefonica.net", "libero.it", "sapo.pt", "club-internet.fr",
    "t-online.de", "freenet.de", "gmx.net", "wp.pl", "op.pl", "o2.pl", "onet.pl", "interia.pl",
    "163.com", "126.com", "qq.com", "mail.ru", "yandex.ru", "seznam.cz", "bluewin.ch",
    "hotmail.es", "hotmail.co.uk", "yahoo.co.uk", "outlook.es", "live.co.uk", "btinternet.com",
    "virgilio.it", "tiscali.it", "sky.com", "aliceadsl.fr", "numericable.fr",
    "gnet.tn", "planet.tn", "topnet.tn",  # Tunisian ISP mailboxes
}
# E-invoicing / document platforms: an address there is the customer's AP inbox, not its domain.
_PLATFORM_EMAIL = re.compile(r"basware|tungsten|esker|invoice|factur|dematerial|docusign|coupa|ariba|pennylane")


# Sites that are not the company's own: directories, social networks, search engines.
NON_COMPANY_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "google.com",
    "google.fr", "goo.gl", "societe.com", "pagesjaunes.fr", "infogreffe.fr", "verif.com",
    "pappers.fr", "annuaire-entreprises.data.gouv.fr", "linkedin.com", "fr.linkedin.com",
}
_DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")


def _host(value) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or " " in v or "@" in v:  # "@": an email typed into the website field
        return None
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    try:
        host = (urlsplit(v).hostname or "").lower()
    except ValueError:
        return None
    host = host[4:] if host.startswith("www.") else host
    return host if _DOMAIN_RE.match(host) else None


def normalize_url(value) -> str | None:
    """The URL with a scheme, or None when it has no valid host (e.g. ``edf.f``)."""
    if _host(value) is None:
        return None
    v = value.strip()
    return v if re.match(r"^https?://", v, re.I) else "https://" + v


def url_domain(value) -> str | None:
    """The company's own web domain; None for directories, social networks and LinkedIn."""
    host = _host(value)
    if host is None or host in NON_COMPANY_DOMAINS or host.endswith(".linkedin.com"):
        return None
    return host


def email_domain(value) -> str | None:
    """Company domain from an email address; the address itself is discarded."""
    if not isinstance(value, str) or "@" not in value:
        return None
    first = next(p for p in re.split(r"[;,\s]+", value.strip()) if "@" in p)
    dom = first.rsplit("@", 1)[1].lower().strip(" .>;,")
    if not _DOMAIN_RE.match(dom) or dom in FREE_MAIL_DOMAINS or _PLATFORM_EMAIL.search(dom):
        return None
    return dom


def linkedin_url(row: dict) -> str | None:
    """LinkedIn link from the dedicated field or the socialnetworks map, if it points at LinkedIn."""
    candidates = [row.get("linkedin")]
    sn = row.get("socialnetworks")
    if isinstance(sn, dict):
        candidates.append(sn.get("linkedin"))
    url = row.get("url")
    if isinstance(url, str) and "linkedin.com/" in url.lower():
        candidates.append(url)
    for c in candidates:
        if isinstance(c, str) and c.strip():
            v = c.strip()
            if "linkedin.com" in v.lower():
                return normalize_url(v)
            # A bare handle such as "company/acme" or "acme".
            return "https://www.linkedin.com/" + (v.lstrip("/") if "/" in v else f"company/{v}")
    return None


def slim(o: dict) -> dict:
    return {
        "erp_tp_id": str(o.get("id")),
        "erp_entity": str(o.get("entity")) if o.get("entity") is not None else None,
        "erp_tp_name": o.get("name"),
        "erp_name_alias": o.get("name_alias") or None,
        "erp_siren": (o.get("idprof1") or "").replace(" ", "") or None,
        "website": normalize_url(o.get("url")) if url_domain(o.get("url")) else None,
        "website_domain": url_domain(o.get("url")),
        "email_domain": email_domain(o.get("email")) or email_domain(re.sub(r"^\w+://", "", str(o.get("url") or ""))),
        "linkedin_url": linkedin_url(o),
        "headcount_band": o.get("effectif") or None,
    }


def list_erp_thirdparties(client: ErpClient, entity_ids=tuple(ENTITY_ID_TO_NAME), page_size: int = 500) -> pd.DataFrame:
    rows = []
    for ent in entity_ids:
        page = 0
        while True:
            status, body = client.get(f"thirdparties?sortfield=t.rowid&sortorder=ASC&limit={page_size}&page={page}", ent)
            if status == 404 or not isinstance(body, list) or not body:
                break
            if status != 200:
                raise SystemExit(f"thirdparties listing failed for entity {ent}: HTTP {status}")
            rows.extend(slim(o) for o in body)
            print(f"  entity {ent}: page {page}, {len(body)} third parties")
            if len(body) < page_size:
                break
            page += 1
    return pd.DataFrame(rows).drop_duplicates("erp_tp_id")


def contact_domains(contacts: list[dict]) -> pd.DataFrame:
    """Per third party: company domains seen on its contacts' email addresses.

    Only the domain survives this function; names, addresses, phones and the people's own
    LinkedIn links are dropped here and never written anywhere.
    """
    counts: dict[str, Counter] = {}
    seen: set[str] = set()
    for o in contacts:
        cid = str(o.get("id"))
        socid = o.get("socid")
        if cid in seen or socid in (None, "", 0, "0"):
            continue
        seen.add(cid)
        dom = email_domain(o.get("email"))
        if dom:
            counts.setdefault(str(socid), Counter())[dom] += 1
    rows = [
        {
            "erp_tp_id": socid,
            "contact_email_domain": c.most_common(1)[0][0],
            "contact_email_domains": ";".join(f"{d}:{n}" for d, n in c.most_common()),
            "n_contacts_with_domain": sum(c.values()),
        }
        for socid, c in counts.items()
    ]
    return pd.DataFrame(rows, columns=["erp_tp_id", "contact_email_domain", "contact_email_domains", "n_contacts_with_domain"])


def list_erp_contact_domains(client: ErpClient, entity_ids=tuple(ENTITY_ID_TO_NAME), page_size: int = 500) -> pd.DataFrame:
    contacts: list[dict] = []
    for ent in entity_ids:
        page = 0
        while True:
            status, body = client.get(f"contacts?sortfield=t.rowid&sortorder=ASC&limit={page_size}&page={page}", ent)
            if status == 404 or not isinstance(body, list) or not body:
                break
            if status != 200:
                raise SystemExit(f"contacts listing failed for entity {ent}: HTTP {status}")
            contacts.extend({"id": o.get("id"), "socid": o.get("socid"), "email": o.get("email")} for o in body)
            print(f"  entity {ent}: page {page}, {len(body)} contacts")
            if len(body) < page_size:
                break
            page += 1
    return contact_domains(contacts)


def attach_web(tp: pd.DataFrame, erp: pd.DataFrame) -> pd.DataFrame:
    """Per snapshot third party: ERP web fields, trusted only when the names agree."""
    t = tp[["THIRD_PARTY_ID", "THIRD_PARTY_NAME", "SIREN"]].copy()
    t["THIRD_PARTY_ID"] = t["THIRD_PARTY_ID"].astype(str)
    m = t.merge(erp, how="left", left_on="THIRD_PARTY_ID", right_on="erp_tp_id")
    m["tp_found"] = m["erp_tp_id"].notna()
    m["tp_name_matches"] = [
        bool(a) and core_key(a) == core_key(b) if isinstance(a, str) and isinstance(b, str) else False
        for a, b in zip(m["THIRD_PARTY_NAME"], m["erp_tp_name"])
    ]
    return m


def run(raw_dir: Path, out_dir: Path, env_file: Path) -> pd.DataFrame:
    tp = pd.read_parquet(raw_dir / "mart_third_parties.parquet")
    client = ErpClient(read_env_file(env_file))
    erp = list_erp_thirdparties(client)
    erp = erp.merge(list_erp_contact_domains(client), how="left", on="erp_tp_id")
    res = attach_web(tp, erp)
    out_dir.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_dir / OUTPUT_NAME, index=False)
    return res


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", required=True)
    p.add_argument("--raw-root", default="data/raw")
    p.add_argument("--out-root", default="data/processed")
    p.add_argument("--env-file", required=True, help="existing .env with DOLIBARR_URL / DOLIBARR_API_KEY")
    a = p.parse_args()
    res = run(Path(a.raw_root) / a.snapshot, Path(a.out_root) / a.snapshot, Path(a.env_file))
    ok = res[res["tp_name_matches"]]
    print(f"snapshot third parties {len(res)}, found {int(res['tp_found'].sum())}, name agrees {len(ok)}; "
          f"website {int(ok['website'].notna().sum())}, linkedin {int(ok['linkedin_url'].notna().sum())}, "
          f"email domain {int(ok['email_domain'].notna().sum())}, "
          f"contact email domain {int(ok['contact_email_domain'].notna().sum())}")


if __name__ == "__main__":
    main()
