# Company activity scoring (activity scorer)

> Status (2026-11-25): first version trained and revised after two review rounds; then, following the 2026-11-25 improvement analysis, LinkedIn industry was added, other was split into 5 sub-labels, and the threshold was moved to 0.65 (reports are all in `data/processed/2026-11-18/scores/review_2026-11-24/`). Model files are in `data/models/activity/2026-11-25/`. The code is `src/analyse_dolibarr_client/activity.py`.
> It replaces the lookalike PU model as the main scoring method. The PU model answers "who will buy", which is not the question the user is asking (see `docs/decisions.md` 2026-11-23).

## 1. The question

**What does this company do? How well does its business fit our target segments?**

- Uses the LinkedIn description only. **Country never takes part in scoring**; sales filter by country themselves.
- Two outputs, given separately:
  - **Fit `fit`**: whether the company is an end user in one of the 37 target segments, and which segment.
  - **Priority `priority`**: `low` only means sales can contact it later; it **never excludes**. Rules in section 5.

## 2. Model

| Step | Approach |
|---|---|
| Text | `passage: ` + the first 1,500 characters of the description. LinkedIn's auto-generated template descriptions ("X is a … company [based out of address, city, country]") are rewritten as "This organisation is a {industry} company.", with the company name, address and country removed |
| Embeddings | `intfloat/multilingual-e5-large` (fastembed, local ONNX), weights in `data/models/fastembed/` |
| Embedding cache | `data/models/embedding_cache/activity_e5large.npz`, keyed by sha256(model name + text). Training and scoring use the same text function |
| Classifier | One multinomial logistic regression, C=30, 47 classes in total: 37 segments (`docs/segments/segments_v2.csv`) plus 10 non-prospect labels: consulting, supplier, competitor, school, media, other, and the 5 sub-labels of other (see below). `insufficient_info` had only 6 training examples and was merged into other |
| other sub-labels | A second three-model vote (majority): `other_sector_body` (associations, federations, industry clusters, certification bodies, tourism promotion agencies), `other_investor_owner` (funds, holdings, property owners), `other_sector_vendor` (sells software or services to the target sector), `other_single_small_site` (single shop, small site), `other_unrelated` (other, unrelated). These organisations that "belong to the target sector but do not operate in it" are exactly the ones most often misclassified as prospects |
| Industry feature | One-hot of the LinkedIn industry (the 87 industries seen ≥5 times in training; old industry names are first mapped to new ones), value 0.3, concatenated with the text embedding. In training, each row with an industry gets an extra copy without the industry (half weight), so pages without an industry can still be scored normally. Industry is not a proxy for country |
| Sample weights | Class balancing × **language factor**: makes the share of prospects in each description language equal to the overall share. Language is only used for weighting, not as a feature |
| `fit` | Sum of the probabilities of the 37 segment classes |
| `label` | prospect when `fit ≥ 0.65` (this threshold keeps prospect recall at about 0.95 in cross-validation; 0.5 would classify 43% of other as prospect), otherwise the non-prospect label with the highest probability. Evaluation and production use the same function `decide`. Template descriptions are always recorded as `template_only` |
| `segment` / `segment_prob` | The most likely segment given prospect, and its conditional probability, plus a second candidate. For template descriptions the segment is only a candidate, derived from the LinkedIn industry via the `linkedin_industries` mapping in `segments_v2.csv` (with an alias table for old industry names), with no probability; template pages without an industry get no `fit` |
| `sales_label` / `category` | Four classes shown to sales: prospect / competitor / template_only / not_target; the fine label is kept in `label`. `category` is one of the 10 segment families the segment belongs to, and is more reliable than the segment (in cross-validation the segment is exactly right 84% of the time, the segment family 90%) |
| Explanation | `similar_training_companies`: the 3 labelled companies in the same segment most similar to this company. The one with identical text (the company itself) is skipped. Given for prospects only |
| Companies seen in training | `train --oof-out` produces 5-fold out-of-fold scores; `score --oof` uses them to replace the scores of companies with identical text (`score_source = out_of_fold`); these scores come from a model that never saw the company |
| Consistency check | The model stores the embedding of a fixed text; before scoring it is recomputed with the current embedding model, and cosine similarity must be ≥ 0.99 |
| Model files | `model.npz` (plain arrays, no pickle) + `meta.json` (training-data hash, class and language counts, evaluation results) |

