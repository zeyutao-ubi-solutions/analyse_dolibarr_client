# 公司业务打分（activity scorer）

> 状态（2026-11-25）：第一版已训练，经过两轮审查修订，又按 2026-11-25 的改进分析加入了 LinkedIn 行业、把 other 拆成 5 个子标签、把门槛调到 0.65（报告都在 `data/processed/2026-11-18/scores/review_2026-11-24/`），模型文件在 `data/models/activity/2026-11-25/`。代码是 `src/analyse_dolibarr_client/activity.py`。
> 它取代 lookalike PU 模型成为主打分方式。PU 模型回答的是「谁会成交」，不是用户要的问题（见 `docs/decisions.md` 2026-11-23）。

## 1. 要回答的问题

**这家公司是做什么的？它的业务和我们的目标细分有多契合？**

- 只看 LinkedIn 简介。**国家永远不参与打分**，销售自己按国家筛选。
- 输出两样东西，分开给：
  - **匹配度 `fit`**：是否属于 37 个目标细分之一的终端用户，以及属于哪个细分。
  - **优先级 `priority`**：`low` 只表示销售可以晚点联系，**从不排除**。规则见第 5 节。

## 2. 模型

| 环节 | 做法 |
|---|---|
| 文本 | `passage: ` + 简介前 1,500 个字符。LinkedIn 自动生成的模板简介（「X is a … company [based out of 地址, 城市, 国家]」）改写成「This organisation is a {行业} company.」，公司名、地址和国家都去掉 |
| 向量 | `intfloat/multilingual-e5-large`（fastembed，本机 ONNX），权重在 `data/models/fastembed/` |
| 向量缓存 | `data/models/embedding_cache/activity_e5large.npz`，按 sha256(模型名 + 文本) 存。训练和打分用同一套文本函数 |
| 分类器 | 一个多项逻辑回归，C=30，共 47 类：37 个细分（`docs/segments/segments_v2.csv`）加 10 个非 prospect 标签：consulting、supplier、competitor、school、media、other，以及 other 的 5 个子标签（见下）。`insufficient_info` 训练样本只有 6 个，已并入 other |
| other 子标签 | 第二次三模型投票（多数票）：`other_sector_body`（协会、联合会、产业集群、认证机构、旅游推广机构）、`other_investor_owner`（基金、控股、地产业主）、`other_sector_vendor`（给目标行业卖软件或服务）、`other_single_small_site`（单店、小场所）、`other_unrelated`（其他无关）。这些「属于目标行业但不运营它」的组织，正是最常被误判成 prospect 的一类 |
| 行业特征 | LinkedIn 行业的 one-hot（训练中出现 ≥5 次的 87 个行业，旧行业名先映射到新名称），取值 0.3，和文本向量拼在一起。训练时每条有行业的数据再加一份去掉行业的副本（权重减半），这样没有行业的页面也能正常打分。行业不是国家代理变量 |
| 样本权重 | 类别平衡 × **语言系数**：让每种简介语言里 prospect 的比例都等于整体比例。语言只用来定权重，不是特征 |
| `fit` | 37 个细分类别的概率之和 |
| `label` | `fit ≥ 0.65` 时为 prospect（这个门槛让交叉验证中 prospect 的召回率保持在约 0.95；0.5 会让 43% 的 other 被判成 prospect），否则取概率最高的非 prospect 标签。评估和上线用同一个函数 `decide`。模板简介一律记为 `template_only` |
| `segment` / `segment_prob` | prospect 前提下最可能的细分及其条件概率，另给第二候选。模板简介的细分只是候选，由 LinkedIn 行业按 `segments_v2.csv` 的 `linkedin_industries` 映射得到（旧行业名有别名表），没有概率；没有行业的模板页不给 `fit` |
| `sales_label` / `category` | 给销售看的四类：prospect / competitor / template_only / not_target，细标签保留在 `label`。`category` 是细分所属的 10 个大类之一，比细分更可靠（交叉验证中细分完全判对 84%，大类判对 90%） |
| 解释 | `similar_training_companies`：同一细分里和这家公司最相似的 3 家已标注公司。文本完全相同的那一家（就是它自己）跳过。只对 prospect 给出 |
| 训练过的公司 | `train --oof-out` 生成 5 折 out-of-fold 分数，`score --oof` 用它替换文本相同的公司的分数（`score_source = out_of_fold`），这些分数来自没见过这家公司的模型 |
| 一致性检查 | 模型里存了一段固定文本的向量，打分前用当前的向量模型重算一次，余弦相似度必须 ≥ 0.99 |
| 模型文件 | `model.npz`（纯数组，不用 pickle）+ `meta.json`（训练数据的哈希、类别和语言计数、评估结果） |

