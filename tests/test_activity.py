import numpy as np
import pandas as pd
import pytest

from analyse_dolibarr_client.activity import (
    PROBE_TEXT,
    ActivityModel,
    EmbeddingCache,
    HashEmbedder,
    clean_description,
    company_text,
    decide,
    description_language,
    employee_lower_bound,
    fit,
    priority,
    score_companies,
    thin_text,
    industry_features,
    normalize_industry,
    is_template,
    size_evidence,
    out_of_fold,
    apply_out_of_fold,
    text_key,
    train_from_labels,
    training_rows,
    training_weights,
)

SEGMENTS = pd.DataFrame({
    "segment_id": ["industrial_laundry", "hotels_hospitality", "research_labs"],
    "name_en": ["Industrial laundry services", "Hotels and hospitality", "Research institutes and laboratories"],
    "segment_priority": ["normal", "normal", "low"],
})

TEXTS = {
    "industrial_laundry": "industrial laundry washing linen hospitals hotels workwear rental",
    "hotels_hospitality": "hotel rooms guests resort hospitality booking stays",
    "research_labs": "research institute laboratory scientists experiments publications",
    "other": "law firm attorneys litigation contracts legal advice",
    "consulting": "consulting advisory strategy transformation clients",
}
EMB = HashEmbedder(256)


def _labels():
    rows = []
    for k, (y, txt) in enumerate(TEXTS.items()):
        for j in range(6):
            prospect = y not in ("other", "consulting")
            rows.append({"item_id": f"T{k}{j}", "split": "train", "clean": "True", "company_name": f"{y}-{j}",
                         "cons_label": "prospect" if prospect else y, "cons_segment": y if prospect else "",
                         "description": f"{txt} variant{j}", "linkedin_company_url": f"https://www.linkedin.com/company/{y}-{j}/"})
    rows.append({"item_id": "X1", "split": "train", "clean": "False", "company_name": "noisy", "cons_label": "other",
                 "cons_segment": "", "description": "whatever", "linkedin_company_url": None})
    rows.append({"item_id": "C1", "split": "eval_customers", "clean": "True", "company_name": "cust",
                 "cons_label": "prospect", "cons_segment": "industrial_laundry", "description": "customer laundry page",
                 "linkedin_company_url": "https://www.linkedin.com/company/industrial_laundry-0"})
    return pd.DataFrame(rows)


def _model():
    return train_from_labels(_labels(), EMB, EmbeddingCache(None, EMB.name), C=10)


def test_training_rows_keeps_clean_train_only_and_drops_evaluation_pages():
    rows = training_rows(_labels())
    assert set(rows["y"]) == set(TEXTS)
    assert not rows["item_id"].isin(["X1", "C1"]).any()
    assert "T00" not in set(rows["item_id"])  # same LinkedIn page as customer C1
    assert len(rows) == 29


def test_training_rows_drops_duplicate_text_and_customer_text():
    lab = _labels()
    lab.loc[1, "description"] = lab.loc[2, "description"]
    lab.loc[3, "description"] = "customer laundry page"
    rows = training_rows(lab)
    assert rows["description"].is_unique
    assert "customer laundry page" not in set(rows["description"])


def test_training_rows_rejects_prospect_without_segment():
    bad = _labels()
    bad.loc[5, "cons_segment"] = ""
    with pytest.raises(ValueError):
        training_rows(bad)


TEMPLATE = "SLI Blanchisserie is a laundry company based out of 12 rue X, Beauvoir-Sur-Mer, France."


def test_template_becomes_neutral_industry_sentence():
    assert clean_description(TEMPLATE) == "This organisation is a laundry company."
    assert "France" not in company_text(TEMPLATE) and "SLI" not in company_text(TEMPLATE)
    assert thin_text(TEMPLATE) and is_template(TEMPLATE)
    assert clean_description("S.A. Dupont is a company based out of 1 rue X, Lyon, France.") == "This organisation is a company."
    assert is_template("BUCKLEY LAMB LIMITED is a hospital & health care company.")
    assert not is_template("We wash linen for hospitals. Today Acme is a growing company.")
    long = "We wash linen for hospitals and hotels with forty trucks across the whole region every single day of the week, including weekends and public holidays"
    assert clean_description(long) == long and not thin_text(long)


