# 数据来源与已知问题

本仓库读四类数据：Snowflake 数据仓库的 Dolibarr marts（主数据）、Dolibarr REST API（只读补充）、Apify 抓取的 LinkedIn 公司主页、HubSpot（联系人模型，计划中）。凭证位置见根目录 README。

## 1. Snowflake：Dolibarr marts

数据库 `UBI_DATAHUB_TEST`，schema `DBT__3_MARTS`。`pull.py` 按原始粒度整表拉取，存为 `data/raw/<snap>/*.parquet` 和 `manifest.json`，之后只读。

| 表 | 粒度 | 主要用途 |
|---|---|---|
| `mart_orders_to_date` | 订单行 | 客户、金额、品类、产品；客户名单的基础 |
| `mart_invoicing_to_date` | 发票行 | 订单 vs 发票核对 |
| `mart_contracts_to_date` | 合同行 | 是否有合同 |
| `mart_product_catalog` | 产品（SKU） | 产品名称（业务线判断） |
| `mart_third_parties` | 第三方档案 | 名称、国家、城市、SIREN、客户 / 潜在客户 / 供应商 / 集团内部标记 |
| `mart_supplier_orders_to_date` | 采购订单行 | 判断客户是否也是供应商 |
| `mart_revenues_per_customer` | 客户 × 期间 | 目前未使用 |
| `mart_element_links` | 单据关联 | 目前未使用 |

### 已知问题

| 问题 | 影响 | 处理 |
|---|---|---|
| 订单的 `CUSTOMER_ID` 是 32 位哈希。部分客户恰好等于 md5(THIRD_PARTY_ID)，其余是把多个第三方归并在一起的未知键 | 不能直接对到第三方档案 | **禁止** `CUSTOMER_ID = THIRD_PARTY_ID`。优先用 Dolibarr API 查订单实际开票的第三方（socid），查不到再按名称匹配 |
| `ENTITY_ID` 对应法人：1 = Ubi Solutions、2 = Page Up、3 = Ubi Smart、5 = Ubi Impact | | `companies.ENTITY_ID_TO_NAME` |
| Page Up / Ubi Smart / Ubi Impact 的订单从 2023–2024 年才进数据仓库 | 只在这几个法人下单的客户，首单日期和活跃年数可能偏短；2024 年起新客户数的跳升部分是数据原因 | 标记 `history_truncated`；价值档位里记为 `truncated` |
| 集团内部公司（`IS_INTERCOMPANY`）也作为「客户」出现在订单里 | 金额虚高 | 全部订单都开给内部公司的客户排除；部分开给内部公司的，扣掉那部分订单 |
| `ITEM_CATEGORY` 分不开 BLE 定位和 RFID：「Traceurs et objets connectés」里大部分是 RFID 纺织标签 | 不能按品类判断业务线 | 用 Dolibarr 产品标签 + 产品名称规则（`product_lines.py`） |
| NAF 字段（`SECTION`…`CLASSE`）只有名称、没有代码，只覆盖约 292 个客户，几乎都在法国 | 不能当模型特征（会变成国家代理变量） | 只用于分析 |
| 档案的 `SIREN` 列混有 SIREN、SIRET 和外国税号 | | 原样保留，用的时候自己校验位数 |
| 档案名有时带内部编码（`FR01 FAURECIA …`），订单上的客户名有时是归并出来的标签（`S Transport` 实际是 BOVIS Transport） | 搜索用的名字不对 | `lookup_name` 优先用开票档案名；两者无关时 `lookup_name_conflict=true`，两个都搜 |

## 2. Dolibarr REST API（只读）

只用 GET。请求头 `DOLAPIKEY`，按法人加 `DOLAPIENTITY`（1 / 2 / 3 / 5）。API 用户是管理员账号，所以代码里**没有任何写操作的方法**。

| 模块 | 接口 | 取什么 | 输出 |
|---|---|---|---|
| `erp_socid.py` | `GET /orders`（分页） | 订单 id、编号、socid、法人 | `erp_orders.csv`、`erp_order_socid.csv` |
| `erp_thirdparties.py` | `GET /thirdparties`、`GET /contacts` | 名称、SIREN、网站、公司邮箱**域名**、联系人邮箱**域名**及次数、员工数档位 | `erp_thirdparties.csv` |
| `product_lines.py` | `GET /categories?type=product`、`GET /categories/{id}/objects` | 产品标签及其产品 | `erp_product_tags.csv` |

### 已知问题

- **API 实例和数据仓库的来源从 ORDER_ID ≈ 9704（2026 年 9 月初）开始不一致**：较新的订单在 API 里缺失或编号不同。只有订单 id **和**编号都一致时才采用 API 返回的 socid（8,860 张里 8,408 张）；哪个实例是生产环境未经 IT 确认。
- 联系人在各法人下返回的是同一批，按 id 去重。
- 产品标签接口在法人 2（Page Up）和 5（Ubi Impact）返回 401；目前看到的标签都属于 Ubi Solutions。
- GPSBLE 标签大约 2024 年起才有，老的定位产品没有标签。
- 我们自己的员工常被挂成客户的联系人：`ubisolutions.net`、`pageup.fr` 等集团域名一律不当作客户域名。

### 个人数据

联系人的姓名、完整邮箱、电话、个人 LinkedIn **只在内存里使用，不写入任何文件**；只保留邮箱的域名和出现次数。

## 3. LinkedIn（Apify）

- actor：`harvestapi/linkedin-company`，输入 `{"searches": [...]}`（按名称搜，返回第一条）或 `{"companies": [url, ...]}`。
- 只抓公司主页，不抓个人资料。
- 试点实测按返回条数计费，约 $0.0012 / 条；搜不到不收费。
- 名称搜索的第一条经常是同名外国公司、集团页或工会页，匹配规则见 `docs/labeling/linkedin_scrape_contract.md` 第 3 节。

## 4. HubSpot（计划中，联系人模型）

web app 已有只读集成（`~/web_app_refactoring/backEnd/src/services/hubspot/`）：读取 contacts / companies / deals 及其关联，按邮箱和 `lemlistlinkedinurl` 把人匹配到 HubSpot 联系人。用到的字段包括：

- 联系人：`email`、`jobtitle`、`lifecyclestage`、`hs_lead_status`、`notes_last_contacted`、`num_associated_deals`、`hubspot_owner_id`、`lemlistlinkedinurl`
- 交易：`dealstage`、`closedate`
- 公司：`name`、`domain`

web app 还有一个只读的字段探查工具（`field_probe.py`），只记录字段名、枚举值和填充数量，不记录个人信息。联系人模型的第一步就是用它确认哪些字段有数据，见 `docs/models/contact_model.md`。

注意：web app 自己也会往 HubSpot 写公司和联系人，所以 HubSpot 里有一部分记录本身就是 web app 筛选出来的。
