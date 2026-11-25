from pathlib import Path

import pandas as pd
import pytest

from analyse_dolibarr_client.linkedin_scrape import (
    ACTOR_ID,
    apply_review,
    _quota_error,
    classify,
    domain_brand,
    is_rejected_page,
    main,
    normalize_domain,
    reclassify,
    registrable_domain,
    run_record,
    save_progress,
    scrape,
    search_sequence,
    select_pilot,
    usage_from_run,
    write_review_queue,
)


TOKEN = "SUPERSECRET_TOKEN_XYZ"


def _item(**kw):
    country = kw.pop("hq_country", "FR")
    city = kw.pop("hq_city", "Paris")
    base = {
        "linkedinUrl": "https://www.linkedin.com/company/acme",
        "universalName": "acme",
        "name": "Acme",
        "website": "https://www.acme.com",
        "description": "We make things.",
        "tagline": "Things",
        "specialities": ["IoT", "RFID"],
        "industries": ["Logistics"],
        "employeeCount": 80,
        "employeeCountRange": {"start": 51, "end": 200},
        "followerCount": 1000,
        "companyType": "Privately Held",
        "foundedOn": {"year": 2001},
        "locations": [{
            "headquarter": True,
            "city": city,
            "country": country,
            "parsed": {"city": city, "countryCode": country},
        }],
    }
    base.update(kw)
    return base


def _units(*rows):
    return pd.DataFrame(rows)


class FakeClient:
    def __init__(self, by_search=None, by_url=None, fail_times=0):
        self.by_search = {str(k).lower(): v for k, v in (by_search or {}).items()}
        self.by_url = by_url or {}
        self.fail_times = fail_times
        self.calls = []
        self.datasets = {}

    def actor(self, name):
        assert name == ACTOR_ID
        return self

    def call(self, run_input=None, **_kw):
        self.calls.append(run_input)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise TimeoutError("network down")
        items = []
        if run_input and run_input.get("searches"):
            for search in run_input["searches"]:
                raw = self.by_search.get(str(search).lower())
                if raw is None:
                    continue
                rows = raw if isinstance(raw, list) else [raw]
                for item in rows:
                    row = dict(item)
                    row.setdefault("originalQuery", {"search": search})
                    items.append(row)
        if run_input and run_input.get("companies"):
            for url in run_input["companies"]:
                if url in self.by_url:
                    items.append(dict(self.by_url[url]))
        run_id = f"run{len(self.calls)}"
        self.datasets[f"ds{run_id}"] = items
        return {
            "id": run_id,
            "defaultDatasetId": f"ds{run_id}",
            "status": "SUCCEEDED",
            "usageTotalUsd": 0.01 * max(len(items), 1),
            "chargedEventCounts": {"company-scraped": len(items)},
        }

    def dataset(self, dataset_id):
        self._current_ds = dataset_id
        return self

    def iterate_items(self):
        return iter(self.datasets.get(getattr(self, "_current_ds", ""), []))


def test_run_record_and_ppe_usage():
    rec = run_record({
        "id": "r1", "defaultDatasetId": "d1", "status": "SUCCEEDED",
        "usageTotalUsd": 0.0,
        "chargedEventCounts": {"linkedin-company-scrape": 20},
        "event_usage": {"linkedin-company-scrape": {"event_total_usd": 0.08, "event_title": "Company"}},
    })
    usd, raw = usage_from_run(rec)
    assert rec["status"] == "SUCCEEDED"
    assert usd == 0.08
    assert "linkedin-company-scrape" in raw


def test_normalize_domain_strips_www_and_scheme():
    assert normalize_domain("https://www.Acme.com/about") == "acme.com"
    assert normalize_domain("acme.com") == "acme.com"


def test_registrable_domain_strips_subdomain():
    assert registrable_domain("https://fr.scc.com") == "scc.com"
    assert registrable_domain("www.acme.co.uk") == "acme.co.uk"
    assert domain_brand("aroihoteles.com") == "aroihoteles"