def test_company_text_prefix_and_truncation():
    assert company_text("x" * 2000) == "passage: " + "x" * 1500
    assert company_text(None) == "passage: "


def test_description_language():
    assert description_language("Nous sommes une entreprise de la blanchisserie et des services pour les hôpitaux") == "fr"
    assert description_language("We are the leading provider of linen services for the hospitals and hotels in our region") == "en"
    assert description_language("Hotel") == "unknown"


def test_training_weights_equalise_prospect_share_across_languages():
    y = np.array(["seg"] * 8 + ["other"] * 2 + ["seg"] * 5 + ["other"] * 5)
    lang = np.array(["fr"] * 10 + ["en"] * 10)
    import analyse_dolibarr_client.activity as act
    old, act.MIN_LANGUAGE_ROWS = act.MIN_LANGUAGE_ROWS, 1
    try:
        w = training_weights(y, lang)
    finally:
        act.MIN_LANGUAGE_ROWS = old
    isp = y == "seg"
    share = {lg: w[(lang == lg) & isp].sum() / w[lang == lg].sum() for lg in ("fr", "en")}
    assert share["fr"] == pytest.approx(share["en"], abs=0.02)


@pytest.mark.parametrize("count,rng,expected", [
    (None, "11-50", (11, "range")),
    ("17.0", "51-200", (51, "range")),
    (None, "1,001-5,000", (1001, "range")),
    (None, "10,001+", (10001, "range")),
    ("17.0", None, (17, "count")),
    ("1,234", None, (1234, "count")),
    ("51_200", None, (51, "range")),
    ("201_plus", None, (201, "range")),
    (None, "{'start': 1001, 'end': 5000}", (1001, "range")),
    (None, None, (None, "unknown")),
])
def test_employee_lower_bound(count, rng, expected):
    assert employee_lower_bound(count, rng) == expected


@pytest.mark.parametrize("count,rng,expected", [
    ("17.0", "11-50", (11, 17)),
    (None, "51-200", (51, None)),
    ("51_200", None, (51, None)),
    ("6", None, (None, 6)),
    (None, None, (None, None)),
])
def test_size_evidence(count, rng, expected):
    assert size_evidence(count, rng) == expected


def test_priority_rules():
    prio = dict(zip(SEGMENTS.segment_id, SEGMENTS.segment_priority))
    P = lambda *a: priority(*a)[0]
    assert P("prospect", "industrial_laundry", prio, 11, None) == "low"
    assert P("prospect", "industrial_laundry", prio, 11, 30) == "low"
    assert P("prospect", "industrial_laundry", prio, 11, 106) == "normal"  # 106 members: the declared range is stale
    assert P("prospect", "research_labs", prio, 5000, None) == "low"
    assert P("consulting", "research_labs", prio, 5000, None) == "normal"  # segment rule: prospects only
    assert P("template_only", "research_labs", prio, 5000, None) == "normal"
    assert P("prospect", "industrial_laundry", prio, 51, None) == "normal"
    assert P("prospect", "industrial_laundry", prio, None, 3) == "unknown_size"  # members are a lower bound
    assert P("prospect", "industrial_laundry", prio, None, 80) == "normal"
    assert P("prospect", "industrial_laundry", prio, None, None) == "unknown_size"
    assert " / " in priority("prospect", "industrial_laundry", prio, 11, None)[1]  # Chinese / French


def test_decide_label_follows_fit_threshold():
    classes = np.array(["industrial_laundry", "hotels_hospitality", "other", "consulting"])
    P = np.array([[0.25, 0.20, 0.30, 0.25], [0.30, 0.25, 0.30, 0.15]])
    d = decide(P, classes, threshold=0.5)
    assert list(d["label"]) == ["other", "prospect"]
    assert list(decide(P, classes)["label"]) == ["other", "other"]  # default threshold 0.65
    assert d["segment_prob"][1] == pytest.approx(0.30 / 0.55)


