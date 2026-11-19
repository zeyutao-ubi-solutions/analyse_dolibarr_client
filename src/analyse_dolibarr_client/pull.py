"""Snapshot the Dolibarr marts from Snowflake into data/raw/<date>/ as Parquet.

Each table is pulled in full at its native grain, without filtering or joins.
Filtering (valid orders, entities, intercompany) belongs to later analysis steps.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from analyse_dolibarr_client.snowflake import SnowflakeConfig, connect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "raw"

DEFAULT_TABLES: dict[str, str] = {
    "MART_ORDERS_TO_DATE": "Customer order (CO) lines: customer, date, product, amount, NAF fields",
    "MART_INVOICING_TO_DATE": "Customer invoice lines",
    "MART_CONTRACTS_TO_DATE": "Contract and service lines",
    "MART_REVENUES_PER_CUSTOMER": "Revenue per customer and period, tier, New/Churn/Upsell",
    "MART_THIRD_PARTIES": "Third-party registry: SIREN, address, client/supplier/intercompany flags",
    "MART_PRODUCT_CATALOG": "SKU catalog and revenue categories",
    "MART_SUPPLIER_ORDERS_TO_DATE": "Supplier order lines, to separate suppliers from customers",
    "MART_ELEMENT_LINKS": "Dolibarr object links (order to invoice, contract, shipment)",
}

_TABLE_NAME = re.compile(r"^MART_[A-Z0-9_]+$")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tables",
        nargs="+",
        default=list(DEFAULT_TABLES),
        help="Mart tables to pull (default: all customer-analysis tables)",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--snapshot",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Snapshot folder name (default: today's UTC date)",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing snapshot folder")
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    return parser.parse_args(argv)


def _validate_tables(tables: list[str]) -> list[str]:
    names = [t.strip().upper() for t in tables]
    bad = [t for t in names if not _TABLE_NAME.match(t)]
    if bad:
        raise ValueError(f"Only MART_* tables can be pulled: {', '.join(bad)}")
    return names


def _pull_table(cur, table: str, target: Path) -> dict:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    expected = cur.fetchone()[0]

    cur.execute(f"SELECT * FROM {table}")
    columns = [(d.name, d.type_code) for d in cur.description]
    arrow = cur.fetch_arrow_all()
    if arrow is None:
        arrow = pa.table({name: pa.array([], type=pa.null()) for name, _ in columns})
    if arrow.num_rows != expected:
        raise RuntimeError(f"{table}: fetched {arrow.num_rows} rows, COUNT(*) said {expected}")

    pq.write_table(arrow, target, compression="zstd")
    return {
        "table": table,
        "file": target.name,
        "row_count": arrow.num_rows,
        "columns": [{"name": f.name, "type": str(f.type)} for f in arrow.schema],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    tables = _validate_tables(args.tables)
    config = SnowflakeConfig.from_env(args.env_file)

    final_dir = args.output_root / args.snapshot
    if final_dir.exists() and not args.force:
        print(f"{final_dir} already exists; pass --force to replace it", file=sys.stderr)
        return 1
    staging_dir = args.output_root / f".{args.snapshot}.partial"
    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True)

    started_at = datetime.now(timezone.utc)
    entries = []
    with connect(config) as conn:
        cur = conn.cursor()
        try:
            for table in tables:
                entry = _pull_table(cur, table, staging_dir / f"{table.lower()}.parquet")
                entry["description"] = DEFAULT_TABLES.get(table, "")
                entries.append(entry)
                print(f"{table}: {entry['row_count']} rows")
        finally:
            cur.close()

    manifest = {
        "source": f"{config.database}.{config.schema}",
        "role": config.role,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "tables": entries,
    }
    (staging_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    if final_dir.exists():
        shutil.rmtree(final_dir)
    staging_dir.rename(final_dir)
    print(f"Snapshot written to {final_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