def test_search_sequence_starts_with_domain_brand():
    seq = search_sequence({
        "search_name": "LA COLINA", "alt_search_names": ["Colina"], "web_domain": "aroihoteles.com",
    })
    assert seq[0] == "aroihoteles"


def test_domain_match_uses_etld_and_allows_unrelated_name():
    unit = {"search_name": "Wrong Name", "web_domain": "scc.com", "country_code": "DE", "town": None}
    item = _item(name="Something Else", website="https://fr.scc.com")
    d = classify(unit, [item], has_remaining=False)
    assert d.match_status == "matched"
    assert d.match_method == "domain"
    assert d.group_page is True


def test_other_domain_with_same_name_is_ambiguous():
    unit = {"search_name": "Acme", "web_domain": "acme.com", "country_code": "FR", "town": None}
    item = _item(name="Acme", website="https://wrong.example", hq_country="FR")
    d = classify(unit, [item], has_remaining=True)
    assert d.match_status == "ambiguous"
    assert d.item is None


def test_name_country_requires_exact_core_key_and_country():
    unit = {"search_name": "Acme SAS", "web_domain": None, "country_code": "FR", "town": "Paris"}
    item = _item(name="ACME", website=None, hq_country="FR", hq_city="Paris")
    d = classify(unit, [item], has_remaining=False)
    assert d.match_status == "matched"
    assert d.match_method == "name_country"


def test_partial_name_is_ambiguous_not_matched():
    unit = {"search_name": "Acme", "web_domain": None, "country_code": "FR", "town": None}
    item = _item(name="Acme France Logistics", website=None, hq_country="FR")
    d = classify(unit, [item], has_remaining=False)
    assert d.match_status == "ambiguous"


def test_empty_country_never_auto_matched():
    unit = {"search_name": "Acme", "web_domain": None, "country_code": None, "town": None}
    item = _item(name="Acme", website=None, hq_country="FR")
    d = classify(unit, [item], has_remaining=False)
    assert d.match_status == "ambiguous"


def test_country_mismatch_exact_name_is_ambiguous():
    unit = {"search_name": "Acme", "web_domain": None, "country_code": "FR", "town": None}
    item = _item(name="Acme", website=None, hq_country="US")
    d = classify(unit, [item], has_remaining=False)
    assert d.match_status == "ambiguous"


def test_ambiguous_when_two_exact_name_country_hits():
    unit = {"search_name": "Acme", "web_domain": None, "country_code": "FR", "town": None}
    a = _item(name="Acme", linkedinUrl="https://www.linkedin.com/company/acme-a", website=None, hq_country="FR")
    b = _item(name="Acme", linkedinUrl="https://www.linkedin.com/company/acme-b", website=None, hq_country="FR")
    d = classify(unit, [a, b], has_remaining=False)
    assert d.match_status == "ambiguous"
    assert len(d.candidates) == 2
    assert d.item is None


def test_rejects_union_page():
    item = _item(name="SYNDICAT CGT HOPITAL DE RAMBOUILLET", website=None, hq_country="FR")
    assert is_rejected_page(item)
    unit = {"search_name": "CH RAMBOUILLET", "web_domain": None, "country_code": "FR", "town": "Rambouillet"}
    d = classify(unit, [item], has_remaining=False)
    assert d.match_status == "not_found"


def test_keeps_searching_when_wrong_company_and_alts_remain():
    unit = {"search_name": "Acme", "web_domain": "acme.com", "country_code": "FR", "town": None}
    item = _item(name="Holding SA", website="https://wrong.example", hq_country="DE")
    d = classify(unit, [item], has_remaining=True)
    assert d.needs_more is True


def test_scrape_domain_and_writes_contract_row(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
        "web_domain": "acme.com", "country_code": "FR", "town": "Paris", "has_domain": True,
    })
    client = FakeClient(by_search={"Acme": _item()})
    out = scrape(units, tmp_path, client=client, retries=0, check_stops=False)
    assert list(out["match_status"]) == ["matched"]
    assert list(out["match_method"]) == ["domain"]
    assert out.loc[0, "specialties"] == "IoT;RFID"
    assert out.loc[0, "employee_count_range"] == "51-200"
    assert out.loc[0, "query_used"]
    assert (tmp_path / "raw" / "run1.jsonl").exists()
    assert (tmp_path / "progress.csv").exists()
    assert (tmp_path / "runs.csv").exists()


