from datetime import date

import pandas as pd
import pytest

from analyse_dolibarr_client.companies import (
    MATCH_AMBIGUOUS,
    MATCH_ERP,
    MATCH_EXACT,
    MATCH_NORMALIZED,
    MATCH_UNMATCHED,
    Snapshot,
    build,
    classify_buyer,
    clean_company_id,
)
from analyse_dolibarr_client.report import render_readme

SNAP_DATE = date(2026, 11, 18)


def _line(cid, name, order, amount, *, cat="Composants RFID & IoT", entity="Ubi Solutions",
          day="2025-01-10", ref="P1", recurring=False, not_real=False, valid=True):
    return {
        "ORDER_ITEM_ID": f"{order}-{amount}-{cat}-{ref}",
        "ORDER_ID": order,
        "ORDER_NUMBER": order,
        "ORDER_DATE": pd.Timestamp(day).date() if day else None,
        "ENTITY_NAME": entity,
        "CUSTOMER_ID": cid,
        "CUSTOMER_NAME": name,
        "COUNTRY_CODE": "France",
        "SECTION": None,
        "CLASSE": None,
        "IS_VALID_ORDER": valid,
        "IS_NOT_REAL_ITEM": not_real,
        "ITEM_CATEGORY": cat,
        "ITEM_SUBCATEGORY_LV1": None,
        "PRODUCT_REF": ref,
        "IS_RECURRING_REVENUE": recurring,
        "ITEM_ORDERED_AMOUNT_HT_EUR": amount,
    }


def _tp(tid, name, *, client=True, supplier=False, interco=False, entity="1", siren=None, town=None):
    return {
        "THIRD_PARTY_ID": tid, "THIRD_PARTY_NAME": name, "ENTITY_ID": entity,
        "IS_CLIENT": client, "IS_SUPPLIER": supplier, "IS_INTERCOMPANY": interco,
        "COUNTRY_CODE": "FR", "TAX_NUMBER": None, "SIREN": siren, "SIRET": None,
        "ZIP_CODE": None, "TOWN": town,
    }


@pytest.fixture
def snap() -> Snapshot:
    lines = [
        # exact match, repeat buyer of one category
        _line("c-exact", "HERTA", "o1", 1000.0, day="2023-03-01"),
        _line("c-exact", "HERTA", "o2", 500.0),
        _line("c-exact", "HERTA", "o2", 0.0, cat="NULL", ref=None),
        # normalized match (legal suffix), one shot
        _line("c-norm", "Kermené SAS", "o3", 200.0, cat="Licences & Abonnements", recurring=True),
        # ambiguous: two client registry rows, different SIRENs
        _line("c-amb", "GEODIS", "o4", 300.0, cat="Projets & Intégration"),
        _line("c-amb", "GEODIS", "o5", 100.0, cat="Terminaux mobiles & tablettes"),
        # intercompany (group word must be ignored for this check)
        _line("c-interco", "Groupe Page Up", "o6", 999.0, entity="Ubi Smart"),
        # unmatched; CUSTOMER_ID equals a THIRD_PARTY_ID of another company on purpose
        _line("42", "Totally Unknown Co", "o7", 50.0, entity="Page Up"),
        _line("42", "Totally Unknown Co", "o8", 50.0, entity="Ubi Solutions", cat="Maintenance & Support"),
        # not-real line: counted as a line, excluded from amount
        _line("c-exact", "HERTA", "o2", 77.0, not_real=True),
        # invalid order: ignored entirely
        _line("c-exact", "HERTA", "o9", 1e6, valid=False),
        # missing date still counted in totals
        _line("c-nodate", "NoDate", "o10", 10.0, day=None),
    ]
    orders = pd.DataFrame(lines)
    valid = orders[orders["IS_VALID_ORDER"]].copy()
    tp = pd.DataFrame(
        [
            _tp("1", "HERTA", siren="393034327", town="Paris"),
            _tp("2", "KERMENE", siren="123456789"),
            _tp("3", "GEODIS", siren="161544512", town="Clichy"),
            _tp("4", "GEODIS", siren="880080569", town="Lyon"),
            _tp("5", "GEODIS", client=False),
            _tp("6", "PAGE UP", interco=True, entity="3"),
            _tp("42", "SOMEONE ELSE"),
            _tp("7", "HERTA", client=False, supplier=True),
        ]
    )
    supplier_orders = pd.DataFrame(
        {"SUPPLIER_NAME": ["Kermene"], "THIRD_PARTY_ID": ["2"], "IS_DRAFT_ORDER": [False]}
    )
    invoices = pd.DataFrame(
        {
            "INVOICE_ID": [1, 1, 2], "CUSTOMER_ID": ["c-exact", "c-exact", "c-norm"],
            "INVOICE_AMOUNT_HT_EUR": [1400.0, 1400.0, 200.0], "IS_INTERCOMPANY": [False, False, False],
        }
    )
    contracts = pd.DataFrame({"CONTRACT_ID": [10], "CUSTOMER_ID": ["c-norm"]})
    return Snapshot("2026-11-18", valid, len(orders), tp, supplier_orders, invoices, contracts)


