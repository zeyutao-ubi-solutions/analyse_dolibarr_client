# Decision log

Decisions that affect data, labels and models, in chronological order. Add new decisions under the corresponding date; when overturning an earlier decision, do not delete the original entry, but add after it "Superseded by the decision of YYYY-MM-DD".

## 2026-11-18 / 19: Customer list

| Decision | Reason |
|---|---|
| The raw snapshot `data/raw/` is read-only; all outputs go under `data/`; `data/`, `.env` and secrets never go into git | Security of customer data and credentials |
| Joining on `CUSTOMER_ID = THIRD_PARTY_ID` is forbidden | `CUSTOMER_ID` is a hash, and some of them merge several third parties |
| No ICP score for customers in this round; suspected integrators are only flagged, not removed | Scoring is left to the later model; removal is irreversible |
| **Read-only** calls to the Dolibarr REST API are allowed (approved by the user) | Name matching left about 300 customers unmatched; the order socid is the only reliable key |
| The API socid is used only when both the order id and the order number match | The API instance and the data warehouse diverge from ORDER_ID ≈ 9704 |
| Orders invoiced to group intercompany entities are deducted from the customer amount; customers invoiced only to intercompany entities are excluded | Internal transactions are not external sales |
| `lookup_name` prefers the invoiced third-party record name; when it is unrelated to the order name, add the `lookup_name_conflict` flag and search both | The order name is sometimes a merged label |
| Websites and emails are stored as **domains** only, never full email addresses or personal names | Data minimisation |

## 2026-11-20: Company lookalike model

| Decision | Reason | Decided by |
|---|---|---|
| Model target A: using only LinkedIn information, judge whether a company looks like our end customers (PU learning, prospects are the unlabeled samples) | Most usable samples, labels need almost no manual labelling, directly usable to rank prospects | User |
| Sample unit = one website domain (group); train / test split by group | On LinkedIn, subsidiaries often share the group page; avoids leakage | Confirmed by user |
| **Country is not a feature**; unlabeled samples are reweighted by country | 81% of positives are in France; otherwise the model learns "is this a French company" | User |
| The effect of country on closing deals is expressed outside the model by a **country factor** (starting from the historical conversion rate, can be overridden manually) | Country does affect closing, but historical data cannot separate "hard to sell" from "never tried to sell"; strategy changes need no retraining | Confirmed by user |
| Business lines are determined by Dolibarr **product tags** (`GPSBLE` etc.); untagged products are filled in by name rules | The user confirmed BLE is classified with tags in Dolibarr; `ITEM_CATEGORY` cannot separate them | User |
| Business scope: hardware (géolocalisation, traçabilité) + software (Connected Things, Ubi Cloud); **Connected Things and géolocalisation are the same line**; the web app no longer classifies by product catalogue | The product catalogue is marketing packaging | User |
| Model structure: **overall model + business-line allocation model** (replaces "one PU model per line") | Too few positives for geolocation and Ubi Cloud; Ubi Cloud is almost always an add-on purchase by hardware customers | User |
| **The company description is the main feature**, LinkedIn industry is only auxiliary; NAF / NAICS do not go into the model | The industry field is often inaccurate or too broad; official codes exist only for some countries and would become a country proxy | User |
| Scrape LinkedIn first, then build industry groupings | Industry groupings are for display and evaluation later and do not block training | User |
| The scrape list contains no customer labels; unlabeled samples are sampled stratified by country | Matching must not differ by label; after sampling the weights are close to uniform and fewer pages need scraping | Confirmed by user |
| Matching tightened after the pilot: matching main domain takes precedence; without a domain, identical name + same country; everything else goes to the manual queue; no automatic match when country is empty | Of the 13 "matched" in the pilot, 7 were wrong or doubtful | Confirmed by user |
| No cost cap on scraping | The measured unit price is very low (about $0.0012 / item) | User |
| Technology: fastembed + multilingual e5, scikit-learn logistic regression, model files as JSON + npz (no pickle); embedding model size chosen after comparison on real data | Runs locally, reproducible; the web app backend has no machine-learning libraries; server memory is limited | Confirmed by user |
| The training module is developed in a separate worktree / branch `lookalike-training` | The scraping agent is changing code and dependencies on `lookalike-labeling` at the same time | Confirmed by user |
| A contact model will later be trained on HubSpot contact data; plan first and confirm compliance first | See `docs/models/contact_model.md` | User |

