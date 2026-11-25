"""Product line of each order line: géolocalisation, traçabilité (RFID) or Ubi Cloud.

Business lines (confirmed 2026-11-20): hardware géolocalisation (BLE / GPS / LoRa) and
traçabilité (RFID); software Connected Things and Ubi Cloud. Connected Things is the
géolocalisation platform, so it is the same line as géolocalisation (``geoloc``).

The datahub's ITEM_CATEGORY cannot tell the two apart (``Traceurs et objets connectés`` is
mostly RFID UHF textile tags), so the line is decided per product:

1. Dolibarr product tags, read-only from the API (``erp_product_tags.csv``): anything under
   the ``GPSBLE`` tag is ``geoloc``; ``Portique RFID`` / ``Kit RFID TC21`` / ``Terminaux RFID``
   are ``rfid``. Source ``tag``.
2. Otherwise rules on the product name / subcategory / manufacturer. The GPSBLE tag only
   exists for products since ~2024, so older trackers (LoRa, GPS T27, Scepter beacons) and
   BLE tracker rentals are only found this way. Source ``name_rule`` (or ``subcategory``).

Mobile terminals, scanners and printers that merely *have* Bluetooth/GPS are never geoloc.

CLI (read-only GET): ``uv run python -m analyse_dolibarr_client.product_lines --snapshot <d> --env-file <.env>``
writes ``data/processed/<snapshot>/erp_product_tags.csv``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:  # erp_socid imports companies, which imports this module
    from analyse_dolibarr_client.erp_socid import ErpClient

TAGS_NAME = "erp_product_tags.csv"
GEOLOC, RFID, UBI_CLOUD, OTHER = "geoloc", "rfid", "ubi_cloud", "other"
LINES = (GEOLOC, RFID, UBI_CLOUD)
LINE_LABELS = {
    GEOLOC: "Géolocalisation / Connected Things",
    RFID: "Traçabilité (RFID)",
    UBI_CLOUD: "Ubi Cloud",
}

GEOLOC_ROOT_TAGS = {"GPSBLE"}
RFID_ROOT_TAGS = {"Portique RFID", "Kit RFID TC21", "Terminaux RFID"}

_DEVICE = re.compile(
    r"scan|gryphon|headset|imprim|printer|\bESL\b|android|\bGMS\b|\b2D\b|imager|terminal|tablet", re.I
)
_GEOLOC_NAME = re.compile(
    r"\bBLE\b|beacon|tracker|traceur|g[ée]olocalisation|\bLoRa|RTLS|\bUWB\b|EnviroTrack|SmallTrack|TrackSense"
    r"|sigfox|NbIoT",
    re.I,
)
_RFID_NAME = re.compile(r"RFID|\bUHF\b|UBITex|FenoDISC|tunnel", re.I)
_UBI_CLOUD_NAME = re.compile(r"ubi[\s_-]*cloud", re.I)
RFID_SUBCATEGORIES = frozenset(
    {"Balises/étiquettes RFID et cartes ID", "Lecteurs et antennes RFID", "Portiques/Cabines et tunnels"}
)
RFID_MANUFACTURERS = frozenset({"FENOTAG", "Impinj", "Feig"})
NON_DEVICE_CATEGORIES_EXCLUDED = frozenset({"Terminaux mobiles & tablettes", "Imprimantes"})


# ------------------------------------------------------------------------------ ERP tags


def fetch_product_tags(client: "ErpClient", entity_id: str = "1") -> pd.DataFrame:
    """Every product category and the products in it (GET only), with each tag's root path."""
    status, cats = client.get("categories?type=product&sortfield=t.rowid&sortorder=ASC&limit=1000", entity_id)
    if status != 200 or not isinstance(cats, list):
        raise SystemExit(f"product categories listing failed: HTTP {status}")
    by_id = {str(c["id"]): c for c in cats}

    def path(cid: str) -> list[str]:
        out, seen = [], set()
        while cid in by_id and cid not in seen:
            seen.add(cid)
            out.append(by_id[cid].get("label") or "")
            cid = str(by_id[cid].get("fk_parent") or "0")
        return out[::-1]

    rows = []
    for cid in by_id:
        status, objs = client.get(f"categories/{cid}/objects?type=product&limit=5000", entity_id)
        if status == 404 or not isinstance(objs, list):
            continue
        p = path(cid)
        for o in objs:
            rows.append(
                {
                    "product_id": str(o.get("id")),
                    "product_ref": o.get("ref"),
                    "product_label": o.get("label"),
                    "tag_id": cid,
                    "tag_label": by_id[cid].get("label"),
                    "tag_path": " > ".join(p),
                }
            )
    return pd.DataFrame(rows, columns=["product_id", "product_ref", "product_label", "tag_id", "tag_label", "tag_path"])