def test_alt_search_recovers_domain(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Holding", "alt_search_names": "Acme",
        "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True,
    })
    client = FakeClient(by_search={
        "Holding": _item(name="Holding SA", website="https://holding.example",
                         linkedinUrl="https://www.linkedin.com/company/holding"),
        "Acme": _item(),
    })
    out = scrape(units, tmp_path, client=client, retries=0, batch_size=1, check_stops=False)
    assert list(out["match_method"]) == ["domain"]
    assert client.calls[0].get("searches") == ["acme"]


def test_resume_does_not_research_matched_with_unused_alts(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Acme",
        "alt_search_names": "Acme SA",
        "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True,
    })
    client = FakeClient(by_search={"Acme": _item()})
    scrape(units, tmp_path, client=client, retries=0, check_stops=False)
    n_calls = len(client.calls)
    assert n_calls >= 1
    client.by_search = {"Acme SA": _item(name="Acme SA", website="https://other.example")}
    scrape(units, tmp_path, client=client, retries=0, check_stops=False)
    assert len(client.calls) == n_calls


def test_save_progress_keeps_other_units(tmp_path):
    path = tmp_path / "progress.csv"
    save_progress(path, {
        "a.com": {
            "unit_id": "a.com", "status": "matched", "attempts": 1, "last_error": None,
            "match_method": "domain", "search_used": "a", "tried_searches": "a",
            "run_ids": "r1", "updated_at": "2026-11-20T00:00:00Z",
        },
    })
    save_progress(path, {
        "b.com": {
            "unit_id": "b.com", "status": "pending", "attempts": 0, "last_error": None,
            "match_method": None, "search_used": None, "tried_searches": "",
            "run_ids": "", "updated_at": "2026-11-23T00:00:00Z",
        },
    })
    out = pd.read_csv(path, dtype=str)
    assert set(out["unit_id"]) == {"a.com", "b.com"}
    assert list(out.loc[out["unit_id"] == "a.com", "status"]) == ["matched"]


def test_resume_skips_completed(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
        "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True,
    })
    client = FakeClient(by_search={"Acme": _item()})
    scrape(units, tmp_path, client=client, retries=0, check_stops=False)
    n_calls = len(client.calls)
    client.by_search = {}
    client.fail_times = 99
    scrape(units, tmp_path, client=client, retries=0, check_stops=False)
    assert len(client.calls) == n_calls


def test_token_never_written(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
        "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True,
    })
    client = FakeClient(by_search={"Acme": _item()})
    scrape(units, tmp_path, client=client, retries=0, check_stops=False)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert TOKEN not in text, path


def test_quota_error_detects_free_plan_monthly_usage():
    assert _quota_error(
        "You've used the $5.00 of monthly usage included in the Free plan, "
        "so Actor runs and other Apify services are blocked"
    )
    assert not _quota_error("actor timeout")


def test_actor_failure_marks_error(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
        "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True,
    })
    client = FakeClient(fail_times=3)
    out = scrape(units, tmp_path, client=client, retries=1, check_stops=False)
    assert list(out["match_status"]) == ["error"]
    progress = pd.read_csv(tmp_path / "progress.csv")
    assert TOKEN not in progress.to_csv()


