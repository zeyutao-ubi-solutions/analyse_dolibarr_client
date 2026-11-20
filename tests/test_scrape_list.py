import pandas as pd

from analyse_dolibarr_client.lookalike import add_country_weights, effective_sample_size
from analyse_dolibarr_client.scrape_list import COLUMNS, build_list, sample_unlabeled


def _units():
    rows = (
        [("positive", "FR")] * 10 + [("unlabeled", "FR")] * 30
        + [("positive", "ES")] * 2 + [("unlabeled", "ES")] * 50
        + [("unlabeled", "DE")] * 40 + [("excluded", "FR")] * 3
    )
    u = pd.DataFrame(
        [
            {
                "unit_id": f"u{i}.fr", "label": lab, "country_code": c, "web_domain": f"u{i}.fr", "has_domain": True,
                "lookup_name": f"CO {i}", "customer_ids": None, "third_party_ids": str(i),
            }
            for i, (lab, c) in enumerate(rows)
        ]
    )
    return add_country_weights(u, min_positives=2)


def test_sampling_keeps_reference_and_balances_others():
    s = sample_unlabeled(_units(), oversample=0.5)
    main = s[s["batch"] == "main"]
    assert (main["country_bucket"] == "FR").sum() == 30  # all of the reference bucket
    assert (main["country_bucket"] == "ES").sum() == 6  # 30/10 unlabeled per positive x 2 positives
    assert (main["country_bucket"] == "other").sum() == 0  # DE has no positives
    assert (s[(s["batch"] == "reserve")]["country_bucket"] == "ES").sum() == 3
    assert sample_unlabeled(_units(), 0.5)["unit_id"].tolist() == s["unit_id"].tolist()  # deterministic


def test_sampled_main_batch_has_flat_weights():
    u = _units()
    s = sample_unlabeled(u)
    chosen = set(s.loc[s["batch"] == "main", "unit_id"]) | set(u.loc[u["label"] == "positive", "unit_id"])
    sub = u[u["unit_id"].isin(chosen) & u["label"].isin(["positive", "unlabeled"])].drop(columns=["country_bucket", "sample_weight"])
    w = add_country_weights(sub, min_positives=2)
    unl = w[w["label"] == "unlabeled"]
    assert abs(effective_sample_size(unl["sample_weight"]) - len(unl)) < 1e-6


def test_list_has_no_label_and_all_positives():
    u = _units()
    tp = pd.DataFrame({"THIRD_PARTY_ID": list(range(len(u))), "THIRD_PARTY_NAME": [f"Co {i} SAS" for i in range(len(u))],
                       "TOWN": "Paris", "SIREN": None})
    companies = pd.DataFrame(columns=["customer_id", "lookup_name", "order_lookup_name", "town", "siren"])
    lst = build_list(u, companies, tp)
    assert list(lst.columns) == COLUMNS
    assert "label" not in lst.columns
    assert set(u.loc[u["label"] == "positive", "unit_id"]) <= set(lst["unit_id"])
    assert not set(u.loc[u["label"] == "excluded", "unit_id"]) & set(lst["unit_id"])
    assert lst["town"].eq("Paris").all()