@pytest.fixture
def result(snap):
    return build(snap, SNAP_DATE)


def _row(result, cid):
    allc = result.all_customers
    return allc[allc["customer_id"] == cid].iloc[0]


def test_match_statuses(result):
    assert _row(result, "c-exact")["match_status"] == MATCH_EXACT
    # rule 4: IS_CLIENT row preferred over the non-client duplicate
    assert _row(result, "c-exact")["third_party_id"] == "1"
    assert _row(result, "c-norm")["match_status"] == MATCH_NORMALIZED
    assert _row(result, "c-norm")["third_party_id"] == "2"
    amb = _row(result, "c-amb")
    assert amb["match_status"] == MATCH_AMBIGUOUS
    assert pd.isna(amb["third_party_id"])
    assert amb["third_party_ids"] == "3;4"
    assert pd.isna(amb["town"])  # candidates disagree, nothing invented


def test_never_joins_on_customer_id(result):
    row = _row(result, "42")
    assert row["match_status"] == MATCH_UNMATCHED
    assert pd.isna(row["third_party_id"])


def test_intercompany_excluded_from_main_list(result):
    assert _row(result, "c-interco")["is_intercompany"]
    assert "c-interco" not in set(result.companies["customer_id"])
    assert not result.companies["is_intercompany"].any()
    assert "intercompany_customer" in set(result.issues["issue_type"])


def test_issues(result):
    types = set(result.issues["issue_type"])
    assert {"ambiguous_match", "siren_conflict_candidates", "intercompany_customer"} <= types


def test_amounts_and_counts(result):
    herta = _row(result, "c-exact")
    assert herta["amount_ht_eur"] == 1500.0  # not-real 77 and invalid 1e6 excluded
    assert herta["n_orders"] == 2
    assert herta["n_order_lines"] == 4
    assert herta["n_invoices"] == 1
    assert herta["invoice_amount_ht_eur"] == 1400.0
    assert herta["order_minus_invoice_ht_eur"] == 100.0
    assert herta["n_years_active"] == 2
    assert str(herta["first_order_date"]) == "2023-03-01"
    assert herta["recency_days"] == (SNAP_DATE - date(2025, 1, 10)).days
    assert herta["item_categories"] == "Composants RFID & IoT"  # "NULL" text lines dropped
    assert herta["top_product_refs"] == "P1:1500.00"
    assert herta["is_also_supplier"]  # same-name registry row is a supplier

    kerm = _row(result, "c-norm")
    assert kerm["share_recurring"] == 1.0
    assert kerm["has_contract"]
    assert kerm["supplier_evidence"]

    pu = _row(result, "42")
    assert pu["entity_names"] == "Page Up;Ubi Solutions"


def test_summary_tables_reconcile(result):
    total = result.companies["amount_ht_eur"].sum()
    assert result.orders_by_category["amount_ht_eur"].sum() == pytest.approx(total)
    assert result.orders_by_entity["amount_ht_eur"].sum() == pytest.approx(total)
    co = result.category_cooccurrence
    assert co.loc[co["category_a"] == co["category_b"], "amount_ht_eur"].sum() == pytest.approx(total)
    # undated line kept with an empty year
    assert result.orders_by_category["year"].isna().any()


def test_cooccurrence_pairs(result):
    co = result.category_cooccurrence
    pair = co[(co["category_a"] == "Projets & Intégration") & (co["category_b"] == "Terminaux mobiles & tablettes")]
    assert pair["n_customers_both"].iloc[0] == 1


