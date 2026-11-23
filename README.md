# analyse_dolibarr_client

从 Dolibarr 的历史订单出发，搞清楚**我们的客户是谁、买了什么**，再据此训练模型，给 web app（Sales Intelligence Workbench，`~/web_app_refactoring`）找到的公司和联系人打分。

## 做什么

| 阶段 | 产出 | 状态（2026-11-20） |
|---|---|---|
| 1. 客户名单 | 有过客户订单（CO）的公司名单、订单 / 品类 / 业务线分析、README 报告 | 完成 |
| 2. 公司 lookalike 模型的标签与样本 | 客户类型标注表、样本单元（正样本 / 未标注）、国家权重和国家系数、业务线标签 | 完成；P1 客户类型待人工复核 |
| 3. LinkedIn 特征 | 公司主页抓取（Apify）、人工匹配队列 | 进行中 |
| 4. 公司模型训练与打分 | 总模型 + 业务线分配模型、模型文件、打分 CLI | 计划中（分支 `lookalike-training`） |
| 5. 接入 web app | 打分服务或批量交换、销售结果回流 | 计划中 |
| 6. 联系人（contact）模型 | 基于 HubSpot 联系人数据的分类 / 打分模型 | 计划中 |

## 文档

| 文档 | 内容 |
|---|---|
| [docs/data_sources.md](docs/data_sources.md) | 数据来源、凭证位置、已知的数据坑 |
| [docs/models/company_lookalike.md](docs/models/company_lookalike.md) | 公司模型：目标、标签、结构、技术、验证、使用与运维 |
| [docs/models/contact_model.md](docs/models/contact_model.md) | 联系人模型的规划（HubSpot） |
| [docs/labeling/feature_policy.md](docs/labeling/feature_policy.md) | 公司模型的特征规范、业务线、国家处理、上线前检查 |
| [docs/labeling/customer_type.md](docs/labeling/customer_type.md) | 客户类型人工标注指南 |
| [docs/labeling/linkedin_scrape_contract.md](docs/labeling/linkedin_scrape_contract.md) | LinkedIn 抓取的输入 / 输出 / 匹配规则 |
| [docs/decisions.md](docs/decisions.md) | 决策记录（谁、何时、为什么） |
| `docs/handoff/` | 交给其他 agent 的任务说明 |
| `data/processed/<snapshot>/README.md` | 每次构建自动生成的客户名单分析报告（不在 git 里） |

## 安装

```bash
uv sync
uv run pytest -q
```

Python ≥ 3.11。依赖由 `uv` 管理（`pyproject.toml` / `uv.lock`）。

## 凭证（只写位置和变量名，值永远不进本仓库）

| 用途 | 位置 | 变量 |
|---|---|---|
| Snowflake 数据仓库（只读） | 本仓库 `.env`（模板 `.env.example`） | `SNOWFLAKE_*`、私钥 `.p8` 路径 |
| Dolibarr REST API（只读 GET） | `~/Projects/internal-agent-hub/dolibarr-mcp/.env` | `DOLIBARR_URL`、`DOLIBARR_API_KEY`、`DOLIBARR_SSL_VERIFY` |
| Apify（LinkedIn 公司主页） | `~/web_app_refactoring/backEnd/.env` | `APIFY_TOKEN` |
| HubSpot（联系人模型，计划中） | `~/web_app_refactoring/backEnd/.env` | `HUBSPOT_PRIVATE_APP_TOKEN` |

代码只在运行时读取这些文件，不打印、不复制、不写入任何输出。

## 流水线

按顺序执行，`<snap>` 是快照日期（如 `2026-11-18`）。

```bash
# 1. 从 Snowflake 拉快照到 data/raw/<snap>/（只读，之后不再修改）
uv run python -m analyse_dolibarr_client.pull --snapshot <snap>

# 2. Dolibarr API（只读）：每张订单实际开票的第三方
uv run python -m analyse_dolibarr_client.erp_socid --snapshot <snap> --env-file ~/Projects/internal-agent-hub/dolibarr-mcp/.env

# 3. Dolibarr API（只读）：第三方的网站、邮箱域名、联系人邮箱域名（只存域名）
uv run python -m analyse_dolibarr_client.erp_thirdparties --snapshot <snap> --env-file ~/Projects/internal-agent-hub/dolibarr-mcp/.env

# 4. Dolibarr API（只读）：产品标签（区分业务线）
uv run python -m analyse_dolibarr_client.product_lines --snapshot <snap> --env-file ~/Projects/internal-agent-hub/dolibarr-mcp/.env

# 5. 客户名单 + 分析报告
uv run python -m analyse_dolibarr_client.companies --snapshot <snap>

# 6. 公司模型的标签、样本单元、国家系数、客户类型标注表
uv run python -m analyse_dolibarr_client.lookalike --snapshot <snap>

# 7. LinkedIn 抓取清单
uv run python -m analyse_dolibarr_client.scrape_list --snapshot <snap>

# 8. LinkedIn 抓取（Apify，按条收费；先 --pilot）
uv run python -m analyse_dolibarr_client.linkedin_scrape --snapshot <snap> --pilot

# 9. 训练与打分（计划中，见 docs/models/company_lookalike.md）
```

第 2–4 步的结果缺失时，第 5 步会退回到只用名称匹配 / 名称规则，并在报告里说明。

## 输出（都在 `data/` 下，已 gitignore）

| 路径 | 内容 |
|---|---|
| `data/raw/<snap>/` | Snowflake 快照（parquet），只读 |
| `data/processed/<snap>/companies.parquet/.csv` | 客户名单（一行一个 CUSTOMER_ID） |
| `data/processed/<snap>/README.md` | 自动生成的分析报告 |
| `data/processed/<snap>/{unmatched,duplicates,issues,orders_by_*,category_cooccurrence}.csv` | 辅助表 |
| `data/processed/<snap>/erp_*.csv` | Dolibarr API 只读结果 |
| `data/processed/<snap>/labeling/` | 标注表、样本单元、国家系数、抓取清单、LinkedIn 结果、人工队列 |
| `data/models/`（计划中） | 模型文件、向量缓存 |

## 规则

- `data/`、`.env`、任何密钥都不进 git。
- `data/raw/` 只读；所有输出写到 `data/processed/` 或 `data/models/`。
- Dolibarr API 只用 GET，不写任何东西。
- 订单的 `CUSTOMER_ID` 是哈希，**禁止**和 `THIRD_PARTY_ID` 直接连接（见 `docs/data_sources.md`）。
- LinkedIn 只抓公司主页，不抓个人资料；联系人数据只按 `docs/models/contact_model.md` 的规则处理。
- 疑似集成商只标记，不删除；名单里不做主观打分，打分由模型完成。