def tag_lines(tags: pd.DataFrame | None, catalog: pd.DataFrame | None = None) -> dict[str, str]:
    """product_id -> geoloc / rfid from tag paths; ids kept only when the ref agrees with the catalog."""
    if tags is None or tags.empty:
        return {}
    t = tags.copy()
    if catalog is not None:
        ref = catalog.assign(SKU_ID=catalog["SKU_ID"].astype(str)).set_index("SKU_ID")["SKU_NUMBER"]
        t = t[t["product_id"].map(ref) == t["product_ref"]]
    out: dict[str, str] = {}
    for pid, p in zip(t["product_id"], t["tag_path"].fillna("")):
        parts = set(p.split(" > "))
        if parts & GEOLOC_ROOT_TAGS:
            out[str(pid)] = GEOLOC
        elif parts & RFID_ROOT_TAGS and out.get(str(pid)) != GEOLOC:
            out[str(pid)] = RFID
    return out


# ------------------------------------------------------------------------------ classification


def add_product_lines(
    lines: pd.DataFrame, catalog: pd.DataFrame | None, tags: pd.DataFrame | None
) -> pd.DataFrame:
    """Adds ``product_line`` (geoloc / rfid / other) and ``product_line_source`` to order lines."""
    out = lines.copy()

    def col(name: str) -> pd.Series:  # tolerate extracts without product columns
        return out[name] if name in out.columns else pd.Series(None, index=out.index, dtype=object)

    pid = col("PRODUCT_ID").astype(str)
    if catalog is not None:
        names = pid.map(catalog.assign(SKU_ID=catalog["SKU_ID"].astype(str)).set_index("SKU_ID")["SKU_NAME"])
    else:
        names = pd.Series(None, index=out.index, dtype=object)
    name = names.fillna("").astype(str)
    by_tag = pid.map(tag_lines(tags, catalog))

    device = col("ITEM_CATEGORY").isin(NON_DEVICE_CATEGORIES_EXCLUDED) | name.str.contains(_DEVICE)
    geo_name = ~device & name.str.contains(_GEOLOC_NAME)
    rfid_sub = col("ITEM_SUBCATEGORY_LV1").isin(RFID_SUBCATEGORIES)
    rfid_other = name.str.contains(_RFID_NAME) | col("ITEM_MANUFACTURER").isin(RFID_MANUFACTURERS)
    cloud_name = name.str.contains(_UBI_CLOUD_NAME)

    line = pd.Series(OTHER, index=out.index)
    source = pd.Series(None, index=out.index, dtype=object)
    for mask, ln, src in (
        (rfid_other & ~geo_name, RFID, "name_rule"),
        (rfid_sub & ~geo_name, RFID, "subcategory"),
        (geo_name, GEOLOC, "name_rule"),
        (cloud_name, UBI_CLOUD, "name_rule"),
        (by_tag == RFID, RFID, "tag"),
        (by_tag == GEOLOC, GEOLOC, "tag"),  # last: a tag beats any rule
    ):
        line = line.mask(mask, ln)
        source = source.mask(mask, src)
    out["product_line"] = line
    out["product_line_source"] = source
    return out


def customer_product_lines(lines: pd.DataFrame, amount_col: str = "amount_real") -> pd.DataFrame:
    """Per CUSTOMER_ID: amount per line, the lines bought (amount > 0) and where geoloc came from."""
    g = lines.groupby(["CUSTOMER_ID", "product_line"])[amount_col].sum().unstack(fill_value=0.0)
    for ln in (*LINES, OTHER):
        if ln not in g.columns:
            g[ln] = 0.0
    res = pd.DataFrame(index=g.index)
    res["amount_geoloc_ht_eur"] = g[GEOLOC]
    res["amount_rfid_ht_eur"] = g[RFID]
    res["amount_ubi_cloud_ht_eur"] = g[UBI_CLOUD]
    res["product_lines"] = [
        ";".join(ln for ln, v in zip(LINES, vals) if v > 0) for vals in zip(g[GEOLOC], g[RFID], g[UBI_CLOUD])
    ]
    geo = lines[(lines["product_line"] == GEOLOC) & (lines[amount_col] > 0)]
    src = geo.groupby("CUSTOMER_ID")["product_line_source"].agg(lambda s: "tag" if "tag" in set(s) else "name_rule")
    res["geoloc_source"] = src.reindex(res.index)
    res.loc[res["amount_geoloc_ht_eur"] <= 0, "geoloc_source"] = None
    return res


# ------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", required=True)
    p.add_argument("--out-root", type=Path, default=Path("data/processed"))
    p.add_argument("--env-file", type=Path, required=True)
    a = p.parse_args(argv)
    from analyse_dolibarr_client.erp_socid import ErpClient, read_env_file

    tags = fetch_product_tags(ErpClient(read_env_file(a.env_file)))
    out = a.out_root / a.snapshot
    out.mkdir(parents=True, exist_ok=True)
    tags.to_csv(out / TAGS_NAME, index=False)
    print(f"{len(tags)} product-tag rows, {tags['product_id'].nunique()} products, {tags['tag_id'].nunique()} tags")
    print(tags.groupby("tag_path")["product_id"].nunique().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