**`fit` is a ranking score, not a calibrated probability**, and it runs high overall: the median for prospects is about 0.9. Any hard threshold should be set from the false-positive rate reported by sales.

## 3. Training data

All in `data/external/server_companies/2026-11-23/training_labels_2026-11-24/` (gitignored, has a README, reproducible by script).

- **Sampling**:
  - 2,300 companies from the server company pool, stratified by the original LLM label;
  - 300 transport / equipment rental pages;
  - 400 Dolibarr prospects;
  - 486 extra companies sampled by keyword for 12 weak segments.
- **Labelling**: blind labelling by three models, gpt-6.2-sol, claude-sonnet-5-5 and claude-haiku-5-5, seeing company name, industry, size and description; total cost about USD 12.
- **Training rows** (`training_rows`):
  - only unanimous (3 of 3 votes) rows;
  - rows whose LinkedIn page or description matches the evaluation set (432 customers) are removed; customers are used for evaluation only;
  - rows with identical descriptions are kept only once;
  - template descriptions are excluded from training, because their votes depend on the company name.
  - Result: **2,643 rows, of which 1,639 prospects**.

## 4. Performance (`train_eval.py`, results in `train_eval_results.csv`)

| Evaluation set | Size | AUC | 8-class accuracy | prospect precision / recall | Segment accuracy |
|---|---:|---:|---:|---:|---:|
| Cross-validation (clean rows from the original 3,000-company sample) | 2,266 | 0.979 | 0.88 | 0.95 / 0.95 | 0.84 |
| Audit set (≥5 of 6 models agree) | 167 | 0.976 | 0.85 | 0.90 / 0.92 | 0.87 |
| **Rows with a 2-1 split among the three models (not in training)** | 735 | 0.782 | 0.51 | 0.56 / 0.77 | 0.57 |

For 8-class accuracy, all sub-labels of other count as other. In cross-validation, recall is 0.75 for other and 0.64 for supplier. Customer evaluation set (432 companies): 85% are classified as prospect, and agreement of the segment with the three-model majority vote is 0.77.

**Effect of splitting other** (`training_labels_2026-11-24/other_split/experiment_results.csv`, prospect recall fixed at 0.95):
- Cross-validation: prospect precision 0.937 → 0.949; share of other misclassified as prospect 19.8% → 14.5%;
- Audit set: other recall 0.54 → 0.81; share of other misclassified as prospect 31% → 15%.

An alternative, merging the non-target labels into one class at training time, did worse: prospect precision fell from 0.94 to 0.89. So they are merged only in the output shown to sales.

**Compared with the text-only version with threshold 0.5** (four comparison groups in `train_eval_results.csv`):
- 8-class accuracy: 0.82 → 0.86;
- other recall: 0.40 → 0.64;
- Segment accuracy: cross-validation 0.80 → 0.85, audit set 0.77 → 0.85;
- The cost: prospect recall falls from 0.99 to 0.95, and the share of customers classified as prospect falls from 91% to 86%.

Tried during the improvement analysis without effect: weighting by the three models' confidence, soft labels from 2-1 split samples, a two-stage model, kNN, MLP, no class balancing. The audit set was also used to choose C (10 / 30 / 100), so it is not a fully independent test set.

**All these numbers are optimistic.** The "ground truth" of the first two sets also comes from model votes, and only includes "easy" samples on which the models agreed. The 2-1 split set holds the hard samples, and there the model clearly leans towards prospect.

