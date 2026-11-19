import pandas as pd
import pytest

from analyse_dolibarr_client.companies import attach_web_hints
from analyse_dolibarr_client.erp_thirdparties import (
    attach_web,
    contact_domains,
    email_domain,
    linkedin_url,
    normalize_url,
    slim,
    url_domain,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("www.Geodis.com", "geodis.com"),
        ("https://www.groupe-omerin.com/index.php/?x=fr", "groupe-omerin.com"),
        ("edf.f", None),
        ("n/a", None),
        ("https://www.facebook.com/acme", None),
        ("https://fr.linkedin.com/company/acme", None),
        (None, None),
    ],
)
def test_url_domain(value, expected):
    assert url_domain(value) == expected


def test_normalize_url_adds_scheme_and_rejects_bad_hosts():
    assert normalize_url("www.acme.fr") == "https://www.acme.fr"
    assert normalize_url("edf.f") is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Jean.Dupont@Acme.FR", "acme.fr"),
        ("compta@acme.fr; achats@acme.fr", "acme.fr"),
        ("n/a; achats@acme.fr", "acme.fr"),
        ("Jean <jean@acme.fr>", "acme.fr"),
        ("someone@gmail.com", None),
        ("x@t-online.de", None),
        ("ap@email.basware.com", None),
        ("no-at-sign", None),
    ],
)
def test_email_domain(value, expected):
    assert email_domain(value) == expected


def test_linkedin_url_from_fields():
    assert linkedin_url({"linkedin": "acme"}) == "https://www.linkedin.com/company/acme"
    assert linkedin_url({"socialnetworks": {"linkedin": "https://www.linkedin.com/company/acme/"}}) == (
        "https://www.linkedin.com/company/acme/"
    )
    assert linkedin_url({"url": "https://fr.linkedin.com/company/acme"}) == "https://fr.linkedin.com/company/acme"
    assert linkedin_url({"linkedin": "", "socialnetworks": []}) is None


def test_slim_keeps_no_personal_fields():
    row = slim(
        {
            "id": 7, "entity": 1, "name": "ACME", "idprof1": "123 456 789", "url": "acme.fr",
            "email": "jean.dupont@acme.fr", "phone": "0102030405", "note_private": "secret",
            "firstname": "Jean", "lastname": "Dupont", "effectif": "51 - 100",
        }
    )
    assert row["email_domain"] == "acme.fr"
    assert row["erp_siren"] == "123456789"
    typo = slim({"id": 8, "name": "X", "url": "https://info@acme.es"})
    assert typo["website"] is None and typo["website_domain"] is None
    assert typo["email_domain"] == "acme.es"
    flat = " ".join(str(v) for v in row.values())
    for leaked in ("jean", "Dupont", "0102030405", "secret"):
        assert leaked not in flat


def test_attach_web_requires_matching_name():
    tp = pd.DataFrame(
        {"THIRD_PARTY_ID": [1, 2], "THIRD_PARTY_NAME": ["ACME SAS", "OLD NAME"], "SIREN": ["123456789", None]}
    )
    erp = pd.DataFrame(
        {"erp_tp_id": ["1", "2"], "erp_tp_name": ["Acme", "Something Else"], "website": ["https://acme.fr", None]}
    )
    m = attach_web(tp, erp).set_index("THIRD_PARTY_ID")
    assert m.at["1", "tp_name_matches"]
    assert not m.at["2", "tp_name_matches"]


# --------------------------------------------------------------------------- attach_web_hints


def _web(rows):
    cols = [
        "THIRD_PARTY_ID", "THIRD_PARTY_NAME", "SIREN", "website", "website_domain", "email_domain", "linkedin_url",
        "headcount_band", "contact_email_domains",
    ]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)


def _tp(rows):
    return pd.DataFrame(rows, columns=["THIRD_PARTY_ID", "COUNTRY_CODE", "IS_INTERCOMPANY"])


def _cust(**kw):
    base = {
        "customer_id": "c1", "lookup_name": "ACME", "order_lookup_name": "ACME", "lookup_name_conflict": False,
        "country_code": "FR", "siren": None, "third_party_id": "1", "third_party_ids": "1", "notes": "",
    }
    return pd.DataFrame([base | kw])


def test_own_website_beats_email_and_borrowed():
    web = _web(
        [
            ("1", "ACME", "111111111", None, None, "acme-mail.fr", None, "51 - 100"),
            ("2", "ACME", "111111111", "https://acme.fr", "acme.fr", None, None, None),
            ("3", "ACME", None, "https://www.acme.com", "acme.com", None, None, None),
        ]
    )
    tp = _tp([("1", "FR", False), ("2", "FR", False), ("3", "FR", False)])
    out = attach_web_hints(_cust(third_party_ids="1;3", siren="111111111"), web, tp).iloc[0]
    assert out["web_domain"] == "acme.com"
    assert out["web_domain_source"] == "own_website"
    assert out["website"] == "https://www.acme.com"
    assert out["web_domain_alternatives"] == "acme-mail.fr;acme.fr"
    assert out["headcount_band"] == "51 - 100"