def test_readme_renders(snap, result):
    text = render_readme(snap, result, SNAP_DATE)
    assert "主名单" in text and "buyer_pattern" in text


@pytest.mark.parametrize(
    "n_orders, amount, cats, expected",
    [
        (1, 100.0, {"Composants RFID & IoT": 100.0}, "one_shot"),
        (3, 0.0, {}, "other"),
        (3, 100.0, {"Maintenance & Support": 80.0, "Composants RFID & IoT": 20.0}, "license_or_maintenance"),
        (3, 100.0, {"Composants RFID & IoT": 75.0, "Autres": 25.0}, "repeat_product"),
        (3, 100.0, {"Composants RFID & IoT": 60.0, "Projets & Intégration": 40.0}, "mix_hardware_project"),
        (3, 100.0, {"Composants RFID & IoT": 60.0, "Formation": 1.0, "Autres": 39.0}, "other"),
        (3, 100.0, {"Unknown": 50.0, "Autres": 50.0}, "other"),
    ],
)
def test_classify_buyer(n_orders, amount, cats, expected):
    assert classify_buyer(n_orders, amount, cats) == expected


@pytest.mark.parametrize(
    "siren, siret, expected",
    [
        ("393 034 327", None, "393034327"),
        (None, "39303432700014", "393034327"),
        ("B41040924", None, "B41040924"),
        ("DE260851003", None, "DE260851003"),
        ("import110", None, None),
        ("Vtiger672", None, None),
        ("PRO 7892", None, None),
        ("PL121", None, None),
    ],
)
def test_clean_company_id(siren, siret, expected):
    assert clean_company_id(siren, siret) == expected


def test_history_truncated(result):
    # only late-history entities -> truncated; any Ubi Solutions order -> full history
    assert not _row(result, "c-exact")["history_truncated"]
    assert _row(result, "c-interco")["history_truncated"]
    assert not _row(result, "42")["history_truncated"]  # Page Up + Ubi Solutions
    assert "订单历史可能不全" not in str(_row(result, "42")["notes"])
    assert "history_truncated" in result.companies.columns


# --------------------------------------------------------------------------------------
# ERP socid layer
# --------------------------------------------------------------------------------------


@pytest.fixture
def snap_erp(snap) -> Snapshot:
    from dataclasses import replace

    tp = pd.concat([snap.third_parties, pd.DataFrame([_tp("8", "TOTALLY UNKNOWN COMPANY SA")])], ignore_index=True)
    erp = pd.DataFrame(
        {
            "ORDER_ID": ["o1", "o4", "o5", "o6", "o7", "o8"],
            "CUSTOMER_ID": ["c-exact", "c-amb", "c-amb", "c-interco", "42", "42"],
            "erp_socid": ["1", "3", "4", "6", "8", "99"],
            # o8: same id but a different ref in the ERP -> must not be used
            "socid_trusted": [True, True, True, True, True, False],
            "md5_socid_equals_customer_id": ["False"] * 6,
            "id_found": [True] * 6,
        }
    )
    # o11: an order of customer 42 billed to the internal company PAGE UP (socid 6)
    extra = pd.DataFrame([_line("42", "Totally Unknown Co", "o11", 70.0)])
    erp = pd.concat(
        [erp, pd.DataFrame([{"ORDER_ID": "o11", "CUSTOMER_ID": "42", "erp_socid": "6", "socid_trusted": True,
                             "md5_socid_equals_customer_id": "False", "id_found": True}])],
        ignore_index=True,
    )
    orders = pd.concat([snap.orders, extra], ignore_index=True)
    return replace(snap, orders=orders, third_parties=tp, erp_order_socid=erp)


@pytest.fixture
def result_erp(snap_erp):
    return build(snap_erp, SNAP_DATE)


