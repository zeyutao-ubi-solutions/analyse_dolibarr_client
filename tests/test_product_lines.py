import pandas as pd

from analyse_dolibarr_client.lookalike import unit_product_lines
from analyse_dolibarr_client.product_lines import add_product_lines, customer_product_lines, tag_lines

CATALOG = pd.DataFrame(
    {
        "SKU_ID": [1, 2, 3, 4, 5, 6, 7],
        "SKU_NUMBER": ["P-1", "P-2", "P-3", "P-4", "P-5", "P-6", "P-7"],
        "SKU_NAME": [
            "UBI SmallTrack BLE",  # tagged GPSBLE
            "Tag RFID : UBITex 2058S",  # RFID by name, filed under "Traceurs"
            "UBI Solutions : GPS Tracker T27",  # untagged old tracker
            "M3 Mobile SL20+, 2D, BT (BLE), GPS, Android",  # terminal with BLE: not geoloc
            "Développement Software",
            "Lecteur fixe",  # RFID by subcategory
            "Kit RFID TC21 accessoire",  # tagged under Kit RFID TC21
        ],
    }
)
TAGS = pd.DataFrame(
    {
        "product_id": ["1", "7", "3"],
        "product_ref": ["P-1", "P-7", "WRONG-REF"],  # ref mismatch -> tag ignored
        "tag_path": ["UBI Solutions > GPSBLE > TAG", "Zebra > Kit RFID TC21", "UBI Solutions > GPSBLE"],
    }
)


def _lines():
    return pd.DataFrame(
        {
            "CUSTOMER_ID": ["a", "a", "b", "c", "c", "d", "e"],
            "PRODUCT_ID": [1, 2, 3, 4, 5, 6, 7],
            "ITEM_CATEGORY": [
                "Composants RFID & IoT", "Composants RFID & IoT", "Composants RFID & IoT", "Autres",
                "Projets & Intégration", "Composants RFID & IoT", "Autres",
            ],
            "ITEM_SUBCATEGORY_LV1": [
                "Traceurs et objets connectés", "Traceurs et objets connectés", "Traceurs et objets connectés",
                "Unknown", "Développement", "Lecteurs et antennes RFID", "Unknown",
            ],
            "ITEM_MANUFACTURER": ["UBI Solutions"] * 7,
            "amount_real": [100.0, 50.0, 30.0, 999.0, 10.0, 20.0, 5.0],
        }
    )


def test_tag_lines_require_matching_ref():
    assert tag_lines(TAGS, CATALOG) == {"1": "geoloc", "7": "rfid"}
    assert tag_lines(None) == {}


def test_add_product_lines_sources():
    out = add_product_lines(_lines(), CATALOG, TAGS)
    got = [(ln, src if isinstance(src, str) else None) for ln, src in zip(out["product_line"], out["product_line_source"])]
    assert got == [
        ("geoloc", "tag"),
        ("rfid", "name_rule"),
        ("geoloc", "name_rule"),
        ("other", None),
        ("other", None),
        ("rfid", "subcategory"),
        ("rfid", "tag"),
    ]


def test_customer_product_lines():
    res = customer_product_lines(add_product_lines(_lines(), CATALOG, TAGS))
    assert res.loc["a", "product_lines"] == "geoloc;rfid"
    assert res.loc["a", "geoloc_source"] == "tag"
    assert res.loc["b", "geoloc_source"] == "name_rule"
    assert res.loc["c", "product_lines"] == "" and pd.isna(res.loc["c", "geoloc_source"])
    assert res.loc["d", "amount_rfid_ht_eur"] == 20.0


def test_unit_product_lines_only_positive_units_count():
    members = pd.DataFrame(
        {"amount_geoloc_ht_eur": [0.0, 40.0], "amount_rfid_ht_eur": [10.0, 0.0], "geoloc_source": [None, "name_rule"]}
    )
    pos = unit_product_lines(members, True)
    assert pos["product_lines"] == "geoloc;rfid" and pos["positive_geoloc"] and pos["positive_rfid"]
    assert pos["geoloc_source"] == "name_rule"
    excl = unit_product_lines(members, False)
    assert not excl["positive_geoloc"] and not excl["positive_rfid"]


def test_ubi_cloud_is_its_own_line_and_combines_with_hardware():
    catalog = pd.DataFrame(
        {
            "SKU_ID": [1, 2, 3],
            "SKU_NUMBER": ["C-1", "C-2", "C-3"],
            "SKU_NAME": ["Abonnement UBI Cloud", "Abonnement Ubi Cloud IoT", "Tag RFID UHF 1275"],
        }
    )
    lines = pd.DataFrame(
        {
            "CUSTOMER_ID": ["x", "x", "y"],
            "PRODUCT_ID": [1, 3, 2],
            "ITEM_CATEGORY": ["Licences & Abonnements", "Composants RFID & IoT", "Licences & Abonnements"],
            "ITEM_SUBCATEGORY_LV1": ["Solutions UBI", "Balises/étiquettes RFID et cartes ID", "Solutions UBI"],
            "ITEM_MANUFACTURER": ["UBI Solutions"] * 3,
            "amount_real": [100.0, 40.0, 7.0],
        }
    )
    out = add_product_lines(lines, catalog, None)
    assert list(out["product_line"]) == ["ubi_cloud", "rfid", "ubi_cloud"]
    res = customer_product_lines(out)
    assert res.loc["x", "product_lines"] == "rfid;ubi_cloud"
    assert res.loc["x", "amount_ubi_cloud_ht_eur"] == 100.0
    assert res.loc["y", "product_lines"] == "ubi_cloud"
    unit = unit_product_lines(res.assign(geoloc_source=None), True)
    assert unit["positive_ubi_cloud"] and unit["positive_rfid"] and not unit["positive_geoloc"]