def test_select_pilot_mixes_domain_and_country():
    rows = []
    for i in range(30):
        rows.append({
            "unit_id": f"d{i}.com", "batch": "main", "search_name": f"D{i}",
            "alt_search_names": None, "web_domain": f"d{i}.com",
            "country_code": "ES" if i < 10 else "FR", "town": None, "has_domain": True,
        })
    for i in range(30):
        rows.append({
            "unit_id": f"tp:{i}", "batch": "main", "search_name": f"N{i}",
            "alt_search_names": None, "web_domain": None,
            "country_code": "DE" if i < 10 else "FR", "town": None, "has_domain": False,
        })
    rows.append({
        "unit_id": "reserve.com", "batch": "reserve", "search_name": "R",
        "alt_search_names": None, "web_domain": "reserve.com",
        "country_code": "IT", "town": None, "has_domain": True,
    })
    picked = select_pilot(pd.DataFrame(rows), 20)
    assert len(picked) == 20
    assert (picked["batch"] == "main").all()
    n_with_domain = int(picked["has_domain"].astype(bool).sum())
    assert n_with_domain in {10, 11}
    assert int((~picked["has_domain"].astype(bool)).sum()) == 20 - n_with_domain
    assert int((picked["country_code"] != "FR").sum()) >= 5


def test_review_queue_written_for_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({
        "unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
        "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True,
    })
    client = FakeClient(by_search={"Acme": _item(name="Acme", website="https://other.io", hq_country="FR")})
    scrape(units, tmp_path, client=client, retries=0, check_stops=False, review_path=tmp_path / "q.csv")
    q = pd.read_csv(tmp_path / "q.csv", dtype={"unit_id": str})
    assert list(q["unit_id"]) == ["acme.com"]
    assert "other.io" in str(q.loc[0, "candidate_website"])


def test_cli_refuses_full_run_without_flag():
    with pytest.raises(SystemExit):
        main([])


def test_module_does_not_read_labels():
    src = Path("src/analyse_dolibarr_client/linkedin_scrape.py").read_text()
    assert "lookalike_units" not in src
    assert '["label"]' not in src
    assert "lookalike_units.csv" not in src


def test_gouv_fr_ministries_are_separate_domains():
    assert registrable_domain("https://www.interieur.gouv.fr") == "interieur.gouv.fr"
    assert domain_brand("finances.gouv.fr") == "finances"
    unit = {"search_name": "Ministere de l'Interieur", "web_domain": "interieur.gouv.fr", "country_code": "FR", "town": None}
    item = _item(name="Cybermalveillance.gouv.fr", website="https://www.cybermalveillance.gouv.fr")
    assert classify(unit, [item], has_remaining=False).match_status == "not_found"


def test_mailbox_domain_is_not_company_evidence():
    unit = {"search_name": "Tessuti Zampagna", "web_domain": "inwind.it", "country_code": "IT", "town": None}
    item = _item(name="Inwind", website="https://www.inwind.it", hq_country="IT")
    assert classify(unit, [item], has_remaining=False).match_status == "not_found"
    assert domain_brand("inwind.it") is None


def test_review_queue_drops_rows_of_units_now_resolved(tmp_path):
    q = tmp_path / "q.csv"
    write_review_queue(q, [{"unit_id": "a.com", "candidate_url": "u1"}, {"unit_id": "b.com", "candidate_url": "u2"}])
    write_review_queue(q, [], {"a.com"})
    assert list(pd.read_csv(q, dtype=str)["unit_id"]) == ["b.com"]


