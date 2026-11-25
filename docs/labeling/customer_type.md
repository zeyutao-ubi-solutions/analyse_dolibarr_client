# 标注指南：客户类型（customer_type）

用于 lookalike（ICP 相似度）模型：只有 **终端用户** 进正样本。集成商、经销商、同行如果混进正样本，模型会学成「找集成商」。

- 标注表：`data/processed/<snapshot>/labeling/customer_type_labels.csv`（UTF-8 BOM，可直接用 Excel 打开）
- 重新生成：`uv run python -m analyse_dolibarr_client.lookalike --snapshot <snapshot>`
  - 只刷新上下文列、补上新客户；**已填写的标注列不会被覆盖**，旧文件会先备份到 `labeling/history/`。
  - 填了不合法的值会报错并列出行号，不会静默忽略。

## 要填的列

| 列 | 取值 | 说明 |
|---|---|---|
| `customer_type` | 见下表 | 必填；拿不准就填 `unsure`，不要猜 |
| `confidence` | `high` / `medium` / `low` | |
| `evidence_url` | URL | 判断依据：官网「关于我们」、LinkedIn 主页、societe.com 等 |
| `annotator` | 姓名缩写 | |
| `labeled_at` | `YYYY-MM-DD` | |
| `comment` | 自由文本 | 尤其是 `unsure` 时写明卡在哪 |

其余列（`priority`、`suggested_type`、金额、品类、`notes`…）是参考信息，不要改。

## customer_type 取值

| 值 | 定义 | 例子 / 线索 |
|---|---|---|
| `end_user` | 自己使用我们的产品/服务（洗衣厂、物流仓、工厂、医院、酒店、零售…） | `GEODIS LOGISTICS`、`ILUNION TEXTIL` |
| `integrator_reseller` | 买来转卖或集成给自己的客户：IT 集成商、经销商、系统商、方案商 | 名字含 SYSTEMS / INFORMATIQUE / DISTRIBUTION 且业务是 IT；订单名是另一家公司（`lookup_name_conflict`）；同时是我们的供应商 |
| `competitor` | 和我们卖同类 RFID / IoT / 追溯方案的公司 | 官网主营 RFID 标签、读写器、追溯软件 |
| `intercompany` | 集团内部公司（Ubi Solutions、Page Up、Ubi Smart、Ubi Impact 及其子公司） | 通常已自动排除；漏网的标这里 |
| `not_a_company` | 个人、测试账户、内部占位客户 | 「DIVERS」「CLIENT TEST」、个人姓名 |
| `unsure` | 查了仍无法判断 | 视同未标注，按 `suggested_type` 处理 |

判断规则：

1. **看他们拿我们的东西干什么，不看他们是谁。** 大集团的 IT 子公司如果是给集团自己用，算 `end_user`。
2. **订单名和档案名不同（`order_name_differs`）时**，档案名是开票方：
   - 开票方是 IT/方案公司、订单名是终端客户（`EXERTIS AZENN` 开票、订单名「Orange」）→ `integrator_reseller`
   - 只是品牌名 vs 法定名（`SECANETA` → JOSÉ ALBERO PUERTO）或集团 vs 子公司（`S Transport` → BOVIS Transport）→ `end_user`
3. **同时是供应商（`also_supplier`）** 不等于集成商：我们也会向客户采购服务。看主营业务。
4. 混合型（既自用又转卖）按金额大的那部分判断，`comment` 写明。

## 先标哪些

按 `priority` 排序，从上往下：

- **P1**：疑似集成商、同时是供应商、订单名和档案名不同 —— 最可能不是终端用户，必须人工看
- **P2**：金额前 90% 的客户，或域名和公司名对不上
- **P3**：其余 —— 默认按 `suggested_type`，抽样检查即可

## 质量控制

- 正式开始前，两个人独立标同一批 **P1 全部 + P2 随机 30 条**，计算一致性（Cohen's kappa）。低于 0.7 先对齐规则、更新本指南，再继续。
- 之后每 200 条随机抽 10% 交叉复核。
- 规则有变化时更新本文件，并在 `comment` 里注明受影响的行。
