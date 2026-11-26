# Feature policy: lookalike model

The question the model answers: **looking only at a company's public LinkedIn information, does it look like our end customers?**
Samples and labels are in `lookalike.py` / `lookalike_units.csv`; this file defines which information may go into features.

## Principles

1. **Features come only from the LinkedIn company page.** Orders, amounts, categories and value tiers in Dolibarr may be used only as labels or for analysis, never as features: prospects do not have this data, so using it is leakage.
2. **Country is not a feature, and neither are country proxies.** 81% of positives are in France, while unlabeled samples are mainly from Spain, France, Germany and Poland; any field from which the country can be inferred will make the model learn "is this a French company".
3. **Information that identifies a specific company does not go into features** (name, domain, URL); otherwise the model memorises the answers.

## Allowed

**The main feature is the company description (About / description)**: the LinkedIn industry field is chosen by the company itself, is often inaccurate or too broad, and is only auxiliary.

| LinkedIn field | Role | Handling |
|---|---|---|
| About / description | **Main feature** | Multilingual embedding model (texts with the same meaning in different languages land in the same place), or translate everything into English first and then embed; never raw bag-of-words, character n-grams or the language itself |
| Tagline, Specialties | Auxiliary text | Handled like the description; can be concatenated into the same text or embedded separately |
| Industry | Auxiliary | Categorical feature, using LinkedIn's English industry codes; corrected by the description when inaccurate, never decides the result on its own |
| Company size / Employees on LinkedIn | Auxiliary | Ordinal category / log transform |
| Company type (public / private / government / non-profit…) | Auxiliary | Categorical |
| Founded (founding year) | Auxiliary | Numeric; missing values encoded separately |
| Followers | Auxiliary | Log transform |
| Number of locations | Auxiliary | Only the **count**, never the locations themselves |
| Has affiliated pages / parent company | Auxiliary | Boolean |

Companies with an empty or very short description (e.g. fewer than 20 words) are flagged separately: their score comes mainly from auxiliary features and is less reliable; the web app should show a warning.

Official industry codes such as NAF / NAICS do not go into the model (they exist only for some countries and would become a country proxy); they can later be used for industry groupings shown to sales and for evaluation by industry.

## Forbidden

| Field | Reason |
|---|---|
| Headquarters country, city, region, postcode | Directly the country |
| Locations list | Same as above |
| Website domain, top-level domain (.fr / .es / .de) | Country proxy; also memorises specific companies |
| **Language** of the description / specialties, raw bag-of-words, character n-grams | Language = country |
| Company name and words in the name (FRANCE, ESPAÑA, GmbH, SAS, S.L.) | Country proxy + memorises companies |
| Legal form | SAS/SARL vs S.L. vs GmbH is the country |
| Phone, address | Country proxy |
| Employees' locations / schools | Country proxy |
| Any Dolibarr field (amount, category, `value_tier`, `country_code`, `web_domain_source`…) | Leakage |

`country_code` and `country_bucket` in `lookalike_units.csv` are used only for weighting and evaluation, never in the model.

## Weighting

`sample_weight`: positives = 1; unlabeled samples are reweighted by country bucket so that the weighted country distribution of unlabeled samples matches the positives (countries with fewer than 10 positives are merged into `other`); `excluded` = 0.
Pass it to the model's `sample_weight` during training. Cost: the effective sample size of unlabeled samples drops from 8,648 to about 2,900, and French prospects get the highest weights.

## How country enters the ranking: country factor

Country does affect closing deals (distance, installation, sales coverage), but it **does not go into the model**; instead it is multiplied in separately outside the model:

```
priority = model score (profile only, no country) × country_factor
```

- Factor table: `data/processed/<snapshot>/labeling/country_factors.csv`, one row per country; the `country_factor` column in `lookalike_units.csv` is already filled in per country.
- `historical_rate` = positive units / (positive + unlabeled units), with a 95% Wilson interval. It mixes "really hard to sell" with "barely tried to sell" (e.g. bulk imports, lists never followed up), so it is **only a starting point**.
- `suggested_factor` = smoothed rate / France rate. Countries with few positives are pulled towards "the pooled rate of all countries other than France" (a prior of 20 pseudo-samples), so that 1/3 does not count as 33%.
- Enter a number in `manual_factor` to override (`manual_note` / `set_by` / `set_at` record the reason and the person); **reruns never overwrite it**, and old files are backed up in `labeling/history/`; non-numeric or negative values raise an error. `factor_source` says whether the final value is manual, suggested or missing.
- `unknown` (missing country) has no suggested value: customers always have a country, only prospects lack one, so the 0% is a data artefact. Fill in the country first, or set a factor manually.

