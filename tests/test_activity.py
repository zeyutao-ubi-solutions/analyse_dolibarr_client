import pandas as pd
import pytest

from analyse_dolibarr_client.activity import (
    ActivityModel,
    HashEmbedder,
    company_text,
    employee_lower_bound,
    fit,
    priority,
    score_companies,
    training_rows,
)

SEGMENTS = pd.DataFrame({
    "segment_id": ["industrial_laundry", "hotels_hospitality", "research_labs"],
    "name_zh": ["工业洗衣房", "酒店与住宿业", "研究机构"],
    "segment_priority": ["normal", "normal", "low"],
})

TEXTS = {
    "industrial_laundry": "industrial laundry washing linen hospitals hotels workwear rental",
    "hotels_hospitality": "hotel rooms guests resort hospitality booking stays",
    "research_labs": "research institute laboratory scientists experiments publications",
    "other": "law firm attorneys litigation contracts legal advice",
    "consulting": "consulting advisory strategy transformation clients",
}


def _labels():
    rows = []
    for k, (y, txt) in enumerate(TEXTS.items()):
        for j in range(6):
            prospect = y not in ("other", "consulting")
            rows.append({"item_id": f"T{k}{j}", "split": "train", "clean": "True", "company_name": f"{y}-{j}",
                         "cons_label": "prospect" if prospect else y, "cons_segment": y if prospect else "",
                         "description": f"{txt} variant{j}"})
    rows.append({"item_id": "X1", "split": "train", "clean": "False", "company_name": "noisy", "cons_label": "other",
                 "cons_segment": "", "description": "whatever"})
    rows.append({"item_id": "C1", "split": "eval_customers", "clean": "True", "company_name": "cust",
                 "cons_label": "prospect", "cons_segment": "industrial_laundry", "description": TEXTS["industrial_laundry"]})
    return pd.DataFrame(rows)


def _model():
    rows = training_rows(_labels())
    emb = HashEmbedder(256)
    X = emb.embed([company_text(d) for d in rows["description"]])
    return fit(X, rows["y"], rows["company_name"], C=10, meta={"embedding_model": emb.name}), emb


def test_training_rows_keeps_clean_train_only_and_flattens_target():
    rows = training_rows(_labels())
    assert len(rows) == 30
    assert set(rows["y"]) == set(TEXTS)
    assert not rows["item_id"].isin(["X1", "C1"]).any()


def test_training_rows_rejects_prospect_without_segment():
    bad = _labels()
    bad.loc[0, "cons_segment"] = ""
    with pytest.raises(ValueError):
        training_rows(bad)


def test_company_text_matches_labelling_input():
    assert company_text("x" * 2000) == "passage: " + "x" * 1500
    assert company_text(None) == "passage: "


@pytest.mark.parametrize("count,rng,expected", [
    (None, "11-50", (11, "range")),
    ("17.0", "51-200", (51, "range")),
    ("17.0", None, (17, "count")),
    ("51_200", None, (51, "range")),
    ("201_plus", None, (201, "range")),
    (None, "{'start': 1001, 'end': 5000}", (1001, "range")),
    (None, "10001+", (10001, "range")),
    (None, None, (None, "unknown")),
])
def test_employee_lower_bound(count, rng, expected):
    assert employee_lower_bound(count, rng) == expected


def test_priority_is_low_for_small_or_low_segment_and_never_excludes():
    prio = dict(zip(SEGMENTS.segment_id, SEGMENTS.segment_priority))
    assert priority("industrial_laundry", prio, 20, "range")[0] == "low"
    assert priority("research_labs", prio, 5000, "range")[0] == "low"
    assert priority("industrial_laundry", prio, 51, "range")[0] == "normal"
    assert priority("industrial_laundry", prio, None, "unknown")[0] == "unknown_size"


def test_score_companies_end_to_end(tmp_path):
    model, emb = _model()
    model.save(tmp_path)
    model = ActivityModel.load(tmp_path)
    companies = pd.DataFrame({
        "description": [TEXTS["industrial_laundry"], TEXTS["other"], TEXTS["research_labs"], TEXTS["hotels_hospitality"]],
        "employee_count_range": ["51-200", "51-200", "1001-5000", None],
        "hq_country": ["FR", "US", "DE", "ES"],
    })
    s = score_companies(model, companies, emb, SEGMENTS)
    assert list(s["label"][:3]) == ["prospect", "other", "prospect"]
    assert s.loc[0, "segment"] == "industrial_laundry" and s.loc[0, "segment_name_zh"] == "工业洗衣房"
    assert s.loc[0, "fit"] > s.loc[1, "fit"]
    assert s.loc[0, "similar_training_companies"].startswith("industrial_laundry-")
    assert list(s["priority"]) == ["normal", "normal", "low", "unknown_size"]
    assert bool(s.loc[3, "thin_text"])  # fewer than 20 words


def test_empty_description_is_flagged_thin():
    model, emb = _model()
    s = score_companies(model, pd.DataFrame({"description": [None]}), emb, SEGMENTS)
    assert bool(s.loc[0, "thin_text"])


def test_country_does_not_change_the_score():
    model, emb = _model()
    a = pd.DataFrame({"description": [TEXTS["hotels_hospitality"]], "hq_country": ["FR"]})
    b = a.assign(hq_country="PL")
    pd.testing.assert_frame_equal(score_companies(model, a, emb, SEGMENTS), score_companies(model, b, emb, SEGMENTS))


def test_score_refuses_vectors_from_another_embedding_model():
    model, _ = _model()
    with pytest.raises(ValueError):
        score_companies(model, pd.DataFrame({"description": ["x"]}), HashEmbedder(128), SEGMENTS)