## 2026-11-24: Company activity scoring

| Decision | Reason | Decided by |
|---|---|---|
| Segment list v2: 37 segments (`docs/segments/segments_v2.csv`) | The draft plus 13 found in customer data, covering 90% of customers | User |
| Scoring has two parts: **fit** and **priority**. Fewer than 51 employees or a research institution = low priority, never excluded | Small companies and research institutions are also suitable, but sales has companies more worth contacting first | User |
| Every company with a closed order counts as a customer; no further question about whether it resells | User: they all have closed orders, it doesn't matter | User |
| Training labels come from a vote of three models; only unanimous (3 of 3 votes) rows are used | On the audit set, unanimous rows agree 100% with an independent group of strong models, 2-1 splits only 54% | Confirmed by user |
| Weak segments topped up with 486 keyword-labelled companies | 7 segments have fewer than 15 samples, recall 0–50% | User |
| Model: e5 embeddings + logistic regression (44 classes); explanation via "the 3 most similar labelled companies" | Better than TF-IDF (AUC 0.97 vs 0.93, segment accuracy 0.79 vs 0.57); zero-shot is unusable. The embedding model also learns the text language, so per-language weighting was added later (see below) | Confirmed by user |
| Size uses the LinkedIn declared employee range first; when only the associated LinkedIn members count is available, ≥51 counts as normal and <51 as `unknown_size` | The members count is only a lower bound: 108 prospects have only a members count (median 3), and the old rule misclassified 105 of them as low | Confirmed by user (2026-11-25) |
| Declared employee range <51 but LinkedIn members ≥51 → normal | The members count is a lower bound, so the declaration is outdated; 19 prospects are in this case | User (2026-11-25) |
| Template descriptions keep only the LinkedIn industry, not the company name; label recorded as `template_only`, candidate segments come from the industry mapping table, and they are excluded from training | The company name is also a country proxy (COMMUNE DE, SARL); industry-only text is too short for the model to give a reliable segment | User (2026-11-25) |
| Companies used in training are scored with out-of-fold scores | Otherwise the scores mostly repeat the training labels and sit at the top of the table | User (2026-11-25) |
| Added LinkedIn industry one-hot features (with an industry-free copy); prospect threshold raised from 0.5 to 0.7 | Improvement analysis: 8-class accuracy 0.82 → 0.86, other recall 0.40 → 0.64, segment accuracy 0.80 → 0.85. Confidence weights, soft labels, two-stage, kNN and MLP did not help | User (2026-11-25) |
| other split into 5 sub-labels (second three-model vote), insufficient_info merged into other; threshold changed to 0.65 to keep prospect recall at about 0.95 | Share of other misclassified as prospect: cross-validation 19.8% → 14.5%, audit set 31% → 15% | User (2026-11-25) |
| The output for sales is merged into four classes (prospect / competitor / template_only / not_target), with an added segment family `category`; training keeps all fine-grained classes | Merging during training would drop precision from 0.94 to 0.89; for sales, four-class accuracy is 0.91 vs only 0.87 for 8 classes | User (2026-11-25) |
| Template descriptions (based out of address / country) are cut before embedding and marked as insufficient information | Address and country are country proxies; the review found 219 prospects with such descriptions | User confirmed the fix |
| Training is weighted by language so that every language has the same prospect share | French descriptions had systematically higher fit (0.095 higher for non-prospects), violating the rule that country plays no role in scoring | User confirmed the fix |
| label = prospect if and only if fit ≥ 0.5; the low priority for research institutions applies only to prospects | Evaluation and production use the same rule; non-prospects such as IBM and Wavestone are no longer downgraded because of their segment | User confirmed the fix |
| Customer pages and descriptions are excluded from training; the scoring table flags companies sharing a page with a customer | The review found 8 training rows and 10 prospects sharing a page with a customer | User confirmed the fix |

## Pending decisions

| Item | Impact |
|---|---|
| Where the web app is deployed in production (cloud / on-premises or office machine) | Model integration approach, whether an always-on machine is needed |
| Which Dolibarr instance is production (needs IT confirmation) | socid for orders after September 2026 |
| Legal basis, DPIA and retention period for the contact model (legal / DPO) | Whether the contact model can start |
| Whether to define industry groupings for sales (NACE / NAICS / LinkedIn industry mapping) | Web app filters and evaluation by industry |
| Hard threshold for `fit` (set by the false-positive rate sales can accept) | Whether to show sales only prospects |
