"""Read-only lookup of each order's third party (socid) through the Dolibarr REST API.

The order mart's CUSTOMER_ID is a hash, not a Dolibarr third-party id, so the only
reliable key is the order's own ``socid`` in the ERP. This module sends GET requests
only: it lists order headers per entity (``/orders``, paged), keeps id/ref/socid/entity,
and writes ``erp_orders.csv`` and ``erp_order_socid.csv`` under ``data/processed/<snapshot>/``.
A snapshot order gets a socid only when both its ORDER_ID and its ORDER_NUMBER agree with
the ERP, because the API instance and the snapshot source diverge for recent orders.

Credentials are read at runtime from an existing ``.env`` file (DOLIBARR_URL,
DOLIBARR_API_KEY, DOLIBARR_SSL_VERIFY); they are never copied, printed or written out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analyse_dolibarr_client.companies import ENTITY_ID_TO_NAME

ENTITY_NAME_TO_ID = {v: k for k, v in ENTITY_ID_TO_NAME.items()}
OUTPUT_NAME = "erp_order_socid.csv"


@dataclass(frozen=True)
class ErpConfig:
    base_url: str
    api_key: str
    ssl_verify: bool


def read_env_file(path: Path) -> ErpConfig:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    url = values.get("DOLIBARR_URL", "").rstrip("/")
    if not url.endswith("/api/index.php"):
        url += "/api/index.php"
    key = values.get("DOLIBARR_API_KEY", "")
    if not key:
        raise SystemExit(f"DOLIBARR_API_KEY missing in {path}")
    verify = values.get("DOLIBARR_SSL_VERIFY", "true").lower() not in {"0", "false", "no"}
    return ErpConfig(url, key, verify)


class ErpClient:
    """Minimal GET-only client. There is deliberately no method that writes."""

    def __init__(self, cfg: ErpConfig, min_interval: float = 0.15):
        self._cfg = cfg
        self._ctx = None if cfg.ssl_verify else ssl._create_unverified_context()
        self._min_interval = min_interval
        self._last = 0.0

    def get(self, path: str, entity_id: str | None = None) -> tuple[int, object]:
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        headers = {"DOLAPIKEY": self._cfg.api_key, "Accept": "application/json"}
        if entity_id:
            headers["DOLAPIENTITY"] = str(entity_id)
        req = urllib.request.Request(f"{self._cfg.base_url}/{path.lstrip('/')}", headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=30) as resp:
                status, body = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        finally:
            self._last = time.monotonic()
        try:
            return status, json.loads(body or b"null")
        except json.JSONDecodeError:
            return status, None


def list_erp_orders(client: ErpClient, entity_ids=tuple(ENTITY_ID_TO_NAME), page_size: int = 500) -> pd.DataFrame:
    """Every order header visible to the key, per entity: id, ref, socid, entity only."""
    rows = []
    for ent in entity_ids:
        page = 0
        while True:
            status, body = client.get(
                f"orders?sortfield=t.rowid&sortorder=ASC&limit={page_size}&page={page}", ent
            )
            if status == 404 or not isinstance(body, list) or not body:
                break
            if status != 200:
                raise SystemExit(f"orders listing failed for entity {ent}: HTTP {status}")
            for o in body:
                rows.append(
                    {
                        "erp_order_id": str(o.get("id")),
                        "erp_ref": o.get("ref"),
                        "erp_socid": str(o["socid"]) if o.get("socid") not in (None, "") else None,
                        "erp_entity": str(o.get("entity")) if o.get("entity") is not None else None,
                        "erp_date": o.get("date_commande"),
                    }
                )
            print(f"  entity {ent}: page {page}, {len(body)} orders")
            if len(body) < page_size:
                break
            page += 1
    return pd.DataFrame(rows).drop_duplicates("erp_order_id")


def md5_hex(value) -> str | None:
    return hashlib.md5(value.encode()).hexdigest() if isinstance(value, str) and value else None


def attach_socid(orders: pd.DataFrame, erp: pd.DataFrame) -> pd.DataFrame:
    """Per valid snapshot order: the ERP socid, kept only when ORDER_ID *and* ref agree."""
    o = orders[orders["IS_VALID_ORDER"].fillna(False).astype(bool)]
    o = o.drop_duplicates("ORDER_ID")[["ORDER_ID", "ORDER_NUMBER", "ORDER_DATE", "ENTITY_NAME", "CUSTOMER_ID", "CUSTOMER_NAME"]]
    m = o.merge(erp, how="left", left_on="ORDER_ID", right_on="erp_order_id")
    m["id_found"] = m["erp_order_id"].notna()
    m["ref_matches"] = m["erp_ref"] == m["ORDER_NUMBER"]
    m["socid_trusted"] = m["ref_matches"] & m["erp_socid"].notna()
    m["md5_socid_equals_customer_id"] = m["erp_socid"].map(md5_hex) == m["CUSTOMER_ID"]
    return m


def run(raw_dir: Path, out_dir: Path, env_file: Path) -> pd.DataFrame:
    orders = pd.read_parquet(raw_dir / "mart_orders_to_date.parquet")
    erp = list_erp_orders(ErpClient(read_env_file(env_file)))
    out_dir.mkdir(parents=True, exist_ok=True)
    erp.to_csv(out_dir / "erp_orders.csv", index=False)
    res = attach_socid(orders, erp)
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
    print(f"snapshot orders {len(res)}, id found {int(res['id_found'].sum())}, "
          f"id+ref agree {int(res['ref_matches'].sum())}")


if __name__ == "__main__":
    main()