**Error-rate estimates from manual spot checks:**
- First-round reviewer checked 52 companies (pre-revision model): about 25% wrong segment. About 15% for fit ≥ 0.9, about 50% for fit between 0.4 and 0.7.
- Second round checked 42 companies (model after the first revision), only companies with a normal description that were not in training: prospect or not wrong about 5–12%, segment wrong about 25–35%.

**Known common errors:**
- Industry associations and industry clusters classified as prospects;
- Technology vendors selling to the target sector assigned to their customers' segment;
- Companies with only a template description, especially French laundries and medical facilities, often get the wrong segment;
- The retail e-commerce and wholesale segments are often confused with each other.

**Language bias:** among non-prospects, French descriptions get a higher average fit than English ones. With language weights the gap fell from 0.108 to 0.072; after adding the industry feature and the other sub-labels it fell to 0.033. The remaining gap comes mainly from sample source: within the same source (the server pool) the gap is only 0.03. The second-round reviewer found the gap no longer significant after controlling for class and source; on 12 French/English translated text pairs, fit differs by only −0.007 on average.

Other approaches compared:
- TF-IDF bag of words: AUC 0.93, segment accuracy 0.57, and the text language itself is a proxy for country;
- Two-stage (8 classes first, then segment): slightly worse;
- Direct similarity to segment descriptions (zero-shot): AUC 0.57, unusable.

## 5. Priority rules

| Case | priority |
|---|---|
| label = prospect, and the segment is low priority (research institutions) | low |
| Declared employee range < 51, but LinkedIn members ≥ 51 (member count is only a lower bound, so the declaration is outdated) | normal |
| Lower bound of the LinkedIn declared employee range < 51 | low |
| No employee range, but associated members ≥ 51 (member count is only a lower bound; ≥51 is enough to prove size) | normal |
| No employee range, associated members < 51, or nothing at all | unknown_size |
| Otherwise | normal |

Employee ranges can be in formats such as `51-200`, `1,001-5,000`, `10,001+`, `51_200`, `201_plus`. Reason text is bilingual English/French; output columns include `declared_range_lower` and `linkedin_members`.

## 6. Usage

```bash
uv run python -m analyse_dolibarr_client.activity train \
  --labels data/external/server_companies/2026-11-23/training_labels_2026-11-24/labels.csv \
  --eval-results data/external/server_companies/2026-11-23/training_labels_2026-11-24/train_eval_results.csv \
  --out data/models/activity/2026-11-25 --oof-out data/models/activity/2026-11-25/oof_scores.csv

uv run python -m analyse_dolibarr_client.activity score \
  --model data/models/activity/2026-11-25 --oof data/models/activity/2026-11-25/oof_scores.csv \
  --input companies.csv --output scores.csv
```

- **Input**: requires a `description` column; `employee_count_range`, `employee_count` or `employees` are used for priority. A country column is not read even if present.
- **Output**: `fit`, `label`, segment and its probability, `similar_training_companies`, `priority` and reason, `thin_text` (fewer than 20 words or a template description), `template_text`.
- **Speed**: about 0.6 seconds per company on local CPU; texts already in the cache are not re-embedded.

Prospect trial sheet: three scripts under `data/processed/2026-11-18/scores/`:
- `build_prospect_input.py`: flags `in_training`, `same_page_as_customer`, `same_page_units`;
- score with `activity score`;
- `build_activity_review.py`: builds the sheet for sales.

## 7. Next steps

- Once the user has checked the red rows of the audit sheet, re-evaluate with the manual labels.
- Collect sales feedback: set the `fit` threshold, add missing segments, add associations and technology vendors as negative examples.
- Integrate into the web app: the web app backend has no machine-learning libraries, so only `coef` / `intercept` can be exported (a numpy matrix multiplication is enough), with the embedding service deployed separately.
- When the segment list changes: relabel the affected rows, then retrain. The definition of `waste_management` changed on 2026-11-24 from "hazardous waste" to waste treatment in general, but the existing labels follow the old definition.
