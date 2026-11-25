# 交接：在本仓库执行并监控 LinkedIn 公司主页抓取（Apify）

## 背景

仓库：`/Users/zeyutao/Projects/analyse_dolibarr_client`（uv + pandas + pytest，`pythonpath=["src"]`）。
我们在做 lookalike 模型：只看 LinkedIn 公司主页，判断一家公司像不像我们的终端客户（总模型 + 业务线分配模型）。标签和样本已经准备好，**缺的是 LinkedIn 特征**，这是你的任务。你只负责抓取和存储，**不要训练模型**。

开始前先读：

1. `docs/labeling/linkedin_scrape_contract.md` —— 输入清单、输出字段、匹配规则（**以它为准**）
2. `docs/labeling/feature_policy.md` —— 哪些字段是特征、哪些只用于核对
3. `src/analyse_dolibarr_client/scrape_list.py` —— 清单怎么生成的
4. 参考（**只读，不要修改**）：`~/web_app_refactoring/backEnd/src/integrations/apify/linkedin_company_details_scraper.py`、`~/web_app_refactoring/backEnd/src/workflows/shared/validate_company/scrape_output.py`（web app 怎么调用同一个 actor、怎么解析返回）

## 任务

对 `data/processed/2026-11-18/labeling/linkedin_scrape_list.csv` 里的单元（`batch=main` 共 3,276 个，`batch=reserve` 140 个备用），用 Apify actor **`harvestapi/linkedin-company`** 抓 LinkedIn 公司主页，原始结果和整理后的结果都存到本地。

## 必须遵守

- **token**：运行时从 `~/web_app_refactoring/backEnd/.env` 读 `APIFY_TOKEN`。不要打印、复制、写进任何文件或日志、提交到 git；不要放进 URL 查询参数（用 `Authorization: Bearer` 头或 apify-client）。
- **不修改** `~/web_app_refactoring` 的任何文件。
- **只抓公司主页**，不抓员工、联系人、帖子；不用任何人的 LinkedIn 登录 cookie。
- **不要引入标签**：清单里没有「是否客户」，匹配阶段（包括任何 LLM 判断）也不能去读 `lookalike_units.csv` 的 `label`。
- **数据只放 `data/` 下**（已 gitignore）。代码放 `src/analyse_dolibarr_client/`，测试放 `tests/`。不要提交 `data/`、`.env`、任何密钥。
- **先试点，再全量**：见下面「步骤」。全量运行前必须停下来等用户确认。

## 步骤

### 1. 写抓取模块

`src/analyse_dolibarr_client/linkedin_scrape.py`（CLI：`uv run python -m analyse_dolibarr_client.linkedin_scrape ...`）：

- 读取抓取清单；按批次调用 actor（建议每次 run 25–50 个搜索，同时最多 1–2 个 run，参数可配置）。
- 输入：有 `web_domain` 时可先试 `{"searches": [search_name]}`，再用返回的 `website` 域名核对；搜不到或域名不一致时依次试 `alt_search_names`。拿到主页 URL 后需要补详情时用 `{"companies": [url]}`。实际返回格式以试点结果为准，必要时调整。
- **可续跑、幂等**：维护进度文件，记录每个 `unit_id` 的状态；重跑时跳过已完成的，除非显式要求重抓。每批结束都落盘。
- 失败 / 超时最多重试 2 次，之后记为 `error` 并继续。
- 依赖：可以 `uv add apify-client`，也可以用标准库调用 Apify REST API。
- 测试：mock Apify，测试里不能访问网络。覆盖：域名匹配、名称匹配、ambiguous、续跑跳过已完成、token 不出现在任何输出里。

### 2. 本地存储（都在 `data/processed/2026-11-18/labeling/linkedin/` 下）

| 文件 | 内容 |
|---|---|
| `raw/<apify_run_id>.jsonl` | 每个 Apify run 的 dataset 原样保存，不改字段 |
| `runs.csv` | 每个 run：run_id、dataset_id、输入的 unit_id 列表、状态、开始 / 结束时间、条数、费用（Apify 返回的 usage） |
| `progress.csv` | 每个 unit_id：状态、尝试次数、最后错误 |
| `scrape.log` | 进度日志（不含 token） |
| `../linkedin_companies_<YYYY-MM-DD>.csv` | 按约定整理的结果，每个 unit_id 一行，字段见约定第 2 节 |

### 3. 试点（必做，然后停下）

从 `batch=main` 取 20 个单元：有域名和无域名各约一半，至少包含几个非法国单元。跑完后**停下来向用户汇报**：

- 匹配结果：matched / not_found / ambiguous / error 各多少；其中 `match_method=domain` 的比例
- 返回字段的实际情况：description、industry、员工数、website 等字段的覆盖率；返回格式和约定不一致的地方
- 抽 5 个 `name_country` 匹配给用户人工看对不对
- **费用和时间**：每家公司的实际费用、每批耗时，以及全量 3,276 个的预计总费用和总时长

用户确认后再跑全量。

### 4. 全量运行和监控

- 后台运行；定期汇报进度：已完成 / 总数、各状态数量、累计费用、预计剩余时间。
- 发现以下情况就暂停并汇报：错误率连续一批超过 20%；累计费用超过试点估算的 1.5 倍；Apify 返回限流 / 额度不足。
- `main` 跑完后，按国家统计 `not_found` 率。某个国家 `not_found` 超过 15% 时，从 `batch=reserve` 里**同一国家**的单元补抓，数量约等于缺口。

### 5. 收尾

- 生成 `linkedin_companies_<YYYY-MM-DD>.csv`，并写一份简短汇总：总数、各 `match_status` / `match_method` 数量、按 `country_code` 的匹配率、字段覆盖率、总费用。
- 跑 `uv run pytest -q`，全部通过。
- 在当前分支提交代码和测试（不含 `data/`），提交说明写清楚做了什么；不要 push。
- 汇报：结果文件路径、汇总、遗留问题（例如 ambiguous 需要人工判断的数量）。