def test_erp_socid_resolves_name_unmatched(result_erp):
    row = _row(result_erp, "42")
    assert row["match_status"] == MATCH_ERP
    assert row["third_party_id"] == "8"
    assert row["name_match_status"] == MATCH_UNMATCHED
    assert row["name_vs_erp"] == "name_unmatched"
    assert row["erp_orders_verified"] == 2  # o7 + o11; o8 is not trusted
    assert row["third_party_name"] == "TOTALLY UNKNOWN COMPANY SA"
    assert row["lookup_name"] == "TOTALLY UNKNOWN COMPANY"
    assert row["lookup_name_source"] == "third_party_name"
    assert row["order_lookup_name"] == "Totally Unknown Co"
    assert not row["lookup_name_conflict"]  # shares "TOTALLY UNKNOWN"
    assert row["lookup_query"].startswith("TOTALLY UNKNOWN COMPANY ")


def test_erp_multiple_third_parties_primary_is_largest(result_erp):
    row = _row(result_erp, "c-amb")
    assert row["match_status"] == MATCH_ERP
    assert row["third_party_id"] == "3"
    assert row["erp_third_parties"] == "3:300.00;4:100.00"
    assert row["town"] == "Clichy"
    assert row["name_vs_erp"] == "erp_in_name_candidates"
    assert "erp_multiple_third_parties" in set(result_erp.issues["issue_type"])
    assert "ambiguous_match" not in set(result_erp.issues["issue_type"])


def test_erp_keeps_name_fallback_and_intercompany(result_erp):
    assert _row(result_erp, "c-norm")["match_status"] == MATCH_NORMALIZED  # no ERP order
    assert _row(result_erp, "c-norm")["lookup_name_source"] == "customer_name"
    assert _row(result_erp, "c-exact")["name_vs_erp"] == "same"
    assert "c-interco" not in set(result_erp.companies["customer_id"])
    assert _row(result_erp, "c-interco")["is_intercompany"]


def test_erp_summaries_reconcile_and_readme(snap_erp, result_erp):
    total = result_erp.companies["amount_ht_eur"].sum()
    assert result_erp.orders_by_category["amount_ht_eur"].sum() == pytest.approx(total)
    text = render_readme(snap_erp, result_erp, SNAP_DATE)
    assert "ERP socid" in text


def test_attach_socid_requires_id_and_ref():
    from analyse_dolibarr_client.erp_socid import attach_socid

    orders = pd.DataFrame(
        {
            "ORDER_ID": ["1", "2", "3"], "ORDER_NUMBER": ["CO1", "CO2", "CO3"], "ORDER_DATE": [None] * 3,
            "ENTITY_NAME": ["Ubi Solutions"] * 3, "CUSTOMER_ID": ["a", "b", "c"], "CUSTOMER_NAME": ["A", "B", "C"],
            "IS_VALID_ORDER": [True, True, True],
        }
    )
    erp = pd.DataFrame(
        {"erp_order_id": ["1", "2"], "erp_ref": ["CO1", "CO2-other"], "erp_socid": ["10", "20"], "erp_entity": ["1", "1"], "erp_date": [0, 0]}
    )
    m = attach_socid(orders, erp).set_index("ORDER_ID")
    assert m.loc["1", "socid_trusted"]
    assert not m.loc["2", "socid_trusted"]  # ref differs
    assert not m.loc["3", "socid_trusted"]  # not in ERP


def test_erp_intercompany_orders_excluded_from_amounts(snap_erp, result_erp):
    row = _row(result_erp, "42")
    assert row["amount_ht_eur"] == 100.0  # o7 + o8; o11 (billed to PAGE UP) dropped
    assert row["intercompany_excluded_ht_eur"] == 70.0
    assert row["n_orders"] == 2
    assert row["third_party_id"] == "8"
    assert "(interco)" in row["erp_third_parties"]
    assert not row["is_intercompany"]
    assert "erp_includes_intercompany" in set(result_erp.issues["issue_type"])
    # totals: main list + excluded intercompany customers + dropped orders = all valid orders
    allc = result_erp.all_customers
    total = snap_erp.orders["ITEM_ORDERED_AMOUNT_HT_EUR"][~snap_erp.orders["IS_NOT_REAL_ITEM"]].sum()
    excluded_customers = allc.loc[allc["is_intercompany"], "amount_ht_eur"].sum()
    assert result_erp.companies["amount_ht_eur"].sum() + excluded_customers + 70.0 == pytest.approx(total)
    assert result_erp.orders_by_entity["amount_ht_eur"].sum() == pytest.approx(result_erp.companies["amount_ht_eur"].sum())
