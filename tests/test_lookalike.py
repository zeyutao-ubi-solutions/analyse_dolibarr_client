import pandas as pd

from analyse_dolibarr_client.lookalike import (
    LABEL_COLUMNS,
    build_sheet,
    build_units,
    effective_types,
    prospect_rows,
    review_priority,
    validate_labels,
    value_tier,
)


def _companies(rows):
    base = {
        "customer_name": None, "order_lookup_name": None, "third_party_name": None, "town": None,
        "web_domain_matches_name": True, "n_orders": 1, "first_order_date": "2020-01-01",
        "last_order_date": "2020-01-01", "top_item_category": None, "category_mix": "", "buyer_pattern": "one_shot",
        "suspect_integrator": False, "suspect_integrator_reason": "", "is_also_supplier": False,
        "supplier_evidence": "", "lookup_name_conflict": False, "notes": "", "country_code": "FR",
        "siren": None, "n_years_active": 1, "amount_recurring_ht_eur": 0.0, "amount_first_24m_ht_eur": 0.0,
        "months_since_first_order": 60, "history_truncated": False,
    }
    df = pd.DataFrame([base | r for r in rows])
    df["third_party_ids"] = df["third_party_id"]
    df["amount_first_24m_ht_eur"] = df["amount_first_24m_ht_eur"].where(df["amount_first_24m_ht_eur"] > 0, df["amount_ht_eur"])
    return df


COMPANIES = _companies(
    [
        {"customer_id": "big", "lookup_name": "GEODIS", "web_domain": "geodis.com", "third_party_id": "1", "amount_ht_eur": 900.0, "siren": "111111111"},
        {"customer_id": "sub", "lookup_name": "GEODIS BM", "web_domain": "geodis.com", "third_party_id": "2", "amount_ht_eur": 50.0},
        {"customer_id": "integ", "lookup_name": "ACME SYSTEMS", "web_domain": "acme-sys.fr", "third_party_id": "3", "amount_ht_eur": 40.0, "suspect_integrator": True},
        {"customer_id": "conf", "lookup_name": "EXERTIS", "web_domain": None, "third_party_id": "4", "amount_ht_eur": 5.0, "lookup_name_conflict": True},
        {"customer_id": "zero", "lookup_name": "ZERO", "web_domain": None, "third_party_id": "5", "amount_ht_eur": 0.0},
    ]
)


def test_review_priority_flags_and_top_amount():
    c = COMPANIES[COMPANIES["amount_ht_eur"] > 0].set_index("customer_id")
    p = review_priority(c)
    assert p.loc["integ", "priority"] == "P1"
    assert p.loc["conf", "priority"] == "P1"
    assert p.loc["big", "priority"] == "P2" and "top_90pct_amount" in p.loc["big", "review_reasons"]
    assert p.loc["sub", "priority"] == "P3"


def test_sheet_keeps_labels_and_drops_zero_amount():
    first = build_sheet(COMPANIES, None)
    assert "zero" not in set(first["customer_id"])
    assert list(first["customer_id"][:2]) == ["integ", "conf"]  # P1 first, by amount
    first.loc[first["customer_id"] == "integ", LABEL_COLUMNS] = ["end_user", "high", "https://x", "zt", "2026-11-20", "uses it"]
    # A customer labeled earlier that is gone from the new build is kept, not lost.
    gone = first.iloc[[0]].assign(customer_id="old", customer_type="competitor")
    again = build_sheet(COMPANIES, pd.concat([first, gone]))
    row = again.set_index("customer_id").loc["integ"]
    assert row["customer_type"] == "end_user" and row["comment"] == "uses it"
    assert again.set_index("customer_id").loc["old", "priority"] == "gone"


def test_validate_and_effective_types():
    sheet = build_sheet(COMPANIES, None)
    sheet.loc[sheet["customer_id"] == "conf", "customer_type"] = "integrator_reseller"
    sheet.loc[sheet["customer_id"] == "integ", "customer_type"] = "unsure"
    assert validate_labels(sheet) == []
    t = effective_types(sheet).set_index("customer_id")
    assert (t.loc["conf", "effective_type"], t.loc["conf", "type_source"]) == ("integrator_reseller", "manual")
    assert (t.loc["integ", "effective_type"], t.loc["integ", "type_source"]) == ("integrator_reseller", "auto")
    bad = sheet.assign(customer_type="enduser")
    assert any("enduser" in e for e in validate_labels(bad))