**`fit` 是排序分，不是校准过的概率**，整体偏高：潜在客户的中位数约 0.9。要设硬阈值，应按销售反馈的误报率来定。

## 3. 训练数据

全部在 `data/external/server_companies/2026-11-23/training_labels_2026-11-24/`（被 gitignore，有 README，脚本可复现）。

- **抽样**：
  - 服务器公司池，按原 LLM 标签分层抽 2,300 家；
  - 运输 / 设备租赁页 300 家；
  - Dolibarr 潜在客户 400 家；
  - 按关键词为 12 个弱细分补抽 486 家。
- **标注**：gpt-6.2-sol、claude-sonnet-5-5、claude-haiku-5-5 三个模型盲标，看的是公司名、行业、规模和简介，共花费约 12 美元。
- **训练行**（`training_rows`）：
  - 只用三票一致的行；
  - 去掉 LinkedIn 主页或简介与检验集（432 家客户）相同的行，客户只做检验；
  - 简介完全相同的行只留一行；
  - 模板简介不进训练，因为它们的投票依赖公司名。
  - 结果：**2,643 行，其中 prospect 1,639 行**。

## 4. 效果（`train_eval.py`，结果在 `train_eval_results.csv`）

| 检验集 | 规模 | AUC | 8 类准确率 | prospect 精确率 / 召回率 | 细分准确率 |
|---|---:|---:|---:|---:|---:|
| 交叉验证（原 3,000 家抽样中的干净行） | 2,266 | 0.979 | 0.88 | 0.95 / 0.95 | 0.84 |
| 审核集（6 个模型中 ≥5 票一致） | 167 | 0.976 | 0.85 | 0.90 / 0.92 | 0.87 |
| **三个模型 2 比 1 的行（没进训练）** | 735 | 0.782 | 0.51 | 0.56 / 0.77 | 0.57 |

8 类准确率在计算时，other 的子标签都算作 other。交叉验证中 other 的召回率是 0.75，supplier 是 0.64。客户检验集（432 家）：85% 被判为 prospect，细分与三模型多数票的一致率是 0.77。

**拆分 other 的效果**（`training_labels_2026-11-24/other_split/experiment_results.csv`，prospect 召回率固定在 0.95）：
- 交叉验证：prospect 精确率 0.937 → 0.949；other 被误判为 prospect 的比例 19.8% → 14.5%；
- 审核集：other 召回率 0.54 → 0.81；other 被误判为 prospect 的比例 31% → 15%。

另一种做法是训练时把非目标标签合并成一类，效果更差：prospect 精确率从 0.94 降到 0.89。所以只在给销售看的输出里合并。

**和只用文本、门槛 0.5 的版本相比**（`train_eval_results.csv` 里四组对照）：
- 8 类准确率：0.82 → 0.86；
- other 召回率：0.40 → 0.64；
- 细分准确率：交叉验证 0.80 → 0.85，审核集 0.77 → 0.85；
- 代价是 prospect 召回率从 0.99 降到 0.95，客户被判为 prospect 的比例从 91% 降到 86%。

改进分析时试过、但没有效果的办法：用三个模型的置信度做权重、用 2 比 1 的样本做软标签、两段式模型、kNN、MLP、不做类别平衡。审核集也参与了选 C（10 / 30 / 100），所以它不完全是独立的测试集。

**这些数字都偏乐观。** 前两组的「真值」也来自模型投票，而且只收了模型意见一致的「容易」样本。2 比 1 那组是难样本，在那里模型明显偏向判成 prospect。

