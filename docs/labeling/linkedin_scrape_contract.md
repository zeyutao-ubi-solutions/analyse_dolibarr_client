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

## 3. 匹配规则（2026-11-20 试点后收紧）

试点 20 个里 13 个「matched」，人工看有 7 个错或存疑（同名外国公司、集团投行页、工会页）。原则：**宁可 not_found / ambiguous，也不要用错的主页凑数**——错配会直接污染标签，漏掉只是少一个样本。

### 3.1 搜什么（按顺序，直到有一条通过 3.2）

1. 有 `web_domain` 时，先用域名主体当品牌名搜（`aroihoteles.com` → `aroihoteles`，`360hostel.com` → `360hostel`）：法定名常搜空，品牌名更接近 LinkedIn 上的名字。
2. `search_name`，再依次 `alt_search_names`。
3. actor 若支持一次返回多个候选（如 `maxItems` / limit），取前 3–5 个，按 3.2 逐个判断；只返回第一条时就只判断第一条。

### 3.2 什么算 matched

| 情况 | 结果 |
|---|---|
| 主页 website 的主域名（eTLD+1，去掉 `www.` 和子域名，如 `fr.scc.com` → `scc.com`）= `web_domain` 的主域名 | `matched`，`match_method=domain` |
| 有 `web_domain`，主页 website 是**另一个**域名 | **不算 matched**。名称和国家都对得上时 → `ambiguous`（进人工队列），否则 → 看下一个候选 / `not_found` |
| 主页没有 website | 只有「规范化名称完全相同 + HQ 国家 = `country_code`」（有 `town` 时城市也要一致）才 `matched`，`match_method=name_country`；否则 `ambiguous` |
| 没有 `web_domain` | 同上：规范化名称完全相同 + HQ 国家一致 → `name_country`；名称只是部分相同 → `ambiguous` |
| `country_code` 为空 | **永不自动 matched**，最多 `ambiguous`（`name_only` 不再算 matched） |
| HQ 国家 ≠ `country_code` | 不算 matched；名称完全相同时 `ambiguous`，否则 `not_found` |
| 不是公司本身的页面：工会（SYNDICAT、CGT、CFDT、FO）、CSE / 员工委员会、校友 / 校园、粉丝页 | 拒绝，看下一个候选 / `not_found` |

「规范化名称」：去重音、大小写、标点和法律形式后比较（可用本仓库 `analyse_dolibarr_client.names.core_key`）。

### 3.3 额外标记（不影响 matched，但要交回）

| 列 | 含义 |
|---|---|
| `group_page` | 域名对上了，但主页名称和清单名称没有共同词（如子公司的域名指向集团页）。可用 `names.names_unrelated` 判断 |
| `thin_page` | 员工数 ≤ 1 且没有 website，或 description 少于 20 个词 |
| `query_used` | 实际命中的搜索词（来自 `originalQuery.search`） |

### 3.4 人工队列

所有 `ambiguous` 写入 `linkedin_review_queue.csv`：`unit_id`、清单里的名称 / 域名 / 国家 / 城市、每个候选的 URL / 名称 / website / HQ 国家 / 城市。人工确认后才能进训练；未确认的不用。

匹配规则对所有单元一视同仁，不能因为是不是客户而不同（清单里本来也没有这个信息）。全量跑完后，本仓库会按客户 / 潜在客户分别统计匹配率，检查有没有系统性差异。

## 4. 本仓库收到后做什么

- 按 `unit_id` 合并标签；只用 `matched` 的单元训练。
- 用实际抓到的单元**重新计算** `sample_weight`（`lookalike.add_country_weights`），因为找不到的比例各国可能不同。
- description / tagline / specialties 统一用多语言向量模型处理（不同语言的同义文本落在同一位置），不用原文词袋、不用语言本身。
- 训练前做国家泄漏检查（`feature_policy.md`）。
