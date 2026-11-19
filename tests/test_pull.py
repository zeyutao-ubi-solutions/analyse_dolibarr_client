import pytest

from analyse_dolibarr_client.pull import _validate_tables
from analyse_dolibarr_client.snowflake import SnowflakeConfig


def test_tables_are_normalised_to_upper_case():
    assert _validate_tables(["mart_orders_to_date"]) == ["MART_ORDERS_TO_DATE"]


@pytest.mark.parametrize(
    "name",
    ["FCT_CUSTOMER_INVOICES", "MART_ORDERS; DROP TABLE X", "DBT__2_MODELED.MART_X"],
)
def test_non_mart_or_unsafe_names_are_rejected(name):
    with pytest.raises(ValueError):
        _validate_tables([name])


def test_schema_other_than_marts_is_rejected(monkeypatch, tmp_path):
    for key, value in {
        "SNOWFLAKE_ACCOUNT": "acc",
        "SNOWFLAKE_USER": "u",
        "SNOWFLAKE_ROLE": "r",
        "SNOWFLAKE_WAREHOUSE": "w",
        "SNOWFLAKE_DATABASE": "d",
        "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8",
        "SNOWFLAKE_SCHEMA": "DBT__2_MODELED",
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        SnowflakeConfig.from_env(tmp_path / "missing.env")