**人工抽查的错误率估计：**
- 第一轮审查者抽查 52 家（修订前的模型）：细分错约 25%。其中 fit ≥ 0.9 的约 15%，fit 在 0.4–0.7 之间的约 50%。
- 第二轮抽查 42 家（第一轮修订后的模型），只看有正常简介、没进训练的公司：是否 prospect 错约 5–12%，细分错约 25–35%。

**已知的常见错误：**
- 行业协会和产业集群被判成 prospect；
- 卖给目标行业的技术厂商被归到客户所在的细分；
- 只有模板简介的公司，尤其是法文的洗衣房和医疗机构，细分常常判错；
- 零售电商和批发两个细分经常互相混淆。

**语言偏差：** 同为非 prospect，法语简介的 fit 平均比英语高。加了语言权重后，差距从 0.108 降到 0.072；再加入行业特征和 other 子标签后降到 0.033。剩下的差距主要来自样本来源：在同一来源（服务器池）里，差距只有 0.03。第二轮审查者控制类别和来源后，差距已经不显著；用 12 对法英对译文本测试，fit 平均只差 −0.007。

对比过的其他做法：
- TF-IDF 词袋：AUC 0.93，细分准确率 0.57，而且文本语言本身就是国家的代理变量；
- 两段式（先判 8 类再判细分）：略差；
- 直接和细分描述比相似度（零样本）：AUC 0.57，不可用。

## 5. 优先级规则

| 情况 | priority |
|---|---|
| label = prospect，而且细分是低优先级（研究机构） | low |
| 声明人数段 < 51，但 LinkedIn 成员数 ≥ 51（成员数只是下限，说明声明已过时） | normal |
| LinkedIn 声明的人数段下限 < 51 | low |
| 没有人数段，但关联成员数 ≥ 51（成员数只是下限，≥51 就能证明规模） | normal |
| 没有人数段，关联成员数 < 51，或什么都没有 | unknown_size |
| 其他 | normal |

人数段可以是 `51-200`、`1,001-5,000`、`10,001+`、`51_200`、`201_plus` 等格式。原因文字中法双语，输出列有 `declared_range_lower` 和 `linkedin_members`。

## 6. 使用

```bash
uv run python -m analyse_dolibarr_client.activity train \
  --labels data/external/server_companies/2026-11-23/training_labels_2026-11-24/labels.csv \
  --eval-results data/external/server_companies/2026-11-23/training_labels_2026-11-24/train_eval_results.csv \
  --out data/models/activity/2026-11-25 --oof-out data/models/activity/2026-11-25/oof_scores.csv

uv run python -m analyse_dolibarr_client.activity score \
  --model data/models/activity/2026-11-25 --oof data/models/activity/2026-11-25/oof_scores.csv \
  --input companies.csv --output scores.csv
```

- **输入**：需要 `description` 列；`employee_count_range`、`employee_count` 或 `employees` 用于定优先级。国家列即使有也不读。
- **输出**：`fit`、`label`、细分及其概率、`similar_training_companies`、`priority` 及原因、`thin_text`（少于 20 个词或是模板简介）、`template_text`。
- **速度**：本机 CPU 上每家约 0.6 秒，缓存里已有的文本不用重新生成向量。

潜在客户试用表：`data/processed/2026-11-18/scores/` 下的三个脚本：
- `build_prospect_input.py`：标记 `in_training`、`same_page_as_customer`、`same_page_units`；
- 用 `activity score` 打分；
- `build_activity_review.py`：生成给销售的表。

## 7. 下一步

- 用户核对审核表的红色行之后，用人工标签重新评估。
- 收回销售的反馈：定 `fit` 阈值，补充缺失的细分，补充协会和技术厂商作为负样本。
- 接入 web app：web app 后端没有机器学习库，可以只导出 `coef` / `intercept`（用 numpy 做矩阵乘法即可），向量服务另行部署。
- 细分清单变化时：重新标注受影响的行，再重新训练。`waste_management` 的定义在 2026-11-24 从「危险废物」改成了泛指废物处理，但现有标签是按旧定义标的。