Changing strategy (e.g. deciding to focus on Spain) only requires editing `manual_factor`; no model retraining.

## Product lines (business lines)

Business scope (confirmed 2026-11-20): **hardware + software**.

| Business line | id | Includes |
|---|---|---|
| Géolocalisation / Connected Things | `geoloc` | BLE / GPS / LoRa trackers, beacons, gateways and their rental; Connected Things is the software platform for geolocation and is the same line as geolocation |
| Traçabilité | `rfid` | RFID tags, readers / antennas, gates / tunnels, RFID terminal kits |
| Ubi Cloud | `ubi_cloud` | Ubi Cloud subscriptions / licences (product name contains UBI Cloud, including "Ubi Cloud IoT") |

The web app used to classify by product catalogue (marketing's industry / product packaging); it has been confirmed that this is no longer used, replaced by these three business lines.

Product lines are a **label dimension, not a feature**: prospects have not bought anything yet.

### Model structure: overall model + allocation model (decided 2026-11-20)

```
Step 1  Overall model (PU)            Does this company look like our customers?       → fit_overall
Step 2  Allocation model (multilabel) If it were a customer, which lines would it buy?  → p_geoloc, p_rfid, p_ubi_cloud

Score for a line  = fit_overall × p_<line>
Ranking priority  = fit_overall × country_factor (multiply by p_<line> again when ranking by line)
```

| Model | Training data (`lookalike_units.csv`) | Label | Weight |
|---|---|---|---|
| Overall model | `label` is positive or unlabeled | positive = 1, unlabeled = unlabeled (PU) | `sample_weight` (country-balanced) |
| Allocation model | `in_allocation_set=true` (customer units that bought at least one line) | `positive_geoloc` / `positive_rfid` / `positive_ubi_cloud`, can be true at the same time | No country weight (comparisons only within customers) |

Why not one PU model per line: geolocation has 204 and Ubi Cloud 135 positives, too noisy to train separately; Ubi Cloud is almost always bought together with hardware, so a separate PU model would learn "is this a hardware customer". The allocation model uses the same set of customers for all three lines and compares only within customers, so it learns "which kind of customer buys which line".

Assumption: "does it look like a customer" and "which line would it buy" can be judged separately. Entirely new industries absent from the current customer base cannot be found by this approach (or by any approach that learns only from historical customers).

### Usage

- **Finding new customers**: rank by `fit_overall × country_factor`; `p_*` tells sales which line to push.
- **Cross-selling**: for customers who already bought a line, look at the allocation model's `p_*` for the other lines (e.g. existing RFID customers with high `p_geoloc`). When evaluating the allocation model use the cross-validation predictions, to avoid self-validation on customers seen in training.
- **Evaluating the allocation model**: GroupKFold by `split_group`, report AUC / average precision per line; Ubi Cloud has few positives (135), so its metrics will fluctuate more.

### Other notes

- Determination rules: Dolibarr product tags take precedence (`UBI Solutions > GPSBLE` → geolocation; `Portique RFID` / `Kit RFID TC21` / `Terminaux RFID` → RFID); otherwise product name / subcategory / manufacturer rules (`geoloc_source=name_rule`). The GPSBLE tag only exists from about 2024; older LoRa / GPS trackers can only be caught by rules.
- Geolocation positives are mostly small 2025–2026 pilots, so `p_geoloc` learns "which kind of customer is willing to try geolocation", not necessarily "will deploy at scale". Ubi Cloud is overwhelmingly bought together with hardware, so `p_ubi_cloud` means "which kind of customer adds Ubi Cloud".
- Customer units that bought none of the three lines (only projects, maintenance, terminals, third-party software such as SOTI) go only into the overall model.

## Checks required before launch

1. **Country leakage check**: train a classifier with the same features to predict `country_bucket`. Accuracy clearly above the "always guess FR" baseline means proxies are still leaking in; find and remove them.
2. **Per-country evaluation**: besides the overall metrics, report metrics for FR and ES separately (ranking ability within each country). Good overall but poor within countries means the model is still ranking by country.
3. **Split by group**: cross-validation uses GroupKFold on `split_group`; subsidiaries with the same domain must never appear in both the training and the test set.
4. **Temporal validation**: additionally train on positives with `cohort_year <= 2024` and check whether new 2025–2026 customers rank above prospects. Note that Page Up / Ubi Smart / Ubi Impact data only entered the data warehouse from 2024, so part of that year's jump is a data artefact.