def test_softmax_matches_sklearn():
    from sklearn.linear_model import LogisticRegression
    rows = training_rows(_labels())
    X = EMB.embed([company_text(d) for d in rows["description"]])
    m = fit(X, rows["y"], rows["company_name"], EMB.embed([PROBE_TEXT])[0], C=10)
    lr = LogisticRegression(C=10, max_iter=4000, class_weight="balanced").fit(X, rows["y"])
    np.testing.assert_allclose(m.predict_proba(X), lr.predict_proba(X), atol=1e-5)


def test_fit_refuses_binary_problems():
    with pytest.raises(ValueError):
        fit(np.eye(4), ["a", "b", "a", "b"], list("wxyz"), np.zeros(4))


def test_score_companies_end_to_end(tmp_path):
    _model().save(tmp_path)
    model = ActivityModel.load(tmp_path)
    companies = pd.DataFrame({
        "description": [TEXTS["industrial_laundry"], TEXTS["other"], TEXTS["research_labs"], TEXTS["hotels_hospitality"]],
        "employee_count_range": ["51-200", "51-200", "1001-5000", None],
        "employee_count": [None, None, None, "4"],
        "hq_country": ["FR", "US", "DE", "ES"],
    })
    s = score_companies(model, companies, EMB, SEGMENTS)
    assert list(s["label"][:3]) == ["prospect", "other", "prospect"]
    assert s.loc[0, "segment"] == "industrial_laundry" and s.loc[0, "segment_name_en"] == "Industrial laundry services"
    assert s.loc[0, "fit"] > s.loc[1, "fit"]
    assert s.loc[0, "similar_training_companies"].startswith("industrial_laundry-")
    assert list(s["priority"]) == ["normal", "normal", "low", "unknown_size"]
    assert bool(s.loc[3, "thin_text"])


def test_similar_companies_skip_an_exact_copy_of_the_text():
    model = _model()
    s = score_companies(model, pd.DataFrame({"description": ["industrial laundry washing linen hospitals hotels workwear rental variant1"]}), EMB, SEGMENTS)
    assert "industrial_laundry-1 " not in s.loc[0, "similar_training_companies"] + " "


def test_country_and_template_address_do_not_change_the_score():
    model = _model()
    a = pd.DataFrame({"description": ["Hotel Lumière is a hospitality company based out of 1 rue X, Lyon, France."], "hq_country": ["FR"]})
    b = pd.DataFrame({"description": ["Hotel Lumière is a hospitality company based out of 9 Main St, Austin, United States."], "hq_country": ["US"]})
    pd.testing.assert_frame_equal(score_companies(model, a, EMB, SEGMENTS), score_companies(model, b, EMB, SEGMENTS))


def test_score_refuses_another_embedder():
    model = _model()
    with pytest.raises(ValueError):
        score_companies(model, pd.DataFrame({"description": ["x"]}), HashEmbedder(128), SEGMENTS)


def test_embedding_cache_roundtrip(tmp_path):
    path = tmp_path / "c.npz"
    c = EmbeddingCache(path, EMB.name)
    v = c.get(["passage: a", "passage: b"], EMB)
    again = EmbeddingCache(path, EMB.name).get(["passage: b", "passage: a"], None)
    np.testing.assert_allclose(again, v[::-1])
    with pytest.raises(ValueError):
        EmbeddingCache(path, "other-model")


def test_template_page_takes_segment_candidates_from_linkedin_industry():
    model = _model()
    segs = SEGMENTS.assign(linkedin_industries=["Laundry and Drycleaning Services; Textile Manufacturing", "Hospitality", ""])
    comp = pd.DataFrame({"description": [
        "SLI is a laundry and drycleaning services company based out of 1 rue X, Lyon, France.",
        "Foo is a textiles company based out of 2 Main St, Leeds, United Kingdom.",
        "Bar is a company based out of 3 Calle Y, Madrid, Spain.",
        TEXTS["other"]]})
    s = score_companies(model, comp, EMB, segs)
    assert list(s["label"][:3]) == ["template_only"] * 3
    assert list(s["segment"][:3]) == ["industrial_laundry", "industrial_laundry", ""]  # "textiles" is an old alias
    assert pd.isna(s.loc[2, "fit"]) and pd.isna(s.loc[0, "segment_prob"])
    assert (s["similar_training_companies"][:4] == "").all()


