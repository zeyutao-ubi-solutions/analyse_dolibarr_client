import math

import pytest

from analyse_dolibarr_client.names import (
    basic_key,
    core_key,
    country_iso,
    domain_matches_name,
    exact_key,
    group_free_key,
    integrator_keywords,
    lookup_name,
    name_notes,
    names_unrelated,
)


def test_exact_key_is_trim_upper_only():
    assert exact_key("  Ouest-France ") == "OUEST-FRANCE"
    assert exact_key("   ") is None
    assert exact_key(None) is None
    assert exact_key(math.nan) is None


@pytest.mark.parametrize(
    "a, b",
    [
        ("Ouest-France", "OUEST FRANCE"),
        ("Kermené", "KERMENE"),
        ("L'Oréal", "LOREAL"),
        ("Mulliez-Flory", "Mulliez  Flory"),
    ],
)
def test_basic_key_equal(a, b):
    assert basic_key(a) == basic_key(b)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("HERTA SAS", "HERTA"),
        ("GOODYEAR FRANCE S.A.S", "GOODYEAR FRANCE"),
        ("WROTOM sp. z o. o.", "WROTOM"),
        ("ILUNION LAVANDERÍAS DE CANARIAS, S.A", "ILUNION LAVANDERIAS DE CANARIAS"),
        ("EDF (FR)", "EDF"),
        ("SUSSEX OPCO LTD (Radisson Blu Sussex Hotel)", "SUSSEX OPCO"),
        ("Wonderbox.fr", "WONDERBOX"),
        ("SAS MENFENIL", "MENFENIL"),
        ("Kuehne + Nagel (AG & Co.) KG", "KUEHNE NAGEL"),
    ],
)
def test_core_key(name, expected):
    assert core_key(name) == expected


def test_core_key_strips_only_one_legal_form():
    # Repeated stripping would collapse this to the generic "CREACIONES".
    assert core_key("Creaciones B V s.l.") == "CREACIONES B V"


def test_core_key_never_empty():
    assert core_key("SAS") == "SAS"
    assert core_key(None) is None


def test_core_key_keeps_group_and_country_words():
    assert core_key("Sonepar France") == "SONEPAR FRANCE"
    assert core_key("Groupe SAFO") == "GROUPE SAFO"


def test_group_free_key_for_intercompany_detection():
    assert group_free_key("Groupe Page Up") == group_free_key("PAGE UP") == "PAGE UP"


def test_lookup_name_keeps_case_and_accents():
    assert lookup_name("ILUNION LAVANDERÍAS DE CANARIAS, S.A") == "ILUNION LAVANDERÍAS DE CANARIAS"
    assert lookup_name("J.F. Almeida, S.A.") == "J.F. Almeida"
    assert lookup_name("Arshad Corporation (Pvt) Ltd") == "Arshad Corporation"
    assert lookup_name("Wonderbox.fr") == "Wonderbox"
    assert lookup_name("SAS") == "SAS"
    assert lookup_name(None) is None


def test_integrator_keywords_narrow():
    assert integrator_keywords("ASIS ID TRAK S.L.") == ["TRAK"]
    assert integrator_keywords("Datalogic S.p.A.") == ["peer:DATALOGIC"]
    # End customers with generic words must not be flagged.
    for name in ["Id Verde", "ID LOGISTICS", "Safran Landing Systems", "SKIPPER TECHNOLOGIES", "SNCF RESEAU"]:
        assert integrator_keywords(name) == [], name


def test_name_notes():
    assert "名称含分支/地点后缀" in name_notes("TCS - GROUPE STERNE")
    assert "名称含括号限定" in name_notes("EDF (FR)")
    assert name_notes(None) == ["无客户名称"]
    assert name_notes("HERTA") == []


@pytest.mark.parametrize(
    "raw, iso",
    [("France", "FR"), ("france", "FR"), ("España", "ES"), ("UK", "GB"), ("Nerderland", "NL"), ("Mars", None), (None, None)],
)
def test_country_iso(raw, iso):
    assert country_iso(raw) == iso


@pytest.mark.parametrize(
    "a, b, unrelated",
    [
        ("Franprix - Groupe Casino", "IR2S", True),
        ("SECANETA", "JOSÉ ALBERO PUERTO", True),
        ("Sonepar France", "SONELOG", True),
        ("TCS - GROUPE STERNE", "TCS", False),
        ("Air France Industries Klm Engineering & Maintenance", "AIR FRANCE", False),
        ("S Transport", "BOVIS Transport", True),  # "TRANSPORT" alone is too generic
        ("Groupe avril", "AVRIL SERVICES", False),
        (None, "PRIMA", False),
    ],
)
def test_names_unrelated(a, b, unrelated):
    assert names_unrelated(a, b) is unrelated


@pytest.mark.parametrize(
    "domain,name,expected",
    [
        ("cerp-rrm.com", "CERP RHIN RHONE MEDITERRANEE", True),
        ("skippergroupe.com", "SKIPPER TECHNOLOGIES", True),
        ("grandsmoulinsdeparis.com", "GRANDS MOULINS DE PARIS", True),
        ("fr.thalesgroup.com", "THALES DMS FRANCE", True),
        ("cfigroupe.com", "COMPAGNIE FRANCAISE INFORMATIQUE", True),
        ("fft.fr", "FEDERATION FRANCAISE DE TENNIS", True),
        ("emilfrey.fr", "PBO", False),
        ("mrbricolage.fr", "MB LOG", False),
        ("france.com", "ACME FRANCE", False),
        (None, "ACME", False),
    ],
)
def test_domain_matches_name(domain, name, expected):
    assert domain_matches_name(domain, name) is expected
