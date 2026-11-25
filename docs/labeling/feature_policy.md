# 特征规范：lookalike 模型

模型回答的问题：**只看一家公司在 LinkedIn 上的公开信息，它像不像我们的终端客户？**
样本和标签见 `lookalike.py` / `lookalike_units.csv`；本文件规定哪些信息可以进特征。

## 原则

1. **特征只来自 LinkedIn 公司主页。** Dolibarr 里的订单、金额、品类、价值档位只能当标签或分析用，绝不能当特征——潜在客户没有这些数据，用了就是泄漏。
2. **国家不是特征，国家的代理变量也不是。** 正样本 81% 在法国，未标注样本以西班牙、法国、德国、波兰为主；任何能推出国家的字段都会让模型学成「是不是法国公司」。
3. **不能用来识别具体公司的信息不进特征**（名称、域名、URL），否则模型会背答案。

## 可以用

**主特征是公司简介（About / description）**：LinkedIn 行业字段由公司自己选，常常不准或太宽泛，只作辅助。

| LinkedIn 字段 | 地位 | 处理方式 |
|---|---|---|
| About / description（简介） | **主特征** | 多语言向量模型（同义不同语言的文本落在同一位置），或先统一翻译成英文再向量化；不能用原文词袋、字符 n-gram 或语言本身 |
| Tagline、Specialties（专长） | 辅助文本 | 和简介同样处理，可拼进同一段文本或单独向量化 |
| Industry（行业） | 辅助 | 类别特征，用 LinkedIn 英文行业代码；不准时由简介纠正，不单独决定结果 |
| Company size / Employees on LinkedIn | 辅助 | 有序类别 / log 变换 |
| Company type（上市 / 私营 / 政府 / 非营利…） | 辅助 | 类别 |
| Founded（成立年份） | 辅助 | 数值；缺失单独编码 |
| Followers | 辅助 | log 变换 |
| 地点数量 | 辅助 | 只用**数量**，不用地点本身 |
| 是否有关联页面 / 母公司 | 辅助 | 布尔 |

简介为空或很短（例如少于 20 个词）的公司单独标记：它们的分数主要来自辅助特征，可信度低，web app 里应提示。

NAF / NAICS 等官方行业代码不进模型（只有部分国家有，会成为国家代理变量）；它们以后可以用于给销售看的行业分组和按行业评估。

## 禁止使用

| 字段 | 原因 |
|---|---|
| Headquarters 国家、城市、地区、邮编 | 直接就是国家 |
| Locations 列表 | 同上 |
| 网站域名、顶级域（.fr / .es / .de） | 国家代理；也会记住具体公司 |
| 简介 / 专长的**语言**、原文词袋、字符 n-gram | 语言 = 国家 |
| 公司名称及名称中的词（FRANCE、ESPAÑA、GmbH、SAS、S.L.） | 国家代理 + 记住公司 |
| 法律形式 | SAS/SARL vs S.L. vs GmbH 就是国家 |
| 电话、地址 | 国家代理 |
| 员工的地点 / 学校 | 国家代理 |
| Dolibarr 任何字段（金额、品类、`value_tier`、`country_code`、`web_domain_source`…） | 泄漏 |

`lookalike_units.csv` 里的 `country_code`、`country_bucket` 只用于加权和评估，不进模型。

## 加权

`sample_weight`：正样本 = 1；未标注样本按国家桶重新加权，使加权后的未标注样本国家分布与正样本相同（正样本少于 10 个的国家合并为 `other`）；`excluded` = 0。
训练时把它传给模型的 `sample_weight`。代价：未标注样本的有效样本量从 8,648 降到约 2,900，法国潜在客户的权重最高。

## 国家怎么进入排序：国家系数

国家确实影响成交（距离、安装、销售覆盖），但它**不进模型**，而是在模型之外单独相乘：

```
优先级 = 模型分（只看画像，不看国家） × country_factor
```

- 系数表：`data/processed/<snapshot>/labeling/country_factors.csv`，每个国家一行；`lookalike_units.csv` 的 `country_factor` 列已按国家填好。
- `historical_rate` = 正样本单元 / （正样本 + 未标注单元），附 95% Wilson 区间。它同时包含「真的难卖」和「没怎么去卖」（例如批量导入、从未跟进的名单），**只能当起点**。
- `suggested_factor` = 平滑后的比率 / 法国比率。正样本少的国家会被拉向「法国以外所有国家的合计比率」（20 个虚拟样本的先验），避免 1/3 就算成 33%。
- 在 `manual_factor` 填数字即可覆盖（`manual_note` / `set_by` / `set_at` 记录理由和人），**重跑不会覆盖**，旧文件备份在 `labeling/history/`；填了非数字或负数会报错。`factor_source` 说明最终用的是 manual、suggested 还是 missing。
- `unknown`（国家缺失）没有建议值：客户一定有国家，缺国家的只有潜在客户，0% 是数据造成的。先补国家，或人工给一个系数。

