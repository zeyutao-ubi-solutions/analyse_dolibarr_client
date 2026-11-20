# LinkedIn 抓取约定（analyse_dolibarr_client ⇄ web app）

本仓库给出要抓的公司清单，web app（Apify）抓 LinkedIn **公司主页**，按下面的格式交回，本仓库再训练 lookalike 模型（总模型 + 分配模型，见 `feature_policy.md`）。

只抓公司主页，**不抓任何个人资料**（员工、联系人、帖子作者）。

## 1. 输入：抓取清单

`data/processed/<snapshot>/labeling/linkedin_scrape_list.csv`（UTF-8 BOM），由下面的命令生成：

```bash
uv run python -m analyse_dolibarr_client.scrape_list --snapshot <snapshot>
```

| 列 | 说明 |
|---|---|
| `unit_id` | 主键，交回时原样带上。是域名（如 `geodis.com`）或 `tp:<第三方id>` / `cust:<客户id>` |
| `batch` | `main` 先抓；`reserve` 是备用，`main` 里找不到主页的比例高时再抓 |
| `search_name` | 主搜索名 |
| `alt_search_names` | 其他名字，`;` 分隔（订单名、别的档案名）。`search_name` 搜不到或结果不像时再试 |
| `web_domain` | 已知域名，**最可靠的匹配依据**（见第 3 节） |
| `country_code` / `town` | 消歧用：同名公司时选这个国家 / 城市的 |
| `registry_id` | 档案里登记的号码（SIREN、SIRET 或外国税号，未清洗），仅供人工核对 |
| `has_domain` | 没有域名的单元只能靠名字匹配，错配风险更高 |

清单里**故意没有**「是不是客户」的标签，也不按标签排序。抓取和匹配（包括任何 LLM 判断）都不能知道哪些是客户，否则匹配质量会因标签而不同，模型会学到假信号。

## 2. 输出：每个 unit_id 一行

交回 `linkedin_companies_<日期>.csv` 或等价的 JSONL，放到 `data/processed/<snapshot>/labeling/` 下。

### 匹配信息（必填）

| 列 | 说明 |
|---|---|
| `unit_id` | 来自清单 |
| `match_status` | `matched` / `not_found` / `ambiguous`（多个候选拿不准）/ `error` |
| `match_method` | `domain`（主页网站域名 = `web_domain`）/ `name_country` / `name_only` / `manual` |
| `linkedin_url`、`linkedin_public_id` | 公司主页 |
| `candidates` | `ambiguous` 时列出候选主页 URL，`;` 分隔 |
| `scraped_at` | ISO 时间 |

### 特征原始字段（尽量全）

| 列 | 用途 |
|---|---|
| `description`（About） | **主特征**。原文保存，不翻译、不截断；语言由本仓库处理 |
| `tagline` | 辅助文本特征 |
| `specialties` | 辅助文本特征，`;` 分隔，原文 |
| `industry` | 辅助特征（LinkedIn 行业，原值，英文 code 或标签都行，保持一致） |
| `employee_count`、`employee_count_range` | 规模 |
| `company_type` | 上市 / 私营 / 政府 / 非营利… |
| `founded_year` | |
| `followers` | |
| `locations_count` | 只要数量 |
| `has_parent_or_affiliated` | 是否有母公司 / 关联页面 |
| `parent_linkedin_url` | 有母公司时填，用于判断是否抓到了集团页 |

### 只用于核对、不进模型的字段

| 列 | 用途 |
|---|---|
| `name` | 核对匹配 |
| `website` | 核对匹配（和 `web_domain` 比） |
| `hq_country`、`hq_city` | 只用于国家加权和分国家评估；**不进模型**（国家代理变量） |

不要交回：员工名单、联系人、电话、邮箱、帖子。

## 3. 匹配规则

1. 有 `web_domain` 时，优先找主页「网站」字段的域名（去掉 `www.`）等于 `web_domain` 的主页 → `match_method=domain`，视为已确认。
2. 否则用 `search_name`（再试 `alt_search_names`）+ `country_code` / `town` 搜索：
   - 唯一且名称、国家都对得上 → `name_country`；
   - 多个候选分不清 → `ambiguous`，列出 `candidates`，**不要随便选一个**。
3. 子公司没有自己的主页、只找到集团主页时：照常交回集团主页，并在 `parent_linkedin_url` 或备注里说明。同一集团的子公司在本仓库里通常已合并为一个 `unit_id`。

非 `domain` 匹配的结果，本仓库会抽样人工核对（L1 实体对齐）；错配率高的话再调整规则。

## 4. 本仓库收到后做什么

- 按 `unit_id` 合并标签；只用 `matched` 的单元训练。
- 用实际抓到的单元**重新计算** `sample_weight`（`lookalike.add_country_weights`），因为找不到的比例各国可能不同。
- description / tagline / specialties 统一用多语言向量模型处理（不同语言的同义文本落在同一位置），不用原文词袋、不用语言本身。
- 训练前做国家泄漏检查（`feature_policy.md`）。
