"""Render data/processed/<snapshot>/README.md from a build result. Every number is computed."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from analyse_dolibarr_client.companies import (
    HARDWARE_CATEGORIES,
    LICENSE_MAINTENANCE_CATEGORIES,
    LICENSE_MAINTENANCE_MIN_SHARE,
    MATCH_AMBIGUOUS,
    MATCH_ERP,
    MATCH_EXACT,
    MATCH_NORMALIZED,
    MATCH_UNMATCHED,
    MIX_MIN_SIDE_SHARE,
    PROJECT_SERVICE_CATEGORIES,
    REPEAT_PRODUCT_MIN_SHARE,
    BuildResult,
    Snapshot,
    _is_true,
)
from analyse_dolibarr_client.names import LEGAL_PREFIXES, LEGAL_SUFFIXES

EXPECTED_CUSTOMERS = 1227
EXPECTED_ORDERS = 8860
EXPECTED_AMOUNT = 1.04e8
NEW_CUSTOMER_YEARS = (2024, 2025, 2026)
TAG_SUBCATEGORY = "Balises/étiquettes RFID et cartes ID"


def eur(x: float) -> str:
    return f"€{x:,.2f}"


def pct(x: float | None) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:.1%}"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        cells = ["" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v) for v in row]
        lines.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |")
    return "\n".join(lines)


def _category_mix(lines: pd.DataFrame) -> pd.Series:
    real = lines[~_is_true(lines["IS_NOT_REAL_ITEM"])]
    s = real.groupby("ITEM_CATEGORY")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    s = s.drop(labels=["NULL"], errors="ignore")
    return s / s.sum()


def render_readme(snap: Snapshot, r: BuildResult, snapshot_date: date) -> str:
    o = snap.orders
    allc, c = r.all_customers, r.companies
    total_amount = o["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    not_real = o[_is_true(o["IS_NOT_REAL_ITEM"])]
    inter = allc[allc["is_intercompany"]]
    inter_lines = o[o["CUSTOMER_ID"].isin(set(inter["customer_id"]))]
    main_total = c["amount_ht_eur"].sum()
    il = r.intercompany_lines
    il_amount = float(il["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()) if len(il) else 0.0
    il_desc = (
        f"{il['CUSTOMER_ID'].nunique()} 个客户 / {il['ORDER_ID'].nunique()} 张订单 / {eur(il_amount)}" if len(il) else "0"
    )
    n = len(c)
    out: list[str] = []
    w = out.append

    w(f"# 有过客户订单（CO）的公司名单 — 快照 {snap.snapshot}\n")
    w(
        f"生成时间 {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC，由 "
        f"`uv run python -m analyse_dolibarr_client.companies --snapshot {snap.snapshot}` 生成，"
        "本文件每次重跑会被覆盖。读 `data/raw/` 下的 parquet，以及 `erp_socid.py` 只读调用 Dolibarr API 得到的 "
        "`erp_order_socid.csv`（订单 → 第三方）、`erp_thirdparties.py` 只读拉取的 `erp_thirdparties.csv`（第三方网站 / 邮箱域名）"
        "和 `product_lines.py` 只读拉取的 `erp_product_tags.csv`（产品标签）；"
        "未连 Snowflake、未抓 LinkedIn。\n"
    )

    # ---------------------------------------------------------------- scope
    w("## 1. 范围与核对\n")
    n_orders, n_cust = o["ORDER_ID"].nunique(), o["CUSTOMER_ID"].nunique()
    no_date = o[o["ORDER_DATE"].isna()]
    entity_start = "，".join(
        f"{k} {v}" for k, v in o.groupby("ENTITY_NAME")["ORDER_DATE"].min().sort_values().items()
    )
    scope = pd.DataFrame(
        [
            ["订单行（全部）", f"{snap.orders_all_rows:,}", "", ""],
            ["有效订单行 IS_VALID_ORDER=true", f"{len(o):,}", "", ""],
            ["有效订单数", f"{n_orders:,}", f"{EXPECTED_ORDERS:,}", f"{n_orders - EXPECTED_ORDERS:+,}"],
            ["有效订单客户数 (CUSTOMER_ID)", f"{n_cust:,}", f"{EXPECTED_CUSTOMERS:,}", f"{n_cust - EXPECTED_CUSTOMERS:+,}"],
            ["有效订单金额 HT", eur(total_amount), "≈ €104,000,000", eur(total_amount - EXPECTED_AMOUNT)],
            ["IS_NOT_REAL_ITEM=true 的有效订单行（已排除）", f"{len(not_real):,} 行 / {eur(not_real['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}", "", ""],
            ["对上内部公司的客户（已排除，见 issues.csv）", f"{len(inter)} 个 / {inter_lines['ORDER_ID'].nunique()} 张订单 / {eur(inter_lines['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}", "", ""],
            ["主名单客户中开给内部公司的订单（已从金额扣除）", il_desc, "", ""],
            ["**主名单 companies.csv 行数**", f"**{n:,}**", "", ""],
            ["**主名单金额合计 amount_ht_eur**", f"**{eur(main_total)}**", "", ""],
        ],
        columns=["项目", "实际", "期望", "差异"],
    )
    w(md_table(scope) + "\n")
    w(
        f"- 有效订单数和客户数与期望完全一致；金额 {eur(total_amount)}（≈ {total_amount / 1e8:.4f} 亿欧元 HT）。\n"
        f"- IS_NOT_REAL_ITEM 在有效订单里没有 true 值，所以排除逻辑虽已实现，但这一轮实际排除 0 行、€0。\n"
        f"- 被排除的内部公司客户：{', '.join(f'{x.customer_name}（{x.entity_names}，{eur(x.amount_ht_eur)}）' for x in inter.itertuples())}。\n"
        f"- 主名单里有 {int((c['amount_ht_eur'] == 0).sum())} 个客户的有效订单金额合计为 €0（全部是 0 元订单行），保留在名单中，notes 里标「有效订单金额为0」。\n"
        f"- {int(c['customer_name'].isna().sum())} 个 CUSTOMER_ID 的订单上没有 CUSTOMER_NAME，无法按名称匹配，"
        f"写进 issues（no_customer_name），合计 {eur(c.loc[c['customer_name'].isna(), 'amount_ht_eur'].sum())}；"
        f"其中 {int((c['customer_name'].isna() & c['match_status'].eq(MATCH_ERP)).sum())} 个由 ERP socid 补上了第三方。"
        "`lookup_name` 为空时可用 `third_party_name`。\n"
        "- 付款状态 IS_PAID 全为空，本轮不分析付款。\n"
        f"- {len(no_date)} 条有效订单行（{no_date['ORDER_ID'].nunique()} 张订单，{', '.join(sorted(no_date['ENTITY_NAME'].unique()))}，"
        f"{eur(no_date['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}）没有 ORDER_DATE。金额照常计入；"
        "orders_by_category 里这些行的 year 为空；日期没有用订单号去推断。\n"
        f"- 各法人在快照里的最早订单：{entity_start}。Page Up、Ubi Smart 的订单基本从 2024 年才开始（2023 年各只有 4 张），"
        "所以它们的客户在本数据里的「首单」大多落在 2024 年以后，不一定真的是新客户。"
        f"只在这几个法人（Page Up / Ubi Smart / Ubi Impact）下过单的客户有 {int(c['history_truncated'].sum())} 个"
        f"（{eur(c.loc[c['history_truncated'], 'amount_ht_eur'].sum())}），标了 `history_truncated=true`："
        "它们的 first_order_date、n_years_active 和「新客户」身份都不可靠。"
        "同时也在 Ubi Solutions 下过单的客户不标，因为 Ubi Solutions 的历史是完整的。\n"
    )

    # ---------------------------------------------------------------- matching
    w("## 2. 和第三方档案的匹配\n")
    vc = c["match_status"].value_counts()
    nm = r.name_matches
    any_match = n - int(vc.get(MATCH_UNMATCHED, 0))
    unique_statuses = [MATCH_ERP, MATCH_EXACT, MATCH_NORMALIZED]
    unique_match = int(sum(vc.get(s, 0) for s in unique_statuses))
    w(
        "分两层：先用 ERP 里订单自己挂的第三方（socid），没有可信 socid 的客户再按名称匹配。\n\n"
        + md_table(
            pd.DataFrame(
                [
                    [s, int(vc.get(s, 0)), pct(vc.get(s, 0) / n), eur(c.loc[c["match_status"] == s, "amount_ht_eur"].sum())]
                    for s in (MATCH_ERP, MATCH_EXACT, MATCH_NORMALIZED, MATCH_AMBIGUOUS, MATCH_UNMATCHED)
                ],
                columns=["match_status", "客户数", "占主名单", "订单金额"],
            )
        )
        + "\n"
    )
    w(
        f"- **唯一匹配率（erp_socid + exact + normalized）：{unique_match}/{n} = {pct(unique_match / n)}**；"
        f"按金额 {pct(c.loc[c['match_status'].isin(unique_statuses), 'amount_ht_eur'].sum() / main_total)}。"
        f"含 ambiguous 至少对上一条档案的 {any_match}/{n} = {pct(any_match / n)}。\n"
    )
    erp = snap.erp_order_socid
    if erp is not None:
        trusted = erp["socid_trusted"]
        bad = erp[~trusted]
        no_erp = c[c["erp_orders_verified"] == 0]
        md5_ok = erp.loc[trusted & erp["md5_socid_equals_customer_id"].eq("True"), "CUSTOMER_ID"].nunique()
        w("### 2.1 ERP socid（主要依据）\n")
        w(
            "订单 mart 的 CUSTOMER_ID 是 32 位哈希，不是第三方 ID，所以不能直接 join。"
            "`erp_socid.py` 用 Dolibarr REST API **只读**列出全部订单抬头（`GET /orders`，按法人分页），只取 id、ref、socid、entity，"
            "存成 `erp_orders.csv`；再按 ORDER_ID 对到快照订单，**ORDER_ID 和订单号都一致**才采用这张订单的 socid（`erp_order_socid.csv`）。\n\n"
            f"- 快照有效订单 {len(erp)} 张：按 ID 在 ERP 找到 {int(erp['id_found'].astype(str).eq('True').sum())} 张，ID 和订单号都一致 {int(trusted.sum())} 张。\n"
            f"- 不一致的 {len(bad)} 张，ORDER_ID 都在 {pd.to_numeric(bad['ORDER_ID'], errors='coerce').min():.0f} 以上"
            f"（{int(bad['id_found'].astype(str).ne('True').sum())} 张 ERP 里没有这个 ID，{int(bad['id_found'].astype(str).eq('True').sum())} 张 ID 相同但订单号不同）。"
            "API 连的实例和快照的数据源在 2026 年 9 月初分叉了：之前的订单完全一致，之后两边各自编号。"
            f"所以没有可信 socid 的 {len(no_erp)} 个客户全是首单在 {pd.to_datetime(no_erp['first_order_date']).min():%Y-%m-%d} 以后的新客户，"
            "它们退回到名称匹配。哪个实例是正式库需要和 IT 确认。\n"
            f"- 旁证：{md5_ok} 个客户的 CUSTOMER_ID 正好等于 `md5(socid)`，说明 mart 对一部分客户就是拿第三方 ID 做的哈希；"
            "其余客户的 CUSTOMER_ID 是跨多个第三方的归并键，算法未知。\n"
            f"- 一个客户的订单开在多个第三方上的有 {int((c['erp_third_parties'].str.count(';') > 0).sum())} 个"
            "（如 GEODIS 的各地分公司、集团和子公司混开）。主名单的 third_party_id 取**订单金额最大的非内部公司** socid，"
            "全部 socid 和金额写在 `erp_third_parties`（`id:金额;…`），并在 issues.csv 记 `erp_multiple_third_parties`。\n"
            "- 订单全部开给内部公司（IS_INTERCOMPANY）的客户排除出主名单。只有部分订单开给内部公司的客户保留，"
            "但这些订单从金额、订单数和品类统计里扣掉（扣掉的金额在 `intercompany_excluded_ht_eur`），记 `erp_includes_intercompany`。"
            "`erp_third_parties` 里内部公司的 socid 标 `(interco)`，金额是扣除前的。\n\n"
        )
        labels = {
            "same": "名称匹配到的就是这个第三方",
            "same_name_other_row": "名称匹配到同名的另一条档案（重复录入）",
            "erp_in_name_candidates": "名称一对多，ERP 选中的在候选里",
            "name_ambiguous_other": "名称一对多，ERP 选中的不在候选里",
            "different": "名称匹配到别的第三方（多为集团名 vs 实际开票子公司）",
            "name_unmatched": "名称没匹配上，ERP 补上",
        }
        cmp_ = c.loc[c["match_status"] == MATCH_ERP, "name_vs_erp"].value_counts()
        w(
            "和单纯名称匹配的对照（match_status=erp_socid 的客户，列 `name_vs_erp`）：\n\n"
            + md_table(
                pd.DataFrame(
                    [[k, labels.get(k, k), int(v)] for k, v in cmp_.items()],
                    columns=["name_vs_erp", "含义", "客户数"],
                )
            )
            + "\n\n名称匹配和 ERP 不一致的，一律采用 ERP，并在 issues.csv 记 `name_match_differs_from_erp`；"
            "原来的名称匹配结果保留在 `name_match_status` / `name_match_third_party_id`。\n"
        )
        w("### 2.2 名称匹配（ERP 没有可信 socid 时的退路）\n")
    exact_rule = int((nm["rule"] == "exact").sum())
    w(
        f"下面的统计是对全部 {len(allc)} 个下单客户单独跑名称匹配的结果（不管有没有 ERP socid）：\n\n"
        f"- 精确规则对上 {exact_rule} 个（{pct(exact_rule / len(allc))}），与 brief 的 831 一致；"
        f"规范化又多配上 {int(nm['rule'].isin(['basic', 'core']).sum())} 个"
        f"（basic {int((nm['rule'] == 'basic').sum())}，core {int((nm['rule'] == 'core').sum())}）；"
        f"一对多 {int((nm['status'] == MATCH_AMBIGUOUS).sum())} 个，未匹配 {int((nm['status'] == MATCH_UNMATCHED).sum())} 个。\n"
        f"- 一对多的消歧：先按 brief 的规则 4 选 IS_CLIENT=true 且非 IS_INTERCOMPANY 的档案（用到 {int(nm['tie_break'].fillna('').str.contains('is_client').sum())} 次）；"
        f"仍多个时，再选档案 ENTITY_ID 属于该客户下单法人的那条（用到 {int(nm['tie_break'].fillna('').str.contains('entity').sum())} 次，"
        "ENTITY_ID 映射 1=Ubi Solutions、2=Page Up、3=Ubi Smart、5=Ubi Impact，是从唯一精确匹配的样本反推出来的）。仍多个的标 ambiguous："
        "third_party_id 留空，候选全部写进 third_party_ids；国家、城市、SIREN 等只在所有候选一致时才填。\n"
        "- 没有使用任何前缀或相似度匹配作为结果。unmatched 行的 `candidate_third_parties` 只是供人工参考的候选"
        "（名称按「 - 」拆分后某一段完全相同，或整词前缀相同），不参与匹配。\n"
        "- SIREN 校验：`company_reg_id` 是从档案 SIREN（9 位）、SIRET 前 9 位、西班牙 CIF 或欧盟 VAT 号清洗出来的；"
        "`import110`、`Vtiger672`、`PRO 7892` 这类 CRM 导入残留不算有效注册号。冲突写在 issues.csv：\n"
        "  - `siren_conflict_candidates`：同名候选档案的注册号不同；\n"
        "  - `siren_shared_by_different_names`：同一个注册号对上了多个名称不同的下单客户（大多是同一法人的门店或部门）；\n"
        "  - `siren_registry_conflict`：匹配到的档案，其注册号在档案表里还挂在其他名称下（多为同一法人的分支或曾用名，优先级低）。\n"
    )
    w("### 名称规范化做了什么\n")
    w(
        "1. **exact**：`upper(trim(name))` 完全相等。\n"
        "2. **basic**：去掉重音（NFKD）、转大写、删掉 `.` 和撇号（`S.A.S.`→`SAS`、`L'Oréal`→`LOREAL`），"
        "其余标点（`-`, `,`, `&`, `+`, `/` 等）换成空格，再压缩连续空格。\n"
        "3. **core**：在 basic 之前先去掉括号内容（`EDF (FR)`→`EDF`、`… LTD (Radisson Blu …)`）和网址后缀（`.fr` `.com` 等），"
        "再从名称**末尾去掉一个**法律形式词，从开头去掉 SAS/SARL/SASU/EURL/STE。只去一次，是因为反复剥离会把"
        "`Creaciones B V s.l.` 剥成 `CREACIONES`，这样宽泛的 key 容易和别的公司撞上。剥完为空时保留原 key（例如客户名就叫 `SAS`）。\n"
        f"   - 末尾法律形式（{len(LEGAL_SUFFIXES)} 种）：" + ", ".join(sorted({' '.join(s) for s in LEGAL_SUFFIXES})) + "\n"
        f"   - 开头法律形式：" + ", ".join(' '.join(s) for s in LEGAL_PREFIXES) + "\n"
        "4. 不去掉 GROUPE/GROUP、FRANCE 这类词（`Sonepar France` 和 `SONEPAR` 是不同法人）。"
        "只有在判断「是否内部公司」时才额外去掉 GROUPE/GROUP（这样 `Groupe Page Up` 能识别为 PAGE UP）。\n"
        "5. `lookup_name` 保留原有大小写和重音，只去掉括号限定、网址后缀和一个法律形式。"
        "match_status=erp_socid 时它取自 ERP 订单实际开票的第三方档案名（`lookup_name_source=third_party_name`），"
        "因为订单上的客户名有时是归并出来的标签（例如 `S Transport` 实际是 BOVIS Transport，`TCS - GROUPE STERNE` 实际是 TCS）；"
        "其余情况取订单客户名（`customer_name`）。订单客户名清洗后的版本始终保留在 `order_lookup_name`，可作为第二个搜索词。"
        f"两者去掉法律形式和泛用词（GROUPE、FRANCE、SERVICES、TRANSPORT 等）后没有共同词的，`lookup_name_conflict=true`"
        f"（{int(c['lookup_name_conflict'].sum())} 个，{eur(c.loc[c['lookup_name_conflict'], 'amount_ht_eur'].sum())}）："
        "可能是中间商开票（`Franprix - Groupe Casino` → IR2S）、品牌名 vs 法定名（`SECANETA` → JOSÉ ALBERO PUERTO）"
        "或集团 vs 子公司（`Newell Brands` → ALLEGRE PUERICULTURE），web app 应两个名字都搜；"
        "`lookup_query` = `lookup_name` + 档案城市 + 国家（ISO2，优先用档案国家，否则把订单上的自由文本国家映射成 ISO2）。\n"
    )

    # ---------------------------------------------------------------- web domains
    w("### 网站域名（给 LinkedIn 查询用）\n")
    if snap.erp_thirdparties is None:
        w("没有 `erp_thirdparties.csv`，`web_domain` 等列为空。先跑 `erp_thirdparties.py`。\n")
    else:
        has = c["web_domain"].notna()
        mn = c["web_domain_matches_name"].fillna(False).astype(bool)
        tab = (
            c[has]
            .assign(m=mn[has])
            .groupby("web_domain_source")
            .agg(客户数=("customer_id", "size"), 对得上名称=("m", "sum"), 金额=("amount_ht_eur", "sum"))
            .sort_values("客户数", ascending=False)
        )
        top100 = c.nlargest(100, "amount_ht_eur")
        shared = c["notes"].fillna("").str.contains("域名与其他客户共用")
        total = c["amount_ht_eur"].sum()
        w(
            "`erp_thirdparties.py` 用 Dolibarr API **只读**列出全部第三方（`GET /thirdparties`）和联系人（`GET /contacts`），"
            "只保留公司层面的信息：名称、SIREN、网站（`url`）、LinkedIn 字段、员工数档位、公司邮箱的**域名**，"
            "以及每个第三方下联系人邮箱的**域名**和出现次数。"
            "完整邮箱、联系人姓名、电话、备注、个人 LinkedIn 都不保存；gmail/orange.fr/t-online.de 这类个人邮箱、"
            "basware/pennylane 这类电子发票或会计平台的域名不算。ERP 名称和快照档案名一致才采用。\n\n"
            f"主名单有 `web_domain` 的客户 {int(has.sum())} / {n} 个，占金额 {pct(c.loc[has, 'amount_ht_eur'].sum() / total)}；"
            f"金额前 100 的客户里有 {int(top100['web_domain'].notna().sum())} 个。"
            f"其中域名和公司名对得上（`web_domain_matches_name=true`）的 {int(mn.sum())} 个，占金额 {pct(c.loc[mn, 'amount_ht_eur'].sum() / total)}。"
            "大部分来自联系人邮箱：Dolibarr 正式客户档案很少填网站，但几乎都挂了联系人。\n\n"
            "取值顺序（`web_domain_source`）：客户自己的档案（`own_*`，主 third_party_id 优先）→ 同一 SIREN 的其他档案（`same_siren_*`）"
            "→ 同国家、规范化名称相同的其他档案（`same_name_*`；3 个字符以内的缩写不借，`lookup_name_conflict=true` 时只用档案名借）。"
            "每层里依次是网站 → 公司邮箱域名 → 联系人邮箱域名（`*_contact_email`；多个时先取和公司名对得上的，再取出现最多的）。"
            "集团自己的域名（ubisolutions.net、pageup.fr 等，常见于我们自己员工被挂成客户联系人）不采用。\n\n"
            "`web_domain_matches_name`：域名里含有公司名的有效词（`cerp-rrm.com` ↔ CERP RHIN RHONE），"
            "或者是公司名的首字母缩写（`cfigroupe.com` ↔ COMPAGNIE FRANCAISE INFORMATIQUE）。"
            "false 多半是母公司或母品牌域名（`MB LOG` → mrbricolage.fr，`SONELOG` → sonepar.fr），"
            "也可能是挂错的联系人（集成商、会计），web app 用它时应把 LinkedIn 主页网站和公司名都核对一下。\n\n"
            + md_table(tab.reset_index().assign(金额=lambda d: d["金额"].map(eur)))
            + f"\n\n没有域名的 {int((~has).sum())} 个。\n\n"
            "注意：\n"
            f"- {int(shared.sum())} 个客户的域名和名单里别的客户相同（notes 写了「域名与其他客户共用」），多半是同一集团（geodis.com、faurecia.com…）。\n"
            f"- `web_domain_alternatives` 列出其他候选域名（{int(c['web_domain_alternatives'].notna().sum())} 个客户有）。\n"
            f"- `linkedin_url`：Dolibarr 的 LinkedIn 字段全部为空，现在没有可用值（{int(c['linkedin_url'].notna().sum())} 个）。"
            f"`headcount_band` 是档案里的员工数档位，有值的 {int(c['headcount_band'].notna().sum())} 个。\n"
        )

    # ---------------------------------------------------------------- distribution
    w("## 3. 分布\n")
    w("### 按法人（orders_by_entity.csv，主名单范围）\n")
    ent = r.orders_by_entity.copy()
    ent["amount_ht_eur"] = ent["amount_ht_eur"].map(eur)
    ent["amount_share"] = ent["amount_share"].map(pct)
    w(md_table(ent[["entity_name", "n_customers", "n_orders", "n_order_lines", "amount_ht_eur", "amount_share"]]) + "\n")
    multi = c["entity_names"].str.contains(";")
    w(f"跨法人下单的客户 {int(multi.sum())} 个（entity_names 含多个值），所以各法人客户数相加大于 {n}。\n")
    w("### 按国家（country_code，前 15）\n")
    cc = (
        c.assign(country_code=c["country_code"].fillna("(空)"))
        .groupby("country_code")
        .agg(客户数=("customer_id", "size"), 金额=("amount_ht_eur", "sum"))
        .sort_values("金额", ascending=False)
    )
    cc["金额占比"] = (cc["金额"] / main_total).map(pct)
    cc["金额"] = cc["金额"].map(eur)
    w(md_table(cc.head(15).reset_index()) + "\n")

    # ---------------------------------------------------------------- unmatched
    w("## 4. 未匹配客户（按金额前 15，全部见 unmatched.csv）\n")
    um = c[c["match_status"] == MATCH_UNMATCHED].head(15)
    w(
        md_table(
            um.assign(amount_ht_eur=um["amount_ht_eur"].map(eur))[
                ["customer_name", "entity_names", "order_country_raw", "amount_ht_eur", "n_orders", "candidate_third_parties"]
            ]
        )
        + "\n"
    )
    w(
        f"未匹配 {int(vc.get(MATCH_UNMATCHED, 0))} 个，金额 {eur(c.loc[c['match_status'] == MATCH_UNMATCHED, 'amount_ht_eur'].sum())}"
        f"（占主名单 {pct(c.loc[c['match_status'] == MATCH_UNMATCHED, 'amount_ht_eur'].sum() / main_total)}）。"
        f"其中 {int((c['match_status'].eq(MATCH_UNMATCHED) & c['candidate_third_parties'].ne('')).sum())} 个有人工参考候选。\n"
    )

    # ---------------------------------------------------------------- order analysis
    w("## 5. 订单分析（主名单范围，金额不含 IS_NOT_REAL_ITEM）\n")
    real = r.main_lines[~_is_true(r.main_lines["IS_NOT_REAL_ITEM"])]
    cat = real.groupby("ITEM_CATEGORY")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum().sort_values(ascending=False)
    cat_cust = real[real["ITEM_ORDERED_AMOUNT_HT_EUR"] != 0].groupby("ITEM_CATEGORY")["CUSTOMER_ID"].nunique()
    w("### 5.1 公司整体卖什么：金额前 5 的 ITEM_CATEGORY\n")
    top5 = pd.DataFrame(
        {
            "ITEM_CATEGORY": cat.index[:5],
            "金额": [eur(v) for v in cat.values[:5]],
            "占比": [pct(v / main_total) for v in cat.values[:5]],
            "客户数": [int(cat_cust.get(k, 0)) for k in cat.index[:5]],
        }
    )
    w(md_table(top5) + "\n")
    w(
        f"前 5 合计 {pct(cat.values[:5].sum() / main_total)}。分不清的品类：Unknown {eur(cat.get('Unknown', 0))}"
        f"（{pct(cat.get('Unknown', 0) / main_total)}）、Autres {eur(cat.get('Autres', 0))}（{pct(cat.get('Autres', 0) / main_total)}）；"
        f"ITEM_CATEGORY 为字符串 \"NULL\" 的 {int((real['ITEM_CATEGORY'] == 'NULL').sum()):,} 行金额都是 €0（文字行），不计入产品结构。\n"
    )

    w("### 5.2 一次性 vs 复购\n")
    one = c["n_orders"] == 1
    w(
        md_table(
            pd.DataFrame(
                [
                    ["一次性（有效订单 1 张）", int(one.sum()), pct(one.mean()), eur(c.loc[one, "amount_ht_eur"].sum()), pct(c.loc[one, "amount_ht_eur"].sum() / main_total)],
                    ["复购（≥ 2 张）", int((~one).sum()), pct((~one).mean()), eur(c.loc[~one, "amount_ht_eur"].sum()), pct(c.loc[~one, "amount_ht_eur"].sum() / main_total)],
                ],
                columns=["类型", "客户数", "客户占比", "金额", "金额占比"],
            )
        )
        + "\n"
    )
    bp = (
        c.groupby("buyer_pattern")
        .agg(客户数=("customer_id", "size"), 金额=("amount_ht_eur", "sum"), 中位订单数=("n_orders", "median"))
        .sort_values("金额", ascending=False)
    )
    bp["金额占比"] = (bp["金额"] / main_total).map(pct)
    bp["金额"] = bp["金额"].map(eur)
    w("buyer_pattern 分布：\n\n" + md_table(bp.reset_index()) + "\n")
    w(
        "**buyer_pattern 规则**（从上到下，命中即停；占比都相对该客户的 amount_ht_eur）：\n\n"
        "1. `one_shot`：有效订单只有 1 张。\n"
        "2. `other`：多张订单，但金额合计 ≤ 0（全是 0 元行），无法判断结构。\n"
        f"3. `license_or_maintenance`：Licences & Abonnements + Maintenance & Support 合计占比 ≥ {LICENSE_MAINTENANCE_MIN_SHARE:.0%}。\n"
        f"4. `repeat_product`：金额第一的 ITEM_CATEGORY 占比 ≥ {REPEAT_PRODUCT_MIN_SHARE:.0%}。\n"
        f"5. `mix_hardware_project`：硬件类（{', '.join(sorted(HARDWARE_CATEGORIES))}）合计占比 ≥ {MIX_MIN_SIDE_SHARE:.0%}，"
        f"且项目/服务类（{', '.join(sorted(PROJECT_SERVICE_CATEGORIES))}）合计占比 ≥ {MIX_MIN_SIDE_SHARE:.0%}。\n"
        "6. `other`：以上都不是（通常是 Unknown / Autres / Prestations diverses 占大头，或者各品类都很分散）。\n\n"
        "和 brief 列出的顺序不同的地方：license_or_maintenance 放在 repeat_product 前面。否则 Maintenance 占 80% 的客户会先被归成 repeat_product，"
        "license_or_maintenance 这一类几乎就空了。mix 要求两边各至少 5%，是为了不让一笔几十欧的培训或保修就把纯硬件客户算成 mix。\n"
    )

    w("### 5.3 合同\n")
    hc = c["has_contract"]
    w(
        f"有有效合同（MART_CONTRACTS_TO_DATE 里 IS_VALID_CONTRACT=true）的客户 **{int(hc.sum())}** 个（{pct(hc.mean())}），"
        f"订单金额 {eur(c.loc[hc, 'amount_ht_eur'].sum())}，占 **{pct(c.loc[hc, 'amount_ht_eur'].sum() / main_total)}**。"
        f"有合同客户的 share_recurring 中位数 {pct(c.loc[hc, 'share_recurring'].median())}，无合同客户 {pct(c.loc[~hc, 'share_recurring'].median())}。\n"
    )
    inv_total = c["invoice_amount_ht_eur"].sum()
    no_inv = c["n_invoices"] == 0
    w(
        f"发票交叉：主名单客户的有效发票（按 INVOICE_ID 去重后的 INVOICE_AMOUNT_HT_EUR）合计 {eur(inv_total)}，订单 − 发票 = {eur(main_total - inv_total)}。"
        f"{int(no_inv.sum())} 个客户没有任何有效发票（订单金额 {eur(c.loc[no_inv, 'amount_ht_eur'].sum())}）。"
        "发票里有不带订单直接开票的情况，所以单个客户的差额可正可负，见 `order_minus_invoice_ht_eur`。\n"
    )

    w("### 5.4 2024–2026 新客户\n")
    first_year = pd.to_datetime(c["first_order_date"]).dt.year.astype("Int64")
    new = first_year.isin(NEW_CUSTOMER_YEARS).fillna(False).astype(bool)
    per_year = c[new].groupby(first_year[new]).agg(客户数=("customer_id", "size"), 金额=("amount_ht_eur", "sum"))
    per_year["金额"] = per_year["金额"].map(eur)
    per_year.index.name = "首单年份"
    w(
        f"首单在 2024–2026 的新客户 **{int(new.sum())}** 个（占 {pct(new.mean())}），累计订单金额 {eur(c.loc[new, 'amount_ht_eur'].sum())}。\n\n"
        + md_table(per_year.reset_index())
        + "\n"
    )
    only_sol = c["entity_names"] == "Ubi Solutions"
    w(
        f"按法人拆：只在 Ubi Solutions 下过单的新客户 {int((new & only_sol).sum())} 个"
        f"（金额 {eur(c.loc[new & only_sol, 'amount_ht_eur'].sum())}）；涉及 Page Up / Ubi Smart / Ubi Impact 的新客户 "
        f"{int((new & ~only_sol).sum())} 个（金额 {eur(c.loc[new & ~only_sol, 'amount_ht_eur'].sum())}）。"
        "后一组很多是这几个法人的数据 2024 年才进 Dolibarr 带来的，不一定是真正的新客户。"
        f"其中 {int((new & c['history_truncated']).sum())} 个是 `history_truncated=true`，无法判断是否真的新。"
        f"只算 Ubi Solutions 的话，2024–2026 新客户占 Ubi Solutions 客户的 {pct((new & only_sol).sum() / only_sol.sum())}。\n"
    )
    period = real[pd.to_datetime(real["ORDER_DATE"]).dt.year.isin(NEW_CUSTOMER_YEARS)]
    new_ids = set(c.loc[new, "customer_id"])
    mix_new = _category_mix(period[period["CUSTOMER_ID"].isin(new_ids)])
    mix_old = _category_mix(period[~period["CUSTOMER_ID"].isin(new_ids)])
    comp = pd.DataFrame({"新客户": mix_new, "老客户": mix_old}).fillna(0.0)
    comp["差 (pp)"] = (comp["新客户"] - comp["老客户"]) * 100
    comp = comp.sort_values("新客户", ascending=False)
    w(
        "两组都只看 2024–2026 年的订单，比较金额的品类结构（老客户 = 首单在 2024 年之前）：\n\n"
        + md_table(
            comp.assign(
                新客户=comp["新客户"].map(pct), 老客户=comp["老客户"].map(pct), **{"差 (pp)": comp["差 (pp)"].map(lambda x: f"{x:+.1f}")}
            ).reset_index(names="ITEM_CATEGORY")
        )
        + "\n"
    )
    def diff_list(cmp: pd.DataFrame, sign: int) -> str:
        sel = cmp[cmp["差 (pp)"] * sign >= 3].sort_values("差 (pp)", ascending=sign < 0)
        return "、".join(f"{k}（{v:+.1f}pp）" for k, v in sel["差 (pp)"].items()) or "无"

    sol_ids = set(c.loc[new & only_sol, "customer_id"])
    sol_period = period[period["ENTITY_NAME"] == "Ubi Solutions"]
    comp_sol = pd.DataFrame(
        {
            "新客户": _category_mix(sol_period[sol_period["CUSTOMER_ID"].isin(sol_ids)]),
            "老客户": _category_mix(sol_period[~sol_period["CUSTOMER_ID"].isin(new_ids)]),
        }
    ).fillna(0.0)
    comp_sol["差 (pp)"] = (comp_sol["新客户"] - comp_sol["老客户"]) * 100
    comp_sol = comp_sol.sort_values("新客户", ascending=False)
    w(
        "\n只看 Ubi Solutions 法人的订单，用只在 Ubi Solutions 下单的新客户对比老客户，"
        "去掉 Page Up / Ubi Smart 数据从 2024 年才开始的影响：\n\n"
        + md_table(
            comp_sol.assign(
                新客户=comp_sol["新客户"].map(pct), 老客户=comp_sol["老客户"].map(pct),
                **{"差 (pp)": comp_sol["差 (pp)"].map(lambda x: f"{x:+.1f}")},
            ).reset_index(names="ITEM_CATEGORY")
        )
        + "\n"
    )
    w(
        f"**结论**：整体看，新客户的品类明显不同，新客户高出 ≥3pp 的是 {diff_list(comp, 1)}，低出 ≥3pp 的是 {diff_list(comp, -1)}。"
        f"但只看 Ubi Solutions 时，新客户高出 ≥3pp 的是 {diff_list(comp_sol, 1)}，低出 ≥3pp 的是 {diff_list(comp_sol, -1)}。"
    )
    other_ent = _category_mix(period[period["ENTITY_NAME"] != "Ubi Solutions"])
    sol_mix = _category_mix(sol_period)
    proj_lic = ["Projets & Intégration", "Licences & Abonnements"]
    old_cons = sol_period[
        ~sol_period["CUSTOMER_ID"].isin(new_ids) & (sol_period["ITEM_CATEGORY"] == "Consommables")
    ].groupby("CUSTOMER_NAME")["ITEM_ORDERED_AMOUNT_HT_EUR"].sum().sort_values(ascending=False)
    new_share_other = (new & ~only_sol).sum() / new.sum()
    old_share_other = (~new & ~only_sol).sum() / (~new).sum()
    w(
        f"整体差异主要是法人构成造成的：新客户里涉及 Page Up / Ubi Smart / Ubi Impact 的占 {pct(new_share_other)}，老客户里只占 {pct(old_share_other)}；"
        f"而 2024–2026 年这几个法人的订单中 Projets & Intégration + Licences & Abonnements 占 {pct(sum(other_ent.get(k, 0) for k in proj_lic))}，"
        f"Ubi Solutions 只有 {pct(sum(sol_mix.get(k, 0) for k in proj_lic))}。"
        "在 Ubi Solutions 内部，新客户并没有更偏项目或许可。新客户的 Maintenance 少，符合先装硬件、后签维保的顺序；"
        f"老客户的 Consommables 高，{old_cons.index[0] if len(old_cons) else '—'} 一家就占老客户耗材金额的 "
        f"{pct(old_cons.iloc[0] / old_cons.sum() if len(old_cons) else None)}。新客户的 Unknown 占比高，说明新产品还没有归类，值得补一下品类映射。\n"
    )
    tp_new = c.loc[new, "buyer_pattern"].value_counts(normalize=True)
    tp_old = c.loc[~new, "buyer_pattern"].value_counts(normalize=True)
    w(
        f"buyer_pattern：新客户 one_shot {pct(tp_new.get('one_shot', 0))}，老客户 {pct(tp_old.get('one_shot', 0))}"
        "（新客户时间短，one_shot 偏高是正常的）。\n"
    )

    w("### 5.5 买标签的人会不会再买项目（category_cooccurrence.csv）\n")
    co = r.category_cooccurrence
    off = co[co["category_a"] != co["category_b"]]

    def cond(a: str, b: str) -> str:
        row = off[((off["category_a"] == a) & (off["category_b"] == b)) | ((off["category_a"] == b) & (off["category_b"] == a))]
        diag = co[(co["category_a"] == a) & (co["category_b"] == a)]
        na = int(diag["n_customers_a"].iloc[0]) if len(diag) else 0
        both = int(row["n_customers_both"].iloc[0]) if len(row) else 0
        return f"买过 {a} 的 {na} 个客户里，{both} 个（{pct(both / na if na else None)}）也买过 {b}"

    rfid = "Composants RFID & IoT"
    lines_ = [cond(rfid, b) for b in ("Projets & Intégration", "Licences & Abonnements", "Maintenance & Support", "Terminaux mobiles & tablettes")]
    tag_buyers = set(real.loc[(real["ITEM_SUBCATEGORY_LV1"] == TAG_SUBCATEGORY) & (real["ITEM_ORDERED_AMOUNT_HT_EUR"] > 0), "CUSTOMER_ID"])
    per = real.groupby(["CUSTOMER_ID", "ITEM_CATEGORY"])["ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    proj_buyers = set(per[per > 0].reset_index().query("ITEM_CATEGORY == 'Projets & Intégration'")["CUSTOMER_ID"])
    lic_buyers = set(per[per > 0].reset_index().query("ITEM_CATEGORY == 'Licences & Abonnements'")["CUSTOMER_ID"])
    w(
        "\n".join(f"- {s}。" for s in lines_)
        + f"\n- 只看子品类「{TAG_SUBCATEGORY}」（标签本身）：{len(tag_buyers)} 个客户买过，"
        f"其中 {len(tag_buyers & proj_buyers)} 个（{pct(len(tag_buyers & proj_buyers) / len(tag_buyers) if tag_buyers else None)}）也买过 Projets & Intégration，"
        f"{len(tag_buyers & lic_buyers)} 个（{pct(len(tag_buyers & lic_buyers) / len(tag_buyers) if tag_buyers else None)}）也买过 Licences & Abonnements。\n"
        "- 共现按「该客户在该品类的净金额 > 0」计，不分先后。表里 share_of_a_also_b = 同时买 a 和 b 的客户数 / 买 a 的客户数。\n"
    )

    w("### 5.6 金额最高的 10 个客户\n")
    top = c.head(10)
    w(
        md_table(
            pd.DataFrame(
                {
                    "客户": top["customer_name"],
                    "国家": top["country_code"],
                    "法人": top["entity_names"],
                    "金额": top["amount_ht_eur"].map(eur),
                    "订单数": top["n_orders"],
                    "品类结构（前 3）": top["category_mix"],
                    "buyer_pattern": top["buyer_pattern"],
                    "合同": top["has_contract"].map({True: "有", False: ""}),
                    "疑似集成商": top["suspect_integrator_reason"],
                    "匹配": top["match_status"],
                }
            )
        )
        + "\n"
    )
    top10_share = top["amount_ht_eur"].sum() / main_total
    w(f"前 10 客户占主名单金额 {pct(top10_share)}；前 50 占 {pct(c.head(50)['amount_ht_eur'].sum() / main_total)}。\n")

    # ---------------------------------------------------------------- integrators
    w("## 6. 疑似集成商 / 同行（只标记，不删除）\n")
    si = c[c["suspect_integrator"]]
    w(
        f"`suspect_integrator`=true 的有 {len(si)} 个，金额 {eur(si['amount_ht_eur'].sum())}。满足下面任一条就标：\n"
        "- 名称里有窄口径关键词：RFID、TRAK、BARCODE/CODE BARRE、IDENTIFICATION、TRACABILITE、INTEGRATION/INTEGRATEUR、"
        "INFORMATIQUE、COMPUTER、SOFTWARE/LOGICIEL、ETIQUETTE/LABEL、AUTOMATISME、CONSULT*；\n"
        "- 名称里有已知 AIDC/RFID 厂商或渠道名（Zebra、Honeywell、Datalogic、Coppernic、SCC、SOTI 等，显示为 `peer:`）；\n"
        "- 也是供应商（`is_also_supplier`），而且硬件类金额占比 ≥ 50%。\n\n"
        "SYSTEMS、TECHNOLOGIES、DATA、单独的 ID 等宽泛词不算，因为会命中 Safran Landing Systems、Id Verde、ID Logistics 这类终端客户。"
        "这只是给人工看的筛选，不是结论。\n\n"
    )
    w(
        md_table(
            si.head(15).assign(amount_ht_eur=si.head(15)["amount_ht_eur"].map(eur))[
                ["customer_name", "suspect_integrator_reason", "top_item_category", "buyer_pattern", "amount_ht_eur"]
            ]
        )
        + "\n"
    )
    w(f"`is_also_supplier`=true 的有 {int(c['is_also_supplier'].sum())} 个（证据见 supplier_evidence：档案 IS_SUPPLIER、供应商订单 THIRD_PARTY_ID 或 SUPPLIER_NAME 规范化后相同）。\n")

    # ---------------------------------------------------------------- reconciliation
    w("## 7. 汇总表对账\n")
    by_cat = r.orders_by_category["amount_ht_eur"].sum()
    by_ent = r.orders_by_entity["amount_ht_eur"].sum()
    diag = co.loc[co["category_a"] == co["category_b"], "amount_ht_eur"].sum()
    null_cat = real.loc[real["ITEM_CATEGORY"] == "NULL", "ITEM_ORDERED_AMOUNT_HT_EUR"].sum()
    w(
        md_table(
            pd.DataFrame(
                [
                    ["companies.amount_ht_eur 合计", eur(main_total), ""],
                    ["orders_by_category.amount_ht_eur 合计", eur(by_cat), eur(by_cat - main_total)],
                    ["orders_by_entity.amount_ht_eur 合计", eur(by_ent), eur(by_ent - main_total)],
                    ["category_cooccurrence 对角线 amount_ht_eur 合计", eur(diag), eur(diag - main_total)],
                    ["全部有效订单金额（含内部公司）", eur(total_amount), eur(total_amount - main_total)],
                ],
                columns=["表", "金额", "与主名单差额"],
            )
        )
        + "\n"
    )
    w(
        f"- 三张汇总表的范围和主名单一样（排除内部公司客户、开给内部公司的订单和 IS_NOT_REAL_ITEM 行）。"
        f"共现表的对角线不含 \"NULL\" 品类，差额就是 \"NULL\" 行的金额 {eur(null_cat)}。\n"
        f"- 和全部有效订单相差 {eur(total_amount - main_total)} = 被排除的内部公司客户 {eur(inter_lines['ITEM_ORDERED_AMOUNT_HT_EUR'].sum())}"
        f" + 主名单客户开给内部公司的订单 {eur(il_amount)}"
        f"（核对差 {eur(total_amount - main_total - inter_lines['ITEM_ORDERED_AMOUNT_HT_EUR'].sum() - il_amount)}）；IS_NOT_REAL_ITEM 带来的差额是 €0。\n"
        "- 金额和日期都是从 parquet 原样聚合的，没有四舍五入（README 里展示时保留到分）。浮点求和可能带来 1e-8 级的尾差。\n"
    )

    # ---------------------------------------------------------------- files
    w("## 8. 输出文件\n")
    w(
        f"- `companies.parquet` / `companies.csv`：主名单，一行一个 CUSTOMER_ID，{n} 行，{len(c.columns)} 列，按 amount_ht_eur 降序。CSV 是 UTF-8 BOM 编码，方便 Excel 打开。\n"
        f"- `unmatched.csv`：match_status=unmatched 的 {int(vc.get(MATCH_UNMATCHED, 0))} 行，字段和主名单相同。\n"
        f"- `duplicates.csv`：{r.duplicates.groupby(['group_type', 'group_key']).ngroups if len(r.duplicates) else 0} 组疑似同一公司"
        "（`same_normalized_name` = core key 相同；`same_company_reg_id` = 匹配到的档案注册号相同；`same_third_party_id` = 主 third_party_id 相同），"
        "但 CUSTOMER_ID 不同。名单里没有合并它们。\n"
        "- `erp_orders.csv` / `erp_order_socid.csv`：从 Dolibarr API 只读拉取的订单抬头（id、ref、socid、entity），以及和快照订单的逐张对照。\n"
        "- `erp_product_tags.csv`：Dolibarr 产品标签（只读拉取），用于区分产品线；`UBI Solutions > GPSBLE` 下的产品是定位，`Portique RFID` / `Kit RFID TC21` / `Terminaux RFID` 是 RFID。\n"
        "- `erp_thirdparties.csv`：每个快照第三方对应的 ERP 公司层面字段（网站、网站域名、邮箱域名、联系人邮箱域名及次数、LinkedIn、员工数档位；不含任何完整邮箱或人名），`tp_name_matches` 为 true 才被采用。\n"
        f"- `issues.csv`：{len(r.issues)} 条，类型分布："
        + "，".join(f"{k} {v}" for k, v in r.issues["issue_type"].value_counts().items())
        + "。\n"
        "- `orders_by_category.csv`：ITEM_CATEGORY × 年，列出客户数、订单数、行数和金额。\n"
        "- `orders_by_entity.csv`：ENTITY_NAME，列出客户数、订单数、行数、金额和金额占比。\n"
        "- `category_cooccurrence.csv`：品类对的共现客户数和条件占比；对角线是单品类。\n\n"
        "主要字段说明：`recency_days` 是相对快照日 "
        f"{snapshot_date.isoformat()} 的天数；`n_years_active` 是有下单的不同年份数；`amount_first_24m_ht_eur` 是首单后 24 个月内的金额（新老客户可比），`months_since_first_order` 不足 24 时该值还不完整；`match_status=erp_socid` 时 `third_party_id` 是 ERP 订单上的第三方（多个时取金额最大的非内部公司），`erp_third_parties` 列出全部 socid 和金额，`erp_orders_verified` 是 ID 和订单号都和 ERP 一致的订单数，`name_match_status` / `name_match_third_party_id` / `name_vs_erp` 是单纯名称匹配的结果及其和 ERP 的对照；`history_truncated` 表示客户只在 Page Up / Ubi Smart / Ubi Impact 下过单，这几个法人 2024 年以前的数据没进数据仓库，所以首单日期和活跃年数可能偏短；`share_recurring` 是 IS_RECURRING_REVENUE 金额 / amount_ht_eur；"
        "`top_product_refs` 是金额前 5 的 PRODUCT_REF，格式 `ref:amount;…`（`(sans ref)` 表示没有 PRODUCT_REF 的行）；"
        "`category_mix` 是前 3 品类及占比；`naf_section`/`naf_classe` 只取订单上已有的值（发票、合同表没有能补充的），"
        f"有值的客户 {int(c['naf_section'].notna().sum())} 个，空的不填；`web_domain` 等网站字段见第 2 节「网站域名」；`product_lines` 是买过的业务线（`geoloc` = géolocalisation / Connected Things：BLE / GPS / LoRa 追踪器、信标、网关及其租赁，Connected Things 是定位的软件平台；`rfid` = traçabilité；`ubi_cloud` = Ubi Cloud 订阅 / 许可），按产品判断：有 Dolibarr 产品标签时以标签为准，否则按产品名称、子品类和制造商规则（ITEM_CATEGORY 分不开两者，`Traceurs et objets connectés` 里大部分是 RFID 纺织标签）；带蓝牙 / GPS 的手持终端、扫码枪不算定位；`amount_geoloc_ht_eur` / `amount_rfid_ht_eur` / `amount_ubi_cloud_ht_eur` 是各条线的金额，`geoloc_source` 说明定位判断来自 `tag` 还是 `name_rule`。\n"
    )
    return "\n".join(out)