def test_value_tier():
    assert value_tier(1, 0.0, 30_000, 60, False) == "core"
    assert value_tier(3, 10.0, 1_000, 60, False) == "core"
    assert value_tier(1, 0.0, 1_000, 60, False) == "standard"
    assert value_tier(1, 0.0, 99_000, 12, False) == "immature"
    assert value_tier(5, 9.0, 99_000, 60, True) == "truncated"


def _prospects(rows):
    cols = ["customer_id", "lookup_name", "country_code", "web_domain", "web_domain_matches_name", "siren", "third_party_id", "is_supplier"]
    return pd.DataFrame(rows, columns=cols)


def test_units_group_by_domain_and_merge_prospects():
    types = effective_types(build_sheet(COMPANIES, None))
    prospects = _prospects(
        [
            ("tp:10", "GEODIS WILSON", "FR", "geodis.com", True, None, "10", False),  # same domain as a customer
            ("tp:11", "GEO OTHER", "FR", None, False, "111 111 111", "11", False),  # same SIREN as a customer
            ("tp:12", "NEWCO", "ES", "newco.es", True, None, "12", False),
            ("tp:13", "NEWCO IBERIA", "ES", "newco.es", True, None, "13", False),
            ("tp:14", "ZEBRA", "US", "zebra.com", True, None, "14", True),
        ]
    )
    u = build_units(COMPANIES, types, prospects).set_index("unit_id")
    geo = u.loc["geodis.com"]
    assert geo["label"] == "positive" and geo["n_end_user_customers"] == 2 and geo["n_prospect_records"] == 2
    assert geo["amount_ht_eur"] == 950.0
    assert u.loc["acme-sys.fr", "label"] == "excluded"
    assert u.loc["acme-sys.fr", "exclusion_reason"] == "integrator_reseller"
    assert u.loc["tp:4", "needs_review"]  # P1 customer still on its auto suggestion
    assert u.loc["tp:5", "exclusion_reason"] == "excluded_zero_amount"
    assert u.loc["newco.es", "label"] == "unlabeled" and u.loc["newco.es", "n_prospect_records"] == 2
    assert u.loc["zebra.com", "label"] == "excluded" and u.loc["zebra.com", "exclusion_reason"] == "supplier"
    assert u.loc["geodis.com", "split_group"] == "geodis.com"
    # No product-line columns on these companies -> nobody is in the allocation set.
    assert not u["in_allocation_set"].any()


def test_prospect_rows_only_never_clients():
    tp = pd.DataFrame(
        {
            "THIRD_PARTY_ID": [1, 2, 3, 4],
            "THIRD_PARTY_NAME": ["Prospect SAS", "Client SA", "Both SARL", "Ubi Smart"],
            "IS_PROSPECT": [True, False, True, True],
            "IS_CLIENT": [False, True, True, False],
            "IS_INTERCOMPANY": [False, False, False, True],
            "IS_SUPPLIER": [False, False, False, False],
            "COUNTRY_CODE": ["FR", "FR", "FR", "FR"],
            "SIREN": [None, None, None, None],
        }
    )
    web = pd.DataFrame(
        {
            "THIRD_PARTY_ID": ["1"], "THIRD_PARTY_NAME": ["Prospect SAS"], "SIREN": [None],
            "website": ["https://prospect.fr"], "website_domain": ["prospect.fr"], "email_domain": [None],
            "linkedin_url": [None], "headcount_band": [None], "contact_email_domains": [None],
        }
    )
    rows = prospect_rows(tp, web)
    assert list(rows["third_party_id"]) == ["1"]
    assert rows.loc[0, "web_domain"] == "prospect.fr"
    assert rows.loc[0, "lookup_name"] == "Prospect"


def test_country_weights_match_positive_mix():
    from analyse_dolibarr_client.lookalike import add_country_weights, effective_sample_size

    rows = (
        [("p", "positive", "FR")] * 30 + [("p", "positive", "ES")] * 10 + [("p", "positive", "DE")] * 2
        + [("u", "unlabeled", "FR")] * 20 + [("u", "unlabeled", "ES")] * 60 + [("u", "unlabeled", "DE")] * 20
        + [("x", "excluded", "FR")] * 3
    )
    units = pd.DataFrame(
        [{"unit_id": f"{k}{i}", "label": lab, "country_code": c} for i, (k, lab, c) in enumerate(rows)]
    )
    u = add_country_weights(units, min_positives=5)
    assert set(u["country_bucket"]) == {"FR", "ES", "other"}  # DE has 2 positives -> other
    assert (u.loc[u["label"] == "positive", "sample_weight"] == 1).all()
    assert (u.loc[u["label"] == "excluded", "sample_weight"] == 0).all()
    unl = u[u["label"] == "unlabeled"]
    pos_mix = u[u["label"] == "positive"]["country_bucket"].value_counts(normalize=True)
    w_mix = unl.groupby("country_bucket")["sample_weight"].sum() / unl["sample_weight"].sum()
    assert (w_mix - pos_mix).abs().max() < 1e-9
    assert abs(unl["sample_weight"].sum() - len(unl)) < 1e-9
    assert 0 < effective_sample_size(unl["sample_weight"]) < len(unl)


