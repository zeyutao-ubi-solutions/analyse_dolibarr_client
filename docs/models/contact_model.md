# Contact model: plan

> Status (2026-11-20): planning, not started. Which fields HubSpot actually has and their coverage are not yet confirmed; everything below that depends on fields must be settled after the probe in step 1.

## 1. The question

**Within a company, whom do we contact first?** Given a contact at a company (job title, department, level), decide whether they are the person we should reach, and which business line suits them.

Relation to the company model:

```
Company priority   = fit_overall × country_factor          (company model, see company_lookalike.md)
Contact score      = contact_role_score                     (this model)
Final ranking      = company priority × contact score
```

The company model answers "which company to target", the contact model answers "whom to target in that company". The two are trained and evaluated separately.

The web app currently judges person fit with an LLM prompt (`backEnd/config/prompts/wf001_person_fit.yml`). Once this model is live it can replace or calibrate it; until then, that prompt's results can serve as one of the baselines.

## 2. Data source: HubSpot (read-only)

The web app already has a read-only integration (see `docs/data_sources.md` section 4). Objects and fields likely to be used:

| Object | Fields (to be confirmed by probe) | Use |
|---|---|---|
| contacts | `jobtitle`, `lifecyclestage`, `hs_lead_status`, `notes_last_contacted`, `num_associated_deals`, `createdate`, unsubscribe / do-not-contact fields | Features (job title), labels (stage, status), exclusion (unsubscribed) |
| deals | `dealstage`, `closedate`, `amount`, product-line fields (if any) | Labels: which contacts took part in won deals |
| companies | `domain`, `name` | Link contacts to the company model's sample units |
| Associations | contact ↔ company, contact ↔ deal | Same as above |
| Source | Whether the record was written by the web app, which campaign it came from (lemlist, etc.) | Identify selection bias (section 6) |

### Step 1: field probe

Use the web app's read-only tool `field_probe.py` to pull a field report: field names, enum values, fill counts, **no personal records**. From it, determine:

- the fill rate of `jobtitle` (below about 50%, it needs to be supplemented from LinkedIn profiles or the people data the web app already scraped);
- which values of `lifecyclestage` / `hs_lead_status` are actually used, and how many of each;
- whether deals can be mapped to business lines (geolocation / RFID / Ubi Cloud);
- how many contacts are associated with won deals;
- the names of the unsubscribe and do-not-contact fields.

## 3. Labels (to be settled after the probe; preliminary proposal below)

| Label | Definition (preliminary) | Notes |
|---|---|---|
| Positive: deal-related | Contacts associated with a won deal | Most reliable, but possibly few |
| Positive: progressed | Reached the "opportunity" stage or later, meeting booked, replied | More of them, but noisier |
| Negative: clearly not relevant | Marked by sales as not a fit / wrong person / no authority | True negatives; depends on whether `hs_lead_status` has such values |
| Unlabelled | Contacted with no outcome, or never contacted | As with the company model, cannot be used directly as negatives |

Business-line dimension: if deals can be mapped to business lines, add an allocation model as in the company model (who buys geolocation, who buys RFID, who buys Ubi Cloud).

## 4. Features

| Allowed | Processing |
|---|---|
| Job title (`jobtitle`, plus the LinkedIn profile headline if available) | Multilingual embeddings (same technology as the company model); after normalisation, extract level (executive / director / manager / staff) and function (operations, logistics, IT, purchasing, quality, finance…) |
| Department / function | Categorical |
| Model output for the contact's company | `fit_overall`, `p_*`, company size — as context, not retrained |

| Forbidden | Reason |
|---|---|
| Name, gender (including inferred from name or photo), age, nationality / ethnicity, photo | Unrelated to the work role; discrimination and GDPR risk |
| Email address, phone, personal social activity, school | Not needed; widens the scope of personal data processing |
| HubSpot owner, number of sales follow-ups | Reflect sales behaviour rather than the person, causing leakage |
| Country, city | As in the company model, used only for weighting and evaluation |

## 5. Model and validation

- Structure: same tech stack as the company model (multilingual embeddings + logistic regression, JSON + npz model files, no pickle).
- Baselines:
  1. Keyword rules (e.g. add points if the job title contains logistique / supply chain / opérations / directeur, etc.);
  2. The web app's existing LLM person fit.

  The model must beat both baselines to go live.
- Split: grouped by company (contacts of the same company in the same fold), plus time-based validation (train on earlier-created contacts, test on later ones).
- Metrics: AUC, average precision, whether the top-ranked person in each company is correct (on companies with several contacts).

## 6. Main risk: selection bias

Contacts in HubSpot are not a random sample:

- some were written after the web app's own filtering (the web app creates contacts and companies in HubSpot), so the model may merely learn "whom the web app used to like";
- sales contacted only people they considered suitable, so job-title types never contacted have no labels at all;
- earlier-created contacts have had longer to convert.

Mitigation: record each contact's source and report evaluation grouped by source; compare labels only among people who "were contacted"; validate over time.

## 7. Personal data and compliance (must be done before starting)

Contacts are personal data subject to GDPR, much more sensitive than company data. The points below must be confirmed with legal / the DPO; this document is not legal advice:

- **Legal basis**: B2B prospecting usually relies on "legitimate interest", which requires a written legitimate interest assessment; profiling and scoring contacts must be disclosed in the privacy notice.
- **Whether a DPIA is needed** (data protection impact assessment): usually recommended for large-scale profiling.
- **Objection and unsubscribe**: contacts who unsubscribed or objected are excluded from training and are not scored.
- **Not solely automated decisions**: scores are only a reference for sales; a person decides whether to make contact (not a solely automated decision within the meaning of GDPR Article 22).
- **Data minimisation**: training data keeps only a pseudonymised ID (salted hash), job title, derived level / function and labels; names, emails and phones are not exported. The mapping between ID and real person stays only in HubSpot.
- **Storage and retention**: training data lives only in local `data/` (encrypted disk), never in git; set a retention period and delete training exports when it expires; model files contain no personal data (unlike the company model, no nearest-neighbour index is stored, or only job-title embeddings are stored without identities).
- **Access**: HubSpot token with read-only permissions, read at runtime; export scripts pull only the fields needed.

## 8. Steps

1. Confirm section 7 with legal / the DPO and record the conclusions.
2. Run the field probe and write a field report (field names and counts only).
3. Settle labels and sample size from the probe results; if samples are too few (e.g. fewer than about 200 deal-related contacts), use rules + LLM first while accumulating data.
4. Write a read-only export module: pseudonymised, allowlisted fields only, stored in `data/`.
5. Job-title normalisation and level / function classification, compared with the keyword baseline.
6. Training and validation (section 5), write a report.
7. Integrate scoring into the web app, sharing the feedback loop with the company model (recording contact outcomes).

## 9. To decide

- [ ] Legal basis, DPIA, retention period (legal / DPO)
- [ ] HubSpot field probe results
- [ ] Exact label definitions (section 3)
- [ ] Whether to supplement job-title data with the LinkedIn people data the web app already scraped, if insufficient
- [ ] Whether the contact model is also split by business line