def test_training_rows_drop_template_pages():
    lab = _labels()
    lab.loc[0, "description"] = TEMPLATE
    assert TEMPLATE not in set(training_rows(lab)["description"])


def test_out_of_fold_replaces_scores_of_trained_texts():
    lab = _labels()
    cache = EmbeddingCache(None, EMB.name)
    oof = out_of_fold(lab, EMB, cache, C=10, folds=3)
    rows = training_rows(lab)
    assert len(oof) == len(rows) and set(oof["text_key"]) == set(rows["description"].map(text_key))
    model = train_from_labels(lab, EMB, cache, C=10)
    comp = pd.DataFrame({"description": [rows.loc[0, "description"], "brand new hotel resort guests"]})
    s = score_companies(model, comp, EMB, SEGMENTS)
    t = apply_out_of_fold(comp, s, oof, SEGMENTS)
    assert list(t["score_source"]) == ["out_of_fold", "model"]
    assert t.loc[0, "fit"] == pytest.approx(oof.set_index("text_key").loc[text_key(rows.loc[0, "description"]), "fit"])
    assert t.loc[1, "fit"] == s.loc[1, "fit"]


def test_normalize_industry_maps_old_linkedin_names():
    assert normalize_industry(" Textiles ") == "textile manufacturing"
    assert normalize_industry("Hospitality") == "hospitality"
    assert normalize_industry(None) == ""


def test_industry_features_one_hot():
    M = industry_features(["Hospitality", "textiles", None, "Unknown"], ["hospitality", "textile manufacturing"], weight=0.3)
    np.testing.assert_allclose(M, [[0.3, 0], [0, 0.3], [0, 0], [0, 0]])


def _labels_with_industry():
    lab = _labels()
    ind = {"industrial_laundry": "Laundry and Drycleaning Services", "hotels_hospitality": "Hospitality",
           "research_labs": "Research Services", "other": "Law Practice", "consulting": "Business Consulting"}
    lab["industry"] = [ind.get(n.rsplit("-", 1)[0]) for n in lab["company_name"]]
    return lab


def test_industry_feature_is_learned_and_optional(tmp_path):
    lab = _labels_with_industry()
    model = train_from_labels(lab, EMB, EmbeddingCache(None, EMB.name), C=10)
    assert "hospitality" in set(model.industry_vocab) and model.coef.shape[1] == 256 + len(model.industry_vocab)
    model.save(tmp_path)
    model = ActivityModel.load(tmp_path)
    text = "a place offering beds and breakfast"
    with_ind = score_companies(model, pd.DataFrame({"description": [text], "industry": ["Hospitality"]}), EMB, SEGMENTS)
    without = score_companies(model, pd.DataFrame({"description": [text]}), EMB, SEGMENTS)
    assert with_ind.loc[0, "segment"] == "hotels_hospitality"
    assert with_ind.loc[0, "fit"] != without.loc[0, "fit"]  # scored without an industry too


def test_out_of_fold_uses_industries():
    lab = _labels_with_industry()
    oof = out_of_fold(lab, EMB, EmbeddingCache(None, EMB.name), C=10, folds=3)
    assert oof["fit"].between(0, 1).all() and len(oof) == len(training_rows(lab))


def test_sales_label_and_category():
    model = _model()
    segs = SEGMENTS.assign(category=["Linen, textiles and workwear", "Linen, textiles and workwear", "Healthcare and public services"])
    comp = pd.DataFrame({"description": [TEXTS["industrial_laundry"], TEXTS["other"], TEXTS["consulting"], TEMPLATE]})
    s = score_companies(model, comp, EMB, segs)
    assert list(s["sales_label"]) == ["prospect", "not_target", "not_target", "template_only"]
    assert s.loc[0, "category"] == "Linen, textiles and workwear" and s.loc[1, "category"] is None


def test_insufficient_info_is_folded_into_other():
    lab = _labels()
    lab.loc[lab["cons_label"].eq("other"), "cons_label"] = "insufficient_info"
    assert "insufficient_info" not in set(training_rows(lab)["y"])
