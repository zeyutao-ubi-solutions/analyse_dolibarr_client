"""Read-only Snowflake connection to the Dolibarr marts."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import snowflake.connector
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

MART_SCHEMA = "DBT__3_MARTS"


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str
    user: str
    role: str
    warehouse: str
    database: str
    schema: str
    private_key_path: Path
    private_key_passphrase: str

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "SnowflakeConfig":
        load_dotenv(env_file, override=True)
        missing = [
            name
            for name in (
                "SNOWFLAKE_ACCOUNT",
                "SNOWFLAKE_USER",
                "SNOWFLAKE_ROLE",
                "SNOWFLAKE_WAREHOUSE",
                "SNOWFLAKE_DATABASE",
                "SNOWFLAKE_PRIVATE_KEY_PATH",
            )
            if not os.environ.get(name, "").strip()
        ]
        if missing:
            raise ValueError(f"Missing in environment or .env: {', '.join(missing)}")
        schema = os.environ.get("SNOWFLAKE_SCHEMA", MART_SCHEMA).strip()
        if schema.upper() != MART_SCHEMA:
            raise ValueError(f"Only {MART_SCHEMA} may be read; got SNOWFLAKE_SCHEMA={schema}")
        return cls(
            account=os.environ["SNOWFLAKE_ACCOUNT"].strip().replace("_", "-"),
            user=os.environ["SNOWFLAKE_USER"].strip(),
            role=os.environ["SNOWFLAKE_ROLE"].strip(),
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"].strip(),
            database=os.environ["SNOWFLAKE_DATABASE"].strip(),
            schema=MART_SCHEMA,
            private_key_path=Path(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"].strip()).expanduser(),
            private_key_passphrase=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "").strip(),
        )


def _private_key_der(config: SnowflakeConfig) -> bytes:
    password = config.private_key_passphrase.encode() if config.private_key_passphrase else None
    key = serialization.load_pem_private_key(config.private_key_path.read_bytes(), password=password)
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@contextmanager
def connect(config: SnowflakeConfig) -> Iterator[snowflake.connector.SnowflakeConnection]:
    conn = snowflake.connector.connect(
        account=config.account,
        user=config.user,
        private_key=_private_key_der(config),
        role=config.role,
        warehouse=config.warehouse,
        database=config.database,
        schema=config.schema,
        login_timeout=30,
        network_timeout=120,
        session_parameters={"QUERY_TAG": "analyse_dolibarr_client.pull"},
    )
    try:
        yield conn
    finally:
        conn.close()