def test_borrows_by_siren_then_by_name_in_same_country():
    web = _web(
        [
            ("2", "OTHER LABEL", "111111111", None, None, "acme.fr", None, None),
            ("3", "ACME", None, "https://acme.es", "acme.es", None, None, None),
            ("4", "ACME", None, "https://acme.de", "acme.de", None, None, None),
        ]
    )
    tp = _tp([("1", "FR", False), ("2", "FR", False), ("3", "ES", False), ("4", "FR", False)])
    by_siren = attach_web_hints(_cust(siren="111 111 111"), web, tp).iloc[0]
    assert (by_siren["web_domain"], by_siren["web_domain_source"]) == ("acme.fr", "same_siren_email")
    by_name = attach_web_hints(_cust(), web, tp).iloc[0]
    assert (by_name["web_domain"], by_name["web_domain_source"]) == ("acme.de", "same_name_website")


def test_no_borrowing_for_short_names_conflicting_order_names_or_group_domains():
    web = _web(
        [
            ("2", "TCS", None, "https://tcs.com", "tcs.com", None, None, None),
            ("3", "ORANGE", None, "https://orange.com", "orange.com", None, None, None),
            ("4", "CODEO", None, None, None, "pageup.fr", None, None),
            ("9", "PAGE UP", None, None, None, "pageup-internal.fr", None, None),
            ("5", "SHOP", None, None, None, "pageup-internal.fr", None, None),
        ]
    )
    tp = _tp([("1", "FR", False), ("2", "FR", False), ("3", "FR", False), ("4", "FR", False), ("9", "FR", True), ("5", "FR", False)])
    assert attach_web_hints(_cust(lookup_name="TCS", order_lookup_name="TCS"), web, tp).iloc[0]["web_domain"] is None
    conflict = _cust(lookup_name="EXERTIS AZENN", order_lookup_name="ORANGE", lookup_name_conflict=True)
    assert attach_web_hints(conflict, web, tp).iloc[0]["web_domain"] is None
    assert attach_web_hints(_cust(lookup_name="CODEO", order_lookup_name="CODEO"), web, tp).iloc[0]["web_domain"] is None
    own_internal = _cust(lookup_name="SHOP", order_lookup_name="SHOP", third_party_id="5", third_party_ids="5")
    assert attach_web_hints(own_internal, web, tp).iloc[0]["web_domain"] is None


def test_shared_domain_note_and_missing_web_file():
    web = _web([("1", "ACME", None, "https://acme.fr", "acme.fr", None, None, None)])
    tp = _tp([("1", "FR", False)])
    two = pd.concat([_cust(), _cust(customer_id="c2")], ignore_index=True)
    out = attach_web_hints(two, web, tp)
    assert out["notes"].str.contains("域名与其他客户共用").all()
    empty = attach_web_hints(_cust(), None, tp).iloc[0]
    assert empty["web_domain"] is None and empty["notes"] == ""


def test_contact_domains_keep_only_domains():
    contacts = [
        {"id": 1, "socid": 7, "email": "jean.dupont@acme.fr"},
        {"id": 2, "socid": 7, "email": "marie@acme.fr"},
        {"id": 3, "socid": 7, "email": "x@integrator.com"},
        {"id": 3, "socid": 7, "email": "x@integrator.com"},  # same contact listed under another entity
        {"id": 4, "socid": 7, "email": "perso@gmail.com"},
        {"id": 5, "socid": None, "email": "y@orphan.fr"},
    ]
    df = contact_domains(contacts)
    assert df.to_dict("records") == [
        {
            "erp_tp_id": "7",
            "contact_email_domain": "acme.fr",
            "contact_email_domains": "acme.fr:2;integrator.com:1",
            "n_contacts_with_domain": 3,
        }
    ]
    assert "jean" not in df.to_csv() and "@" not in df.to_csv()


def test_contact_email_tier_prefers_name_match_and_skips_group_domain():
    web = _web(
        [
            ("1", "ACME", None, None, None, None, None, None, "ubisolutions.net:5;integrator.com:3;acme-group.com:1"),
        ]
    )
    tp = _tp([("1", "FR", False)])
    out = attach_web_hints(_cust(), web, tp).iloc[0]
    assert out["web_domain"] == "acme-group.com"
    assert out["web_domain_source"] == "own_contact_email"
    assert out["web_domain_matches_name"] is True
    assert out["web_domain_alternatives"] == "integrator.com"
    assert out["website"] is None


def test_contact_email_ranks_below_company_email():
    web = _web([("1", "ACME", None, None, None, "acme.fr", None, None, "acme.com:9")])
    out = attach_web_hints(_cust(), web, _tp([("1", "FR", False)])).iloc[0]
    assert (out["web_domain"], out["web_domain_source"]) == ("acme.fr", "own_email")
