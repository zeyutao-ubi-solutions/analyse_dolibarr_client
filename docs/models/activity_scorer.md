# 公司业务打分（activity scorer）

> 状态（2026-11-24）：第一版已训练，模型文件在 `data/models/activity/2026-11-24/`。代码是 `src/analyse_dolibarr_client/activity.py`。
> 它取代 lookalike PU 模型，作为主打分方式；PU 模型回答的是「谁会成交」，不是用户要的问题（见 `docs/decisions.md` 2026-11-23）。

## 1. 要回答的问题

**这家公司是做什么的？它的业务和我们的目标细分有多契合？**

- 只看 LinkedIn 简介。**国家永远不参与打分**，销售自己按国家筛选。
- 输出两样东西，分开给：
  - **匹配度 `fit`**：是否属于 37 个目标细分之一的终端用户，以及属于哪个细分。
  - **优先级 `priority`**：员工少于 51 人或属于低优先级细分（研究机构）时为 `low`。`low` 只表示销售可以晚点联系，**从不排除**。

## 2. 模型

| 环节 | 做法 |
|---|---|
| 文本 | `passage: ` + 简介前 1,500 个字符，和标注模型看到的文本完全一样 |
| 向量 | `intfloat/multilingual-e5-large`（fastembed，本机 ONNX），权重存在 `data/models/fastembed/` |
| 分类器 | 一个多项逻辑回归，C=30，类别权重平衡。共 44 类：37 个细分（`docs/segments/segments_v2.csv`）加 7 个非 prospect 标签（other、consulting、supplier、competitor、school、media、insufficient_info） |
| `fit` | 37 个细分类别的概率之和 |
| `label` | prospect 和 7 个非 prospect 标签里概率最高的那个 |
| `segment` / `segment_prob` | prospect 前提下最可能的细分及其条件概率，另给第二候选 |
| 解释 | `similar_training_companies`：同一细分里和这家公司最相似的 3 家已标注公司（括号里是余弦相似度） |
| 模型文件 | `model.npz`（数组，不用 pickle）+ `meta.json`（训练数据的哈希、类别计数、评估结果） |

**`fit` 是排序分，不是校准过的概率。** 因为类别权重平衡，37 个细分每个都加了权，`fit` 普遍偏高：客户里 96% 被判为 prospect，审核集上 0.5 阈值的精确率约 0.76。按 AUC 看排序很好；要设硬阈值时，应按销售能接受的误报率另行确定。

## 3. 训练数据

全部在 `data/external/server_companies/2026-11-23/training_labels_2026-11-24/`（被 gitignore，有 README，脚本可复现）：

- **抽样**：服务器公司池按原 LLM 标签分层 2,300 家，运输 / 设备租赁页 300 家，Dolibarr 潜在客户 400 家；另外按关键词为 12 个弱细分补了 486 家。排除了 200 家审核公司和我们自己的客户。
- **标注**：gpt-6.2-sol、claude-sonnet-5-5、claude-haiku-5-5 盲标，规则与审核用的 `guide.md` 相同。共花费约 12 美元。
- **只用三票一致的行**：一共 2,700 行，其中 prospect 1,682 行。在审核集上，三票一致的行与另一组更强的三个模型 100% 一致，2 比 1 的行只有 54% 一致。
- **客户（432 家）只做检验**，不进训练。

## 4. 效果（`train_eval.py`）

| 指标 | 值 |
|---|---:|
| 交叉验证 AUC（prospect 和非 prospect） | 0.969 |
| 交叉验证细分准确率（真 prospect） | 0.79 |
| 审核集 AUC（167 家，6 模型 ≥5 票一致） | 0.954 |
| 审核集 8 类准确率 / 细分准确率 | 0.80 / 0.77 |
| 客户判为 prospect | 96% |
| 客户细分与 LLM 投票一致 | 0.72–0.75 |

对比过的做法：
- TF-IDF 词袋：AUC 0.93，细分准确率 0.57，而且文本语言本身就是国家的代理变量；
- 两段式（先判 8 类再判细分）：略差；
- 直接和细分描述比余弦相似度（零样本）：AUC 0.57，不可用。

**审核集的「真值」也来自模型投票。** 用户人工核对完审核表里的 33 行红色之后，应该再验一次。

**仍然偏弱的细分：**
- it_asset_services：只有 11 个样本；
- specialty_retail_ecommerce 和 wholesale_distribution：两者边界本来就模糊。

## 5. 使用

```bash
# 训练（标签和向量已经准备好）
uv run python -m analyse_dolibarr_client.activity train \
  --labels data/external/server_companies/2026-11-23/training_labels_2026-11-24/labels.csv \
  --embeddings data/external/server_companies/2026-11-23/training_labels_2026-11-24/embeddings_e5large.npz \
  --eval-results data/external/server_companies/2026-11-23/training_labels_2026-11-24/train_eval_results.csv \
  --out data/models/activity/2026-11-24

# 打分：输入是 LinkedIn 公司表，至少要有 description
uv run python -m analyse_dolibarr_client.activity score \
  --model data/models/activity/2026-11-24 --input companies.csv --output scores.csv
```

- **输入**：需要 `description` 列；`employee_count_range`（优先）、`employee_count` 或 `employees` 用于定优先级。国家列即使有也不读。
- **规模**：优先用 LinkedIn 声明的人数段。`employee_count` 是关联到主页的成员数，会低估：按它算客户有 34% 不足 51 人，按人数段只有 19–20%。两个都没有时，优先级记为 `unknown_size`。
- **`thin_text`**：简介少于 20 个词，这时分数不可靠。
- **速度**：本机 CPU 上每家约 0.6 秒，432 家用了约 4 分钟。

## 6. 下一步

- 用户核对审核表的红色行之后，用人工标签重新评估。
- 按销售可接受的误报率定 `fit` 阈值。
- 接入 web app：web app 后端没有机器学习库，可以只导出 `coef` / `intercept`（numpy 矩阵乘法即可），向量服务另行部署。
- 细分清单有变化时：重新标注受影响的行，再重新训练。