def test_reclassify_updates_only_changed_units(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units(
        {"unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
         "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True},
        {"unit_id": "beta.com", "batch": "main", "search_name": "Beta", "alt_search_names": None,
         "web_domain": "beta.com", "country_code": "FR", "town": None, "has_domain": True},
    )
    client = FakeClient(by_search={
        "Acme": _item(),
        "Beta": _item(name="Beta", website="https://other.io",
                      linkedinUrl="https://www.linkedin.com/company/beta", universalName="beta"),
    })
    res, q = tmp_path / "res.csv", tmp_path / "q.csv"
    scrape(units, tmp_path, client=client, retries=0, check_stops=False, results_path=res, review_path=q)
    assert set(pd.read_csv(q, dtype=str)["unit_id"]) == {"beta.com"}
    df = pd.read_csv(res, dtype=str)
    df.loc[df["unit_id"] == "beta.com", ["match_status", "linkedin_url"]] = ["matched", "https://x"]
    df.to_csv(res, index=False, encoding="utf-8-sig")
    stamp = df.loc[df["unit_id"] == "acme.com", "scraped_at"].item()
    n_calls = len(client.calls)

    changes = reclassify(units, tmp_path, results_path=res, review_path=q)

    assert [c["unit_id"] for c in changes] == ["beta.com"]
    out = pd.read_csv(res, dtype=str).set_index("unit_id")
    assert out.at["beta.com", "match_status"] == "ambiguous"
    assert out.at["acme.com", "scraped_at"] == stamp
    assert len(client.calls) == n_calls
    prog = pd.read_csv(tmp_path / "progress.csv", dtype=str).set_index("unit_id")
    assert prog.at["beta.com", "status"] == "ambiguous"
    assert set(pd.read_csv(q, dtype=str)["unit_id"]) == {"beta.com"}


def test_reclassify_prunes_queue_rows_of_resolved_units(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({"unit_id": "acme.com", "batch": "main", "search_name": "Acme", "alt_search_names": None,
                    "web_domain": "acme.com", "country_code": "FR", "town": None, "has_domain": True})
    res, q = tmp_path / "res.csv", tmp_path / "q.csv"
    scrape(units, tmp_path, client=FakeClient(by_search={"Acme": _item()}), retries=0,
           check_stops=False, results_path=res, review_path=q)
    write_review_queue(q, [{"unit_id": "acme.com", "candidate_url": "stale"}])
    assert reclassify(units, tmp_path, results_path=res, review_path=q) == []
    assert pd.read_csv(q, dtype=str).empty


def test_apply_review_marks_accept_matched_and_survives_reclassify(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({"unit_id": "beta.com", "batch": "main", "search_name": "Beta", "alt_search_names": None,
                    "web_domain": "beta.com", "country_code": "FR", "town": None, "has_domain": True})
    url = "https://www.linkedin.com/company/beta"
    client = FakeClient(by_search={"Beta": _item(name="Beta", website="https://other.io", linkedinUrl=url, universalName="beta")})
    res, q = tmp_path / "res.csv", tmp_path / "q.csv"
    scrape(units, tmp_path, client=client, retries=0, check_stops=False, results_path=res, review_path=q)
    assert pd.read_csv(res, dtype=str).loc[0, "match_status"] == "ambiguous"
    dec = tmp_path / "dec.csv"
    pd.DataFrame([{"unit_id": "beta.com", "candidate_url": url, "claude_decision": "accept", "human_decision": None}]).to_csv(dec, index=False)

    assert apply_review(dec, tmp_path, results_path=res, units_df=units, review_path=q) == ["beta.com"]

    row = pd.read_csv(res, dtype=str).iloc[0]
    assert (row["match_status"], row["match_method"], row["linkedin_url"]) == ("matched", "claude_review", url)
    assert row["description"] == "We make things."
    assert pd.read_csv(q, dtype=str).empty
    assert pd.read_csv(tmp_path / "progress.csv", dtype=str).loc[0, "status"] == "matched"
    assert reclassify(units, tmp_path, results_path=res, review_path=q) == []
    assert pd.read_csv(res, dtype=str).loc[0, "match_status"] == "matched"


def test_apply_review_human_decision_overrides_claude(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    units = _units({"unit_id": "beta.com", "batch": "main", "search_name": "Beta", "alt_search_names": None,
                    "web_domain": "beta.com", "country_code": "FR", "town": None, "has_domain": True})
    url = "https://www.linkedin.com/company/beta"
    client = FakeClient(by_search={"Beta": _item(name="Beta", website="https://other.io", linkedinUrl=url, universalName="beta")})
    res = tmp_path / "res.csv"
    scrape(units, tmp_path, client=client, retries=0, check_stops=False, results_path=res, review_path=tmp_path / "q.csv")
    dec = tmp_path / "dec.csv"
    pd.DataFrame([{"unit_id": "beta.com", "candidate_url": url, "claude_decision": "accept", "human_decision": "reject"}]).to_csv(dec, index=False)
    assert apply_review(dec, tmp_path, results_path=res, units_df=units, review_path=tmp_path / "q.csv") == []
    assert pd.read_csv(res, dtype=str).loc[0, "match_status"] == "ambiguous"