调整策略（例如决定重点开拓西班牙）只需改 `manual_factor`，不用重新训练模型。

## 产品线（业务线）

业务范围（2026-11-20 确认）：**硬件 + 软件**。

| 业务线 | id | 包含 |
|---|---|---|
| Géolocalisation / Connected Things | `geoloc` | BLE / GPS / LoRa 追踪器、信标、网关及其租赁；Connected Things 是定位的软件平台，和定位是同一条线 |
| Traçabilité | `rfid` | RFID 标签、读写器 / 天线、门禁 / 隧道、RFID 终端套件 |
| Ubi Cloud | `ubi_cloud` | Ubi Cloud 订阅 / 许可（产品名含 UBI Cloud，含「Ubi Cloud IoT」） |

web app 原来按产品目录（marketing 的行业 / 产品包装）分类，已确认不再使用，改用这三条业务线。

产品线是**标签维度，不是特征**——潜在客户还没买过东西。

### 模型结构：总模型 + 分配模型（2026-11-20 确定）

```
第 1 步  总模型（PU）     这家公司像不像我们的客户？        → fit_overall
第 2 步  分配模型（多标签） 如果它是客户，会买哪几条业务线？  → p_geoloc, p_rfid, p_ubi_cloud

某条线的分数 = fit_overall × p_该线
排序优先级   = fit_overall × country_factor（按线排序时再乘 p_该线）
```

| 模型 | 训练数据（`lookalike_units.csv`） | 标签 | 权重 |
|---|---|---|---|
| 总模型 | `label` 为 positive 或 unlabeled | positive = 1，unlabeled = 未标注（PU） | `sample_weight`（国家平衡） |
| 分配模型 | `in_allocation_set=true`（买过至少一条线的客户单元） | `positive_geoloc` / `positive_rfid` / `positive_ubi_cloud`，可同时为真 | 不加国家权重（只在客户内部比较） |

为什么不是每条线一个 PU 模型：定位 204、Ubi Cloud 135 个正样本单独训练噪音大；Ubi Cloud 几乎都和硬件一起买，单独的 PU 模型会学成「是不是买硬件的客户」。分配模型三条线共用同一批客户，只在客户内部比较，学的是「哪类客户买哪条线」。

前提：「像不像客户」和「买哪条线」可以分开判断。现有客户群里没有的全新行业，这套方法（以及任何只从历史客户学习的方法）都找不出来。

### 用法

- **找新客户**：按 `fit_overall × country_factor` 排序；`p_*` 告诉销售推哪条线。
- **交叉销售**：对已买某条线的客户，看分配模型给其他线的 `p_*`（例如 RFID 老客户里 `p_geoloc` 高的）。分配模型评估时用交叉验证的预测值，避免在训练过的客户上自我验证。
- **评估分配模型**：按 `split_group` 做 GroupKFold，每条线报告 AUC / 平均精度；Ubi Cloud 正样本少（135），指标波动会比较大。

### 其他说明

- 判断规则：Dolibarr 产品标签优先（`UBI Solutions > GPSBLE` → 定位；`Portique RFID` / `Kit RFID TC21` / `Terminaux RFID` → RFID），否则按产品名称 / 子品类 / 制造商规则（`geoloc_source=name_rule`）。GPSBLE 标签大约 2024 年起才有，老的 LoRa / GPS 追踪器只能靠规则。
- 定位正样本大多是 2025–2026 年的小额试点，`p_geoloc` 学到的是「哪类客户愿意试定位」，不一定是「会大规模部署」。Ubi Cloud 绝大多数和硬件一起买，`p_ubi_cloud` 的含义是「哪类客户会加购 Ubi Cloud」。
- 三条线都没买的客户单元（只买项目、维护、终端、第三方软件如 SOTI）只进总模型。

## 上线前必须做的检查

1. **国家泄漏检查**：用同一套特征训练一个分类器去预测 `country_bucket`。准确率明显高于「全猜 FR」的基线，说明还有代理变量漏进来，要找出来去掉。
2. **分国家评估**：除了整体指标，单独报告 FR 和 ES 的指标（各自国家内部的排序能力）。只有整体好、国家内部差，说明模型还在按国家排序。
3. **按集团切分**：交叉验证用 `split_group` 做 GroupKFold，同一域名的子公司不能同时出现在训练集和测试集。
4. **按时间验证**：另外用 `cohort_year <= 2024` 的正样本训练，看 2025–2026 年新客户能否排在潜在客户前面。注意 2024 年起 Page Up / Ubi Smart / Ubi Impact 的数据才进数仓，这一年的跳升部分是数据原因。