def _factor_units():
    rows = (
        [("positive", "FR")] * 30 + [("unlabeled", "FR")] * 70
        + [("positive", "ES")] * 2 + [("unlabeled", "ES")] * 98
        + [("positive", "PT")] * 1 + [("unlabeled", "PT")] * 1
        + [("unlabeled", None)] * 5 + [("excluded", "FR")] * 4
    )
    return pd.DataFrame([{"unit_id": str(i), "label": lab, "country_code": c} for i, (lab, c) in enumerate(rows)])


def test_wilson_interval():
    from analyse_dolibarr_client.lookalike import wilson_interval

    lo, hi = wilson_interval(30, 100)
    assert 0.21 < lo < 0.22 and 0.39 < hi < 0.40
    assert wilson_interval(0, 0) == (None, None)


def test_country_factors_shrink_small_countries_and_skip_unknown():
    from analyse_dolibarr_client.lookalike import country_factors

    f = country_factors(_factor_units()).set_index("country_code")
    assert f.loc["FR", "suggested_factor"] == 1.0 and f.loc["FR", "n_units"] == 100  # excluded not counted
    assert abs(f.loc["ES", "historical_rate"] - 0.02) < 1e-9
    # PT is 1/2 = 50% raw, above FR; the prior pulls it far below FR.
    assert f.loc["PT", "historical_rate"] == 0.5
    assert f.loc["PT", "suggested_factor"] < 0.5
    assert pd.isna(f.loc["unknown", "suggested_factor"])
    assert f.loc["unknown", "factor_source"] == "missing"
    assert "set it by hand" in f.loc["PT", "auto_note"]


def test_country_factors_keep_manual_override_and_validate():
    from analyse_dolibarr_client.lookalike import attach_country_factor, country_factors, validate_factors

    first = country_factors(_factor_units())
    first.loc[first["country_code"] == "ES", ["manual_factor", "manual_note", "set_by"]] = ["0.6", "expand Spain", "zt"]
    again = country_factors(_factor_units(), first.astype(object)).set_index("country_code")
    assert again.loc["ES", "factor"] == 0.6 and again.loc["ES", "factor_source"] == "manual"
    assert again.loc["ES", "manual_note"] == "expand Spain"
    u = attach_country_factor(_factor_units(), again.reset_index())
    assert set(u.loc[u["country_code"] == "ES", "country_factor"]) == {0.6}
    assert u.loc[u["country_code"].isna(), "country_factor"].isna().all()
    bad = first.astype(object)
    bad.loc[0, "manual_factor"] = "high"
    bad.loc[1, "manual_factor"] = "-1"
    errs = validate_factors(bad)
    assert len(errs) == 2


def test_allocation_set_is_customers_with_a_line():
    lines = _companies(
        [
            {"customer_id": "g", "lookup_name": "GEO", "web_domain": "geo.fr", "third_party_id": "1", "amount_ht_eur": 10.0},
            {"customer_id": "n", "lookup_name": "NONE", "web_domain": "none.fr", "third_party_id": "2", "amount_ht_eur": 10.0},
            {"customer_id": "i", "lookup_name": "INT SYS", "web_domain": "int.fr", "third_party_id": "3", "amount_ht_eur": 10.0,
             "suspect_integrator": True},
        ]
    ).assign(
        amount_geoloc_ht_eur=[10.0, 0.0, 10.0], amount_rfid_ht_eur=0.0, amount_ubi_cloud_ht_eur=[5.0, 0.0, 0.0],
        geoloc_source=["tag", None, "tag"],
    )
    types = effective_types(build_sheet(lines, None))
    u = build_units(lines, types, _prospects([("tp:9", "P", "FR", "p.fr", True, None, "9", False)])).set_index("unit_id")
    assert u.loc["geo.fr", "in_allocation_set"]
    assert u.loc["geo.fr", "positive_geoloc"] and u.loc["geo.fr", "positive_ubi_cloud"]
    assert not u.loc["none.fr", "in_allocation_set"] and u.loc["none.fr", "label"] == "positive"
    assert not u.loc["int.fr", "in_allocation_set"]  # integrator: excluded, not a customer example
    assert not u.loc["p.fr", "in_allocation_set"]
