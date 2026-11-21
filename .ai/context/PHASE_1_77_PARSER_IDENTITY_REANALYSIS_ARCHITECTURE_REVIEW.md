# PHASE 1.77
## Parser Identity & Reanalysis Architecture Design Review

**Task Type:** PARSER IDENTITY & REANALYSIS ARCHITECTURE DESIGN REVIEW
**Phase:** 1.77
**Execution Mode:** STRICT READ-ONLY AUDIT + ARCHITECTURE DESIGN
**Implementation:** PROHIBITED（未实施任何方案）
**Formal Data Mutation:** PROHIBITED（8 个受保护清单 8/8 与 Batch E 完全一致）
**Git Mutation:** PROHIBITED（未 stage / commit / push / reset / checkout / clean）
**前置:** Phase 1.76 Batch E = `PASS_WITH_LIMITATIONS` / `READY_FOR_FUTURE_DESIGN_REVIEW`

---

## A. Executive Summary

本阶段回答一个问题：**当前的 Parser / Adapter / Analysis 身份体系，是否足以支撑未来的受控 Reanalysis 而不破坏历史身份或污染正式 Evidence？**

审计结论（全部来自真实源码与真实数据，见 Q 节）：

| 发现 | 证据 |
|---|---|
| `PARSER_VERSION` 直接参与 Analysis ID 计算 | `external_code_understanding.py:52-54` |
| 34 条正式记录的 ID **在 1.71 下 34/34 可复算，在 1.75 下 0/34** | 只读复算实验 |
| 34 条正式记录**没有** `parser_build_identity`，且**完全没有 coverage 字段**，`parser_version` 全为 `1.71` | 逐条读取 `analysis/*.json` |
| 当前实构建身份 = `gd_parse@1.75+build:3b36069a44beb55c`，Batch B 记录值 = `…6b74a6cd20a06033` | `corpus_audit_176.parser_build_identity()` 复算 |
| Build Identity 只存在于 Batch B 的 manifest/preflight，**不在任何 Analysis 记录中** | 29/29 重分析记录均无该字段 |
| `write_record` 无存在性守卫，直接 `write_text` 覆盖同名文件 | `external_code_understanding.py:378-385` |
| 版本一旦 bump，34 条 ID 全部改变；`linkage_id = f(analysis_id, feature_id)`，150 条 Linkage 全部失去关联 | `_analysis_id`、`feature_linkage.py:192-194` |
| Batch B 用硬编码 `EXPECTED_IDENTITY` 做前置门禁，Build 一变即拒绝运行 | `reanalysis_176.py:51,236` |
| 来源身份里 **`source_digest` 不参与 ID**，只有 `input_digest`（Reference 副本字节）参与 | `_analysis_id` 签名 |

**核心判定：现有身份模型不足以安全支撑 Reanalysis。** 它能识别“版本变了”，却无法识别“同一版本内实现变了”，而后者已经在 Batch E 真实发生过。

**Verdict: `PASS_WITH_LIMITATIONS`**
**Readiness: `READY_FOR_IDENTITY_IMPLEMENTATION_DESIGN`**

关键限制：本阶段只做设计与证据，未实现任何字段；Build Identity 的生成时机、回填策略与下游门禁仍是设计建议，尚未落地。

---

## B. Baseline & Repository Integrity

### B.1 Git 基线（实测）

| 项 | 值 |
|---|---|
| Project Root | `F:/Godot_v4.7-stable/game`（`/f/Godot_v4.7-stable/game`） |
| Branch | `master` |
| HEAD | `d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84` |
| Staged | **0** |
| Deleted | 0 |
| Modified | **31** 个已跟踪文件（含 `.ai/tools/learning/gd_parse.py`、`AI_ENTRY.md`、`AGENT_ONBOARDING.md` 及既有 Phase 1.7x 产物） |
| Untracked | **593** 个文件（`git status --porcelain` 显示 145 行，因未跟踪目录被折叠；展开后 593 个文件），含 `.ai/context/PHASE_1_5x–1_77` 报告、`.ai/tools/external_code/`、`.ai/learning/external_code/` 整棵树 |
| 本阶段新增修改 | **0 个已跟踪文件**（`gd_parse.py` 的 M 状态继承自 Batch E，mtime 早于本阶段起点） |

已识别并保留既有未提交修改，未清理、未覆盖、未重新归类任何一项。`HEAD` 与 Batch E 完成时一致，说明本阶段未产生 Git 写。

### B.2 受保护数据清单（Batch E 同一清单方案，实测）

| 路径 | 文件数 | SHA-256 | 与 Batch E 对比 |
|---|---|---|---|
| `.ai/learning/external_code/analysis` | 34 | `8202f322fe5cb166f3a2aaaf15617f53a708077a6794a8dc6a60be33e16b9a0c` | IDENTICAL |
| `.ai/learning/external_code/feature_links` | 150 | `ce7edc060a5d7917712d8ea0292069d4019c95a9bb52b3e48c935724faa48cd4` | IDENTICAL |
| `.ai/learning/external_code/reanalysis` | 191 | `53859cb96641bfae9ef146bae262a048b391d28ee0af30be656450e0e666da9c` | IDENTICAL |
| `.ai/learning/external_code/reconciliation` | 1 | `66ba91f05f00325b74d71f2029ee80210c661101d56cfd433e4d2d205d9dfb62` | IDENTICAL |
| `.ai/learning/external_code/evidence_impact` | 8 | `c1abd1ba2150818abe3b60732ab0695de316a759a46e8b80f5d351c2a8386695` | IDENTICAL |
| `.ai/learning/external_code/evidence_review` | 6 | `0220a4840cd1224a957a87d9a419c0856ba05eb081cf485c966a248423730be6` | IDENTICAL |
| `.ai/learning/candidate_workspace` | 3 | `b991d4f547266ea60980f1cf781ae735c5a8e9014699aa79662fca4c19f4491d` | IDENTICAL |
| `code_library`（sources + references，含 `.gd`/`.json`/`.md`） | 13 807 | `87af1d7f1ba7abce6cf127d28bc1ed2a35bdd3debc78880c1c5ab09a560606f5` | IDENTICAL |

本阶段内被写入的受保护文件：**0**。目录结构与任务书描述一致，未创建任何替代目录。

### B.3 Parser 相关文件审计清单

| 文件 | 角色 | 本阶段 |
|---|---|---|
| `.ai/tools/learning/gd_parse.py` | 语法解析器，输出 `Script.coverage` | 只读 |
| `.ai/tools/external_code/external_code_understanding.py` | Adapter：身份、digest、记录序列化 | 只读 |
| `.ai/tools/external_code/corpus_audit_176.py` | 定义 `parser_build_identity()` | 只读 |
| `.ai/tools/external_code/reanalysis_176.py` / `reanalysis_175.py` | 受控重分析执行器与前置门禁 | 只读 |
| `.ai/tools/external_code/feature_linkage.py` | Linkage 身份 | 只读 |
| `.ai/tools/feature_registry/candidate_eligibility.py` / `candidate_workspace.py` | Candidate 资格与工作区 | 只读 |
| `.ai/tools/learning/tests/test_gd_parse.py` / `test_coverage_reporting.py` / `test_source_analysis.py` | 测试 | 只读 |

---

## C. Parser Identity Source Audit（源码定位）

| 关注点 | 位置 | 实测结论 |
|---|---|---|
| `PARSER_VERSION` 定义 | `external_code_understanding.py:37` → `"1.75"` | 单一常量，无独立 build/protocol 字段 |
| `PARSER_NAME` | 同文件 `:36` → `"gd_parse"` | 参与 ID |
| `_analysis_id` 定义 | `:52-54` | `"ext-" + sha256("repo|commit|source_path|input_digest|gd_parse|PARSER_VERSION")[:16]` |
| `_analysis_id` 调用点 | 仅 `_base_record():173-174`（唯一调用方） | ID 只在建记录时生成一次 |
| `input_digest` | `:220` `_digest(raw)`，`raw` 为 Reference 副本字节 | 参与 ID |
| `source_digest` | `:258` 对 pinned source 字节计算 | **不参与 ID** |
| `parser_version` 写入 | `:191` | 从常量写入记录 |
| Build Identity 计算 | `corpus_audit_176.py:47-65` | `sha256(gd_parse.py ‖ 0x00 ‖ adapter.py)`，取前 16 位，格式 `gd_parse@<version>+build:<16hex>` |
| Build Identity 写入 | Batch B `manifest.json` / `preflight.json` | **不在任何 Analysis 记录中** |
| 记录保存 | `write_record():378-385` → `analysis/<analysis_id>.json` | 无存在性检查、无版本后缀、无 supersedes |
| 索引重建 | `build_index():387-424` → `index.json`（键名 `analyses`） | 条目只带 `analysis_id` 与摘要字段，无 `parser_version` |
| Source / Reference 选择 | `_base_record()`：`source_dir/gd/<repo_path>` 为 pinned source，`path` 参数为 Reference 副本 | 两者分别计算 digest |
| 身份消费方 | `feature_linkage.py`、`candidate_eligibility.py`、`candidate_workspace.py`、`search_assets.py`、`evidence_impact_176.py`、`manual_evidence_review_176.py`、`reanalysis_176.py` | 见 K 节 |

---

## D. Current Identity Model（还原后的真实模型）

| Identity Component | 真实实现 | 说明 |
|---|---|---|
| `PARSER_VERSION` | 人工声明的单一字符串 `"1.75"` | 同时充当“协议版本 + 实现版本”，无独立语义区分 |
| Parser Build Identity | `sha256(gd_parse.py ‖ 0x00 ‖ adapter.py)[:16]` | 存在，但**只由工具侧计算**，未持久化到 Analysis |
| Analysis ID | `ext-` + sha256(repo, commit, source_path, **input_digest**, parser_name, **parser_version**)[:16] | 版本参与，实现不参与 |
| Source Identity | repo + commit + source_path + `source_digest` | `source_digest` **不参与** Analysis ID |
| Input Identity | `input_digest` = Reference 副本字节摘要 | 参与 Analysis ID，是唯一进入 ID 的内容摘要 |
| Output Identity | **不存在** | 正式记录不保存输出摘要；Batch B 仅在 diff/manifest 侧计算 `content_digest` |
| Analysis Provenance | `provenance_status=complete`（34/34），含 `commit_sha`、`commit_sha_full`、`immutable_source_url`、`source_url`、`repo`、`source_path` | 可追溯来源，**不可追溯实际执行的 Parser 实现** |

关键结论：**Analysis ID 是“来源 + 参考副本 + 版本字符串”的函数，不是“实际 Parser 实现”的函数。** `source_digest` 与 build identity 都不在 ID 内。

### D.1 Analysis ID 可复算性实验（只读、内存计算）

| 实验 | 结果 |
|---|---|
| 用 `1.71` 复算 34 条 ID | **34 / 34 完全一致** |
| 用 `1.75` 复算 34 条 ID | **0 / 34** |
| 用 `1.76` 复算 34 条 ID | **0 / 34** |
| `input_digest` 与 Reference 文件当前字节一致 | 34 / 34 |
| Reference 文件存在 | 34 / 34 |
| 版本 bump 到 1.75 会导致 ID 改变 | **34 / 34** |
| Batch B 的 `reanalysis_id` 用 1.75 复算 | 33 / 34（例外为 `ext-80c1104f5262a6ee`，`NOT_APPLICABLE` 的 shader，其 `reanalysis_id` 为 `null`，非身份冲突） |
| `linkage_id` 复算 | 150 / 150 |
| `index.json` 条目 ID 与正式记录集合一致 | 是（34 / 34） |

这说明：**正式记录的 ID 是 1.71 契约下的产物，当前代码常量已是 1.75。** 若今天重跑 Adapter，34 条全部生成新 ID，旧记录不会被覆盖（发生分叉），而 Batch B 的 29 条重分析记录已经是 1.75 身份下的“影子正式记录”，只是从未提升。

---

## E. Identity Conflict Analysis

### Case A — 同一 Parser Version，不同实现（**已在 Batch E 实际发生**）

- `PARSER_VERSION` 两侧都是 `1.75`。
- Build Identity：Batch B = `gd_parse@1.75+build:6b74a6cd20a06033`（`gd_parse.py` = `d7593797…`，adapter = `30b9efcc…`）；当前 = `gd_parse@1.75+build:3b36069a44beb55c`（`gd_parse.py` = `f56aa340…`，adapter = `fa30686a…`）。
- **是否产生相同 Parser Identity？** 声明的 version 相同；工具侧 build identity 不同。系统内没有任何正式记录携带 build identity，因此**正式数据侧无法检测这次变化**。
- **是否生成相同 Analysis ID？** 是——`repo/commit/path/input_digest/version` 全部未变，ID 完全相同。
- **是否可能覆盖或混淆？** `write_record` 无守卫：若对同一 Reference 重跑 Adapter，会**静默覆盖同 ID 文件**，旧内容无副本、无 `supersedes`、无差异记录。
- **现有系统能否检测？** 只有 Batch B 那套工具内部的硬编码 `EXPECTED_IDENTITY` 会拒绝运行；正式数据层与 Candidate/Linkage 层都无法察觉。

**判定：这是当前体系中最严重的身份缺陷 —— 已被真实触发，且不可观测。**

### Case B — 直接 bump `PARSER_VERSION`

- ID 变化：**34/34 全变**（已实测）。
- 历史 Analysis 是否被视为新记录：会生成 34 个新文件，旧文件仍在，形成同源双版本。
- Linkage：`linkage_id = sha("phase-1.73-b|<analysis_id>|<feature_id>")`，150/150 全部改变；旧 Linkage 指向旧 ID，仍可读但不再对应最新分析。
- Candidate / Seed：`candidate_workspace` 与 `candidate_eligibility` 的 `evidence_refs` 记录 `analysis_id`，会指向旧 ID；Seed 政策未以 `parser_version` 为门禁（见 K 节），因此**不会自动阻断**。
- 历史引用：`index.json` 需重建；`evidence_impact` / `evidence_review` 中的引用仍指向旧 ID。

**判定：bump 版本是“可追溯的分叉”，不是破坏；但会产生 150 条 Linkage 的孤儿化，需要一次受控重建。**

### Case C — 只改 Build Identity（版本不变）

- Analysis 逻辑身份可保留（ID 不变），但**同 ID 不同内容**成为必然。
- 区分不同构建结果：当前**无法**，除非 Build Identity 进入记录或文件名。
- 避免覆盖：必须引入存在性守卫与“新记录不覆盖旧记录”的写入策略。
- 比较输出：可复用 Batch B 的 `canonical()` + `content_digest()` 机制。

**判定：可行且低风险，但必须先解决“同 ID 覆盖”问题。**

### Case D — 只改 Adapter（Parser 不变）

- 当前 build identity 把 adapter 字节并入：adapter 变化同样改变 build identity。
- 是否需要独立 Adapter Identity：需要。Batch E 就是“Parser 符号输出不变、Adapter 坐标投影与序列化变化”的实例，二者若共用一个 build 字符串，就无法说明变化到底来自语法还是坐标。
- Parser 输出相同、Record 输出不同：只能靠 Record 级输出摘要区分，当前不存在。

### Case E — 只改 Coverage Reporting

Batch E 的变更属于此类：构造码改名、`analysis_completeness` 派生修正、`line_coordinates` 扩展、残差扫描新增。

| 变化 | 应归属 |
|---|---|
| 新增/改名 `unsupported_constructs[].code` | **Parser Output Contract**（消费者会读到新码） |
| `analysis_completeness` 派生规则 | **Parser Output Contract** |
| `line_coordinates` / `source_line` / `record_line` 结构 | **Adapter Output Contract**（投影由 Adapter 完成） |
| 记录字段仍为 `schema_version=1` | **Analysis Schema 未变**（字段只增不减，旧读者可忽略新键） |

**判定：不应以 `PARSER_VERSION` 承担契约语义。契约变化需要独立的 contract 版本，且必须进入 Reanalysis 判定。**

---

## F. Candidate Identity Architectures

### F.1 Architecture A — Version-Centric Identity（以版本为核心）

- 保持单一 `parser_version`，任何影响输出的变化都 bump 版本。
- Build 差异不用单独字段表示；通过版本号单调递增隐含表达。
- 历史兼容：旧记录保留旧版本号，ID 由版本决定，天然分叉。
- Adapter 变化：也计入同一版本序列（或另设 `adapter_version`，否则无法区分）。
- Analysis ID：保持当前公式，随版本变化。

| 优点 | 缺点 |
|---|---|
| 改动最小，不新增字段 | 版本号被当作“实现指纹”使用，人工填写、无法验证 |
| ID 天然区分新旧 | 同版本内实现变化依然不可见（正是 Batch E 的情况） |
| 无迁移成本 | 每次契约微调都要 bump 版本，ID 与 Linkage 全线漂移 |

**不可单独采用**：无法解决 Case A 与 Case D。

### F.2 Architecture B — Build-Aware Identity（版本与构建分离）

| 字段 | 职责 | 生成方式 | 必填 | 允许空 | 可继承历史 | 参与 Analysis ID | 参与 Reanalysis 判定 | 需回填 |
|---|---|---|---|---|---|---|---|---|
| `parser_version` | 人类可读的能力/协议标签 | 源码常量 | 是 | 否 | 是（旧值保留） | **否**（建议） | 是 | 否 |
| `parser_build_identity` | 实际执行实现指纹 | `sha256(gd_parse.py)[:16]`（或 git blob sha） | 是（新记录） | 仅历史记录 | 否——历史值不得伪造 | 建议**否** | 是（核心） | 仅写 `NOT_AVAILABLE` 标记，不填值 |
| `parser_output_contract` | 构造码、completeness 规则、坐标字段契约 | 语义化标签 + 契约清单摘要 | 是 | 否 | 是 | 否 | 是 | 否 |
| `adapter_build_identity` | Adapter 实现指纹 | `sha256(adapter.py)[:16]` | 是 | 否 | 否 | 否 | 是 | 标记 `NOT_AVAILABLE` |
| `adapter_version` | Adapter 契约标签 | 常量 | 是 | 否 | 是 | 否 | 是 | 否 |
| `analysis_schema_version` | 记录结构版本（已有，=1） | 常量 | 是 | 否 | 是 | 否 | 是（结构不兼容时迁移） | 否 |
| `output_digest` | 记录内容稳定摘要（排除时间戳） | `canonical()` + sha256 | 建议是 | 是（旧记录） | 否 | 否 | 是（检测“同身份不同输出”） | 标记 `NOT_AVAILABLE` |

**必须进入 Build Identity 的因素**：Parser 源码字节（唯一决定语法与 coverage 的输入）。
**只作为 Provenance 记录的因素**：git commit（便于人读）、依赖版本（本项目无第三方解析依赖）、运行环境（Python 3.12，纯标准库）、平台（无平台相关输出）、影响结果的配置（`KNOWN_ANNOTATIONS` 等均在源码内，随字节变化）。

**为什么 Adapter 用独立身份**：Batch E 证明二者会独立变化，且 Adapter 决定坐标与序列化。

**生成必须可验证**：`parser_build_identity` 由工具在运行时计算并写入记录，评审时可复算；不接受人工填写的“看起来像版本号”的字符串。

### F.3 Architecture C — Layered Identity（分层身份，推荐方向）

四层，各自独立演进：

```
Layer 1  Parser Implementation   parser_build_identity = sha256(gd_parse.py)[:16]
Layer 2  Parser Output Contract   parser_output_contract = "<semver>+codes:<16hex>"
Layer 3  Adapter                  adapter_build_identity + adapter_version
Layer 4  Analysis Schema          analysis_schema_version (existing, =1)

Analysis identity key =
    (repo, commit, source_path, input_digest, source_digest)
       └─ 内容身份（Content Identity）：决定“分析的是哪份输入”

Analysis ID = ext- + sha256(content identity)[:16]        ← 建议与 Parser 解耦
Record identity key = (Analysis ID, parser_build_identity, adapter_build_identity)
       └─ 记录身份：同源输入 + 不同实现 ⇒ 不同记录，互不覆盖
```

依赖关系：L1 产出的符号/coverage 被 L3 投影，L2 约束 L1 的输出契约，L4 描述记录结构；Analysis ID 只依赖内容身份，因此**Parser 升级不再导致 ID 漂移**，Linkage/Candidate 无需重建即可指向“同一输入的新分析”，由记录级身份区分实现。

---

## G. Architecture Comparison

| 评价维度 | A 版本核心 | B 构建感知 | C 分层 |
|---|---|---|---|
| 历史记录兼容 | 高（无需迁移） | 中（旧记录缺 build，需显式 `NOT_AVAILABLE`） | 中高（ID 不变，新增记录层） |
| Build 可追溯性 | 低（人工版本号） | 高 | 高 |
| Analysis ID 稳定性 | 低（版本一变全漂移） | 低（仍含版本） | **高**（与实现解耦） |
| Reanalysis 判定能力 | 弱（只能比版本） | 强 | 强（四层各自触发） |
| Adapter 独立升级 | 无 | 有 | 有 |
| Schema 演进 | 无 | 有 | 有 |
| 实现复杂度 | 低 | 中 | 中高（需双键记录） |
| 数据迁移风险 | 无 | 中（回填标记） | 中（ID 语义变更需迁移映射） |
| 历史 Seed 兼容性 | 高 | 高 | 需一次性映射表（旧 ID → 内容身份） |

**可行性证据**：
- A 不可行（单独）——Batch E 已证明同版本内实现变化不可观测，A 无法表达该事实。
- B 可行，但 ID 仍含版本，Case B 的 150 条 Linkage 漂移无法避免。
- C 可行且解决全部 Case，代价是引入“记录级身份”与一张迁移映射表。

**推荐：C 为目标架构，以 B 作为过渡阶段落地形态**（先引入 `parser_build_identity` / `adapter_build_identity` / `parser_output_contract`，再逐步把版本从 ID 中移出）。理由：C 的收益全部来自记录级身份，而 B 已经提供了该身份所需的字段；分两步可以在不打断现有 Linkage 的前提下完成迁移。此为 `DESIGN_RECOMMENDATION`。

---

## H. Reanalysis Trigger Classification

| # | 触发条件 | 必须动作 | 说明 |
|---|---|---|---|
| 1 | Source commit 改变 | **REANALYZE**（输入来源变了） | 当前 commit 不参与 digest，需同时核对 `source_digest` |
| 2 | `source_digest` 改变 | **REANALYZE** | 该值目前不参与 ID，必须靠判定而非 ID 发现 |
| 3 | `input_digest` 改变 | **REANALYZE**（ID 也会变） | Reference 副本变更等价于新输入 |
| 4 | `parser_build_identity` 改变 | **REANALYZE（评审后）** → 先 `EVALUATE` | 符号输出可能变化；Batch E 即此类 |
| 5 | `parser_output_contract` 改变 | **EVALUATE → 可能 RECORD_MIGRATION** | 构造码/派生规则变化，未必影响符号 |
| 6 | `adapter_build_identity` 改变 | **EVALUATE → 可能 RECORD_MIGRATION** | 坐标/序列化变化；Batch E 亦属此类 |
| 7 | `analysis_schema_version` 改变 | **RECORD_MIGRATION**（结构不兼容时 `REANALYZE`） | 旧读者可能无法解析 |
| 8 | Coverage reporting 规则改变 | **REVALIDATE + EVALUATE** | 不影响声明的存在性，只影响报告文本 |
| 9 | Provenance 不完整 | **MANUAL_REVIEW** | 无法确认来源时不得自动重跑 |
| 10 | 历史 Analysis 身份不可信 | **MANUAL_REVIEW** | 例如 ID 无法复算 |
| 11 | Analysis 输出缺失或损坏 | **REANALYZE**（若输入仍在） | 输出不可用 |
| 12 | Parser Build 无法确认 | **MANUAL_REVIEW** | 不得用当前 Build 冒充历史 Build |

---

## I. Reanalysis Decision Matrix

| Source | Input | Parser Build | Adapter | Schema | Recommended Action |
|---|---|---|---|---|---|
| Same | Same | Same | Same | Same | `REUSE` |
| Changed | Same/Changed | Same | Same | Same | `REANALYZE` |
| Same | Changed | Same | Same | Same | `REANALYZE`（ID 已变） |
| Same | Same | **Changed** | Same | Same | `EVALUATE` → 符号变化则 `REANALYZE`，仅报告变化则 `RECORD_MIGRATION` |
| Same | Same | Same | **Changed** | Same | `EVALUATE` → 坐标/序列化变化则 `RECORD_MIGRATION`，否则 `REVALIDATE` |
| Same | Same | Same | Same | **Changed** | `RECORD_MIGRATION`；结构不兼容则 `REANALYZE` |
| Same | Same | Same | Same | Same（但 coverage 契约变） | `REVALIDATE` |
| Unknown | Unknown | Unknown | Unknown | Unknown | `MANUAL_REVIEW` |
| — | — | Build 无法确认 | — | — | `MANUAL_REVIEW` |
| 文件为 shader / 非 GDScript | — | — | — | — | `NOT_APPLICABLE` |

判定顺序建议：`NOT_APPLICABLE` → `MANUAL_REVIEW`（来源/输入不可信）→ `REANALYZE`（输入变化）→ `EVALUATE`（实现变化）→ `RECORD_MIGRATION`/`REVALIDATE` → `REUSE`。

---

## J. Reanalysis Record Model（非破坏性）

```text
analysis_id             现有内容身份派生 ID（建议：component = repo|commit|path|input_digest|source_digest）
previous_analysis_id    （建议新增）被本记录取代的旧记录 ID
reanalysis_of           （建议新增）旧记录 ID；与 previous_analysis_id 二选一，语义更明确的推荐
supersedes              （建议新增）布尔或列表：仅表示“逻辑上取代”，不删除旧文件
parser_version         现有
parser_build_identity   （建议新增）运行时计算的实际实现指纹
parser_output_contract  （建议新增）输出契约标签
adapter_version / adapter_build_identity （建议新增）
output_digest           （建议新增）canonical 记录摘要
trigger_reason          （建议新增）对应 H 节编号 + 人类可读原因
reanalysis_run          （建议新增）运行标识，与 Batch B 的 workspace 对齐
```

**关键约束**：
1. Reanalysis **只新增记录**，从不覆盖旧记录；旧记录保持可读、可引用。
2. 新旧通过 `reanalysis_of` / `previous_analysis_id` 双向可追溯（旧记录侧建议追加 `superseded_by`，但只在授权迁移时写入）。
3. 不同 Parser Build 的结果落在不同记录（记录级身份），因此可以并存与比较。
4. Batch B 已经实践了该模型的雏形（`original/`、`reanalyzed/`、`diff/`、`manifest.json`），只是尚未提升为正式记录结构。

---

## K. 幂等性与确定性设计

| 问题 | 设计回答 | 现状证据 |
|---|---|---|
| 相同 Source / Input / Parser Build 是否产生相同结果 | 应产生**逐字节等价**（排除时间戳）的记录 | Batch B 已实现 `canonical()` + `content_digest()`，并对每条分析执行两次内存比对（`deterministic_runs/`、`idempotency/`） |
| 相同身份是否允许不同输出 | 不允许；若出现即视为缺陷或环境差异 | `VOLATILE` 字段（`created_at` 等）是唯一允许的差异 |
| 输出不同如何检测 | 记录 `output_digest`，重跑后比对 | 当前正式记录**没有**该字段，只能整体 diff 文件字节 |
| 区分非确定性与环境差异 | 记录解释器版本与 Build Identity；确定性失败即报错而不是重试 | Batch B 的两次运行比对已覆盖 |
| 重复执行是否产生重复 Analysis | 旧行为：同 ID 覆盖（危险）；建议：同双键则视为同一次分析，写入前比对 `output_digest` | `write_record` 无守卫（已确认） |
| 中断/失败/部分生成 | 写入临时文件后原子替换；失败记录写入 workspace 的失败清单，不产生半条正式记录 | 现行 Adapter 直接 `write_text`，无原子保证 |

---

## L. Batch B / Batch E Historical Compatibility

### L.1 34 条正式 Analysis 逐条清单（只读，实测）

所有记录的 `parser_version = 1.71`、`syntax_coverage_status`/`analysis_completeness` = **NOT_AVAILABLE（字段不存在）**、`parser_build_identity` = **NOT_RECORDED**、`provenance_status = complete`、`schema_version = 1`。

| Analysis ID | Repository | Commit | Source Path | Linkage | analysis_status |
|---|---|---|---|---|---|
| `ext-1d204b35464cf388` | gdquest-demos/godot-make-pro-2d-games | 7290681 | actors/health/Stats.gd | 5 | analysis_partial |
| `ext-23949c1378c49203` | bitbrain/beehave | fe58915 | addons/beehave/blackboard.gd | 5 | analysis_partial |
| `ext-27ddd863881677d7` | bitbrain/beehave | fe58915 | addons/beehave/nodes/leaves/blackboard_… | 5 | analysis_partial |
| `ext-2a4f612899a6b6a5` | gdquest-demos/godot-make-pro-2d-games | 7290681 | actors/hit_box/HitBox.gd | 5 | analysis_partial |
| `ext-409141da889d20af` | nezvers/Godot-GameTemplate | d5d8d15 | addons/top_down/scripts/damage/ActorDamage… | 5 | analysis_complete |
| `ext-40ab1c0330e01d7f` | alfredbaudisch/Godello | 4458a14 | scripts/drag_utils.gd | 5 | analysis_complete |
| `ext-43748f09c01294f9` | gdquest-demos/godot-open-rpg | d59f2f7 | src/field/cutscenes/templates/doors/door… | **0** | analysis_partial |
| `ext-4b7782ce66be92a7` | alfredbaudisch/Godello | 4458a14 | addons/uuid/uuid.gd | 5 | analysis_complete |
| `ext-51d46c1b4943a254` | gdquest-demos/godot-open-rpg | d59f2f7 | src/field/cutscenes/templates/doors/door… | 5 | analysis_partial |
| `ext-51fbb1e2b03c3f67` | ceceppa/anima | f4a454e | addons/anima/motion/runtime/anima_race_… | 5 | analysis_complete |
| `ext-55aef2d453370c1b` | bitbrain/beehave | fe58915 | addons/beehave/nodes/leaves/blackboard_… | 5 | analysis_partial |
| `ext-56ca48126ec8514d` | alfredbaudisch/Godello | 4458a14 | scripts/events.gd | 5 | analysis_partial |
| `ext-5a8d53c7f530e4af` | gdquest-demos/godot-open-rpg | d59f2f7 | overworld/maps/town/door_unlock_interact… | **0** | analysis_partial |
| `ext-5adc6644d3347390` | Ark2000/PankuConsole | 863324d | addons/panku_console/modules/interactive… | 5 | analysis_partial |
| `ext-6f85edf0730ee075` | gdquest-demos/godot-make-pro-2d-games | 7290681 | core/world/Door.gd | 5 | analysis_partial |
| `ext-73c80a3db6d71e48` | nezvers/Godot-GameTemplate | d5d8d15 | addons/top_down/scripts/damage/HealthRes… | 5 | analysis_complete |
| `ext-7973e94ee75e2819` | nezvers/Godot-GameTemplate | d5d8d15 | addons/top_down/scripts/actor/bots/Proxi… | 5 | analysis_complete |
| `ext-7d7933a2343f52d0` | gdquest-demos/godot-open-rpg | d59f2f7 | src/combat/ui/battler_entry/ui_life_bar.… | 5 | analysis_complete |
| `ext-80c1104f5262a6ee` | Ark2000/PankuConsole | 863324d | addons/panku_console/res/shader/simple_f… | **0** | unsupported_shader |
| `ext-9e62ed2e3dec8164` | alfredbaudisch/Godello | 4458a14 | scripts/board_member_button.gd | 5 | analysis_partial |
| `ext-9f0aad5e01dd71f7` | gdquest-demos/godot-make-pro-2d-games | 7290681 | interface/gui/player/life_bar/Lifebar.gd | 5 | analysis_partial |
| `ext-aa0204cc227b0480` | derkork/godot-statecharts | 76d226a | addons/godot_state_charts/animation_tree… | 5 | analysis_partial |
| `ext-ab693f3d6ef9439c` | lampe-games/godot-open-rts | a628ad3 | source/match/units/traits/HealthBar.gd | **0** | analysis_partial |
| `ext-bfe9b7e6dbebbfae` | blackears/cyclopsLevelBuilder | ea41fea | godot/addons/cyclops_level_builder/actio… | 5 | analysis_partial |
| `ext-c341755c352c7563` | lampe-games/godot-open-rts | a628ad3 | source/match/units/actions/AutoAttacking… | 5 | analysis_partial |
| `ext-c7b0d12daf86d973` | gdquest-demos/godot-make-pro-2d-games | 7290681 | actors/DamageSource.gd | 5 | analysis_partial |
| `ext-d5f7ac2db3a8c4e4` | gdquest-demos/godot-open-rpg | d59f2f7 | src/combat/actions/battler_action_attack… | 5 | analysis_complete |
| `ext-d82bd2e536c75c4a` | nezvers/Godot-GameTemplate | d5d8d15 | addons/top_down/scripts/ui/game_screen/H… | 5 | analysis_complete |
| `ext-d9764c3981017194` | gdquest-demos/godot-make-pro-2d-games | 7290681 | actors/health/Status.gd | 5 | analysis_partial |
| `ext-ec789727924bfa6c` | foxssake/netfox | cf5189d | examples/forest-brawl/scripts/play-rando… | 5 | analysis_complete |
| `ext-f80d07f302bacc20` | cis-ash/TEXTREME | 673dc09 | Scenes/EffectParameterSelector/EffectPar… | 5 | analysis_complete |
| `ext-fb806b579659b155` | foxssake/netfox | cf5189d | examples/multiplayer-state-machine/scrip… | 5 | analysis_partial |
| `ext-fe3acf782b88edda` | Ark2000/PankuConsole | 863324d | addons/panku_console/modules/history_man… | 5 | analysis_partial |
| `ext-fffa637657ffede1` | alfredbaudisch/Godello | 4458a14 | scripts/board_card.gd | 5 | analysis_partial |

汇总：34 条 / 12 个 repo / 12 个 commit；`analysis_complete` 11、`analysis_partial` 22、`unsupported_shader` 1；Linkage 共 150 条，覆盖 30 条分析，**4 条无 Linkage**（`ext-43748f09c01294f9`、`ext-5a8d53c7f530e4af`、`ext-ab693f3d6ef9439c`、`ext-80c1104f5262a6ee`＝shader）。

**需要未来 Reanalysis 的判定**：全部 34 条属于 `REANALYZE`（输入已存在、Parser 实现已变、且无 coverage 字段可复用）；其中 shader 一条为 `NOT_APPLICABLE`。这不是自动授权，只是证据支持的结论。

### L.2 Batch B Workspace（实测）

| 项 | 值 |
|---|---|
| 记录数 | 34 |
| `REANALYZED_AND_VALIDATED` | **29** |
| `REUSED_PHASE_1_75` | **4** |
| `NOT_APPLICABLE` | **1**（`ext-80c1104f5262a6ee`，shader） |
| 记录的 Build Identity | 全部为 `gd_parse@1.75+build:6b74a6cd20a06033`（仅存于 manifest 记录字段） |
| manifest 中的完整身份 | `identity_sha256=6b74a6cd…451221`、`gd_parse_sha256=d7593797…0a01485`、`adapter_sha256=30b9efcc…564adfbe`、`known_annotations=24` |
| `reanalyzed/` 文件数 | 29 |
| 29 条重分析的 `parser_version` | 全部 `1.75` |
| 29 条重分析的 coverage | COMPLETE/FULL 26、PARTIAL/FULL 3 |
| 29 条重分析记录是否自带 Build Identity | **0 / 29**（只在 manifest） |
| Workspace 子目录 | `deterministic_runs/`、`diff/`、`idempotency/`、`original/`、`reanalyzed/`、`reports/`、`validation/` |

回答任务书的六个问题：

1. **是否足以作为 Reanalysis 的可信比较基线？** 是——`original/` 保存旧记录、`reanalyzed/` 保存新记录、`diff/` 与 `manifest.json` 保存映射，且原记录 digest 可验证（`input_digest` 34/34、`source_digest` 34/34 一致）。
2. **是否保存了足够的 Parser 输出与 Provenance？** 输出足够（完整记录副本）；Provenance 只在 manifest 层，**记录级缺失**。
3. **哪些可复用？** 29 条重分析结果可在其 Build Identity 下复用；4 条 `REUSED_PHASE_1_75` 需要重新确认（它们复用的是 1.75 结果，与当前 1.75 实构建不同）。
4. **哪些需要重新验证？** 34 条全部需要（当前 Build 与 Batch B Build 不同，且 Batch E 修正了 claim/completeness）。
5. **哪些无法确认 Build Identity？** 34 条正式记录全部（字段不存在）；Batch B 的 29 条仅能通过 manifest 间接确认。
6. **是否存在无法恢复的历史信息？** 存在：Batch B 之前的 1.71 实现的 build identity 从未记录，**不可重建且不得伪造**；1.71→1.75 的契约差异也没有独立记录。

### L.3 Batch E 行为变化的身份影响

| 变化 | 类别 | 对身份的影响 | 对下游的影响 |
|---|---|---|---|
| `expand_to` / `title_label` 新增捕获 | **Parser Symbol Output Change** | 同一 Build 下符号表变大 | Candidate/Linkage 可能新增可匹配标识符；旧 Analysis 不含这些符号 |
| Legacy setget 构造码重分类 | **Coverage Metadata Change** | 记录内容变，ID 不变 | 读 `unsupported_constructs[].code` 的消费者会看到新码；`LEGACY_SETGET_NOT_INTERPRETED` 消失 |
| `line_coordinates` 扩展 | **Source Location Projection Change**（Adapter） | 记录内容变，ID 不变 | 依赖 `line` 的旧消费方必须改用 `source_line` |
| `analysis_completeness` 缺口判定修正 | **Coverage Metadata Change** | 部分文件从 `FULL` 变 `DECLARATION_GAPS` | 任何把 `FULL` 当质量门禁的逻辑会改变判定 |
| 顶层残差扫描新增 | **Parser Symbol Output + Coverage Change** | 声明与缺口同时增加 | 同上 |
| `LEGACY_EXPORT_HINT_ARGS_NOT_INTERPRETED` 等新码 | **Coverage Metadata Change** | 2 个文件由 COMPLETE 变 PARTIAL | Linkage/Candidate 不直接消费，但审阅结论会变 |

**综合影响**：Batch E 属 `EVALUATE` 级变化——不改变 Analysis ID，却实质改变记录内容与符号表。这正是现有模型最危险的盲区：**ID 相同、内容不同、无任何记录级痕迹**。

---

## M. Downstream Identity Consumption Audit（身份依赖图）

```text
analysis/<analysis_id>.json  ──┬─→ index.json（analysis_id + symbols 摘要）
                               ├─→ feature_linkage.py → linkage_id = sha(analysis_id|feature_id) → feature_links/*.json
                               ├─→ candidate_workspace.py → candidate.evidence_refs[].analysis_id
                               ├─→ candidate_eligibility.py → 资格判定（读 analysis_id、source_digest、provenance）
                               ├─→ search_assets.py → 以 snippet_id / analysis_id 为键
                               ├─→ evidence_impact_176.py / manual_evidence_review_176.py（阶段工具，读 parser_version + digests）
                               └─→ reanalysis_175/176.py（读 analysis_id、input_digest、source_digest、reference/source 文件）
```

| 组件 | 依赖什么 | 是否依赖 Parser Version | 是否假设“同 ID ⇒ 同输出” | 不同 Build 混用风险 |
|---|---|---|---|---|
| `index.json` | `analysis_id` + 摘要 | 否（条目无版本字段） | 是（ID 为唯一键） | **高**——新 ID 与旧 ID 并存时索引会同时列出两版 |
| `feature_linkage.py` | `analysis_id`、`source_digest`、重复 ID 检查 | 否 | 是（`linkage_id` 由 ID 派生） | **高**——版本 bump 后 150 条 Linkage 需重建 |
| `candidate_workspace.py` | `analysis_id`、`source_digest`（与 ref 比对） | 否 | 是 | **中**——同 ID 内容变化不会被发现 |
| `candidate_eligibility.py` | `analysis_id`、`source_digest`、provenance | 否（策略 JSON 无 parser 字段） | 是 | **中**——不会因 Parser 升级而失效，也不会阻断新结果 |
| `candidate_seed_policy.json` | 3 个 seed，`policy_version=phase-1.74-c/1` | **否**（仅文本提及“parser captured 1 of 5 @export vars”作为排除理由） | 不适用 | 低（但意味着 **Seed 不会自动因 Parser 变化而重评**） |
| `search_assets.py` | `analysis_id` / `snippet_id` | 否 | 是 | 中 |
| `evidence_impact_176.py` | `parser_name@parser_version`、digests | **是**（文本级） | 是 | 低（阶段工具，只读） |
| `manual_evidence_review_176.py` | digests、`parser_build_identity`（自算） | 是 | 是 | 低 |
| `reanalysis_176.py` | 硬编码 `EXPECTED_IDENTITY` | **是** | 是 | **低（这是唯一有效的保护）** |
| `feature_graph.json` | 无 `analysis_id` / `ext-` 引用 | 否 | 不适用 | 无 |
| `feature_evidence.py` | 项目内 `SOURCE` 引用，`parser_version="regex-v1"` | 否（独立体系） | 不适用 | 无 |

**结论**：
1. 只依赖 `Analysis ID` 的组件：`index.json`、`feature_linkage.py`、`candidate_workspace.py`、`candidate_eligibility.py`、`search_assets.py`。
2. 直接依赖 Parser Version 的组件：`evidence_impact_176.py`、`manual_evidence_review_176.py`、`reanalysis_176.py`（以及记录字段 `parser_version` 本身）。
3. 假设“同 ID 永远对应同一份输出”的组件：**除 `reanalysis_176.py` 外全部**。
4. 可能混用不同 Build 结果的组件：`index.json`、`candidate_workspace.py`、`candidate_eligibility.py`。
5. 需要兼容升级的消费方：`feature_linkage.py`（派生 ID）、`candidate_*`（证据引用）、`search_assets.py`。
6. 隐式身份推断：`evidence_impact_176.py:146` 用 `parser_name@parser_version` 拼出“正式 Parser 身份”，在缺 Build 时**等价于用版本号冒充实现身份**——这是必须显式标记 `NOT_AVAILABLE` 的地方。

---

## N. Migration & Rollout Strategy（未来实施建议，本阶段未执行）

### G1 — Identity Contract
定义并冻结字段语义：`parser_version`（标签）、`parser_build_identity`（实现）、`parser_output_contract`（输出契约）、`adapter_version`、`adapter_build_identity`、`analysis_schema_version`、`output_digest`。明确 `parser_build_identity = sha256(gd_parse.py bytes)[:16]`，由 Adapter 运行时计算写入。

### G2 — Backward Compatibility
历史记录一律写 `parser_build_identity: "NOT_AVAILABLE"`、`parser_output_contract: "NOT_RECORDED"`，**禁止回填猜测值**；读取方必须区分“缺失”与“已知”。保留 1.71 的 ID 语义，不做原地改写。

### G3 — Non-destructive Identity Introduction
新增字段只增不改；`write_record` 增加存在性守卫与 `output_digest` 比对：同 ID 同摘要 → 视为重复执行（跳过）；同 ID 不同摘要 → 拒绝覆盖并写入冲突报告。所有写入走临时文件 + 原子替换。

### G4 — Controlled Reanalysis Pilot（设计）
- 样本：3 条（`board_member_button.gd`、`board_card.gd`、`blackboard_compare.gd`——即 Batch D/E 已人工复核者）。
- 旧结果：复制到 `reanalysis/<contract>/original/`，计算 digest。
- 新结果：写入 `reanalysis/<contract>/reanalyzed/`，绝不写正式目录。
- 比较：复用 `canonical()` + `content_digest()` + 符号级 diff。
- 幂等：每条分析两次内存比对 + 整体二次运行。
- 停止/回滚：任何 digest 不一致或身份不可复算即停止；回滚仅需删除 workspace 子目录。
- 防提前消费：正式 `analysis/`、`feature_links/`、`candidate_workspace/` 保持只读，并在 Pilot 结束前不重建 `index.json`。

### G5 — Controlled Formal Reanalysis（设计）
预检（身份可复算、输入摘要一致、workspace 存在）→ 授权（人工书面授权）→ 输入快照（复制 Reference + pinned source + 旧记录 digest）→ 输出到隔离目录 → 新旧通过 `reanalysis_of` 关联 → Symbol Diff → Linkage 影响评估 → Candidate/Seed 影响评估 → Integrity Validation → 人工验收 → **单独授权**才写正式目录。

### G6 — Downstream Adoption
只有在新 Analysis 通过验收、且 Linkage/Candidate 明确声明所消费的 `parser_build_identity` 之后，才允许下游消费。**Reanalysis 完成 ≠ Evidence Integration 授权**；Seed 政策需单独更新并重新评审。

---

## O. Risk Register

| Risk ID | Risk | Impact | Likelihood | Evidence | Mitigation | Blocking? |
|---|---|---|---|---|---|---|
| R-01 | 历史 Build Identity 缺失 | 无法证明旧分析由何实现产生 | 确定（已发生） | 34/34 记录无该字段 | 标记 `NOT_AVAILABLE`，不回填 | 否（但限制“可复现”声明） |
| R-02 | Analysis ID 与 Parser Version 耦合 | 版本一变 34 条 ID 与 150 条 Linkage 全漂移 | 确定（实测） | 1.71 复算 34/34，1.75 复算 0/34 | 分层身份，ID 改用内容身份 | **是**（解锁前必须解决） |
| R-03 | 不同 Build 输出混用 | 同 ID 不同内容被当成同一结论 | 高 | `write_record` 无守卫 | 记录级身份 + `output_digest` | **是** |
| R-04 | Adapter 变化但 Parser Identity 不变 | 坐标/序列化变化不可追溯 | 已发生（Batch E） | 当前 build 含 adapter，但记录不含 | 独立 `adapter_build_identity` | 是 |
| R-05 | Coverage Contract 变化无法追溯 | 构造码/派生规则变化无痕迹 | 已发生（Batch E） | 记录无 `parser_output_contract` | 显式契约版本 | 否 |
| R-06 | Source / Reference 坐标映射不完整 | 伪 commit 行号 | 中 | Batch E 前硬编码 `[3:]` | 已修；需长期断言 `mapping_status` | 否 |
| R-07 | 历史 Analysis 无法重建 | 1.71 输出不可复现 | 确定 | 无旧 Build 记录 | 保留旧记录只读，禁止声称可重建 | 否 |
| R-08 | 新旧 Analysis 覆盖 | 历史被静默替换 | 中 | `write_text` 直接覆盖 | 存在性守卫 + 原子写 + `supersedes` | **是** |
| R-09 | Linkage 引用失效 | 150 条关联断裂 | 中（版本 bump 时确定） | `linkage_id=f(analysis_id)` | 迁移映射表 / 内容身份 ID | 是（若 bump 版本） |
| R-10 | Seed 消费未验证的新结果 | Seed 基于旧/新混合证据 | 中 | Seed 策略无 parser 门禁 | 显式门禁 + 重新评审 | 是（涉及 Seed 时） |
| R-11 | Reanalysis 非确定性 | 同身份不同输出 | 低 | Batch B 已做双跑比对 | `output_digest` + 确定性断言 | 否 |
| R-12 | 历史 Provenance 不完整 | 无法确认来源 | 低 | `provenance_status=complete` 34/34，字段齐 | 保持现状，补 Build 维度 | 否 |
| R-13 | 4 条分析无 Linkage | 证据链缺口 | 确定 | 实测 4 条 `linkage_count=0` | 后续阶段单独处理 | 否（本阶段） |
| R-14 | 硬编码 `EXPECTED_IDENTITY` 阻碍合法重跑 | 正常升级被误判为异常 | 中 | `reanalysis_176.py:51` | 改为读取身份清单而非单值 | 否 |

---

## P. Open Questions

1. `parser_output_contract` 是否用语义化标签（`1.75.0`）还是契约清单摘要？前者人读友好，后者可验证。
2. Analysis ID 改为内容身份后，150 条既有 Linkage 需要一张旧→新映射表；是否允许一次性迁移，还是双 ID 并存一个阶段？
3. `source_digest` 是否应进入内容身份？（当前不进入，意味着 pinned source 变化不会改变 ID——建议进入。）
4. `reanalysis_of` 与 `previous_analysis_id` 是否二者取一，还是分别表达“来源记录”与“被取代记录”？
5. Seed 政策是否需要把 `parser_build_identity` 纳入门禁字段，还是保持“人工评审”？
6. 历史 4 条无 Linkage 分析是否在重跑后重新建立 Linkage？
7. `output_digest` 是否排除 `unresolved_questions` 等易变文本？

---

## Q. Final Architecture Recommendation

1. **推荐架构：C（分层身份），以 B 作为过渡落地形态。** —— `DESIGN_RECOMMENDATION`
2. **身份字段与职责：** `parser_version`（标签）、`parser_build_identity`（实现指纹）、`parser_output_contract`（输出契约）、`adapter_version` + `adapter_build_identity`、`analysis_schema_version`、`output_digest`。 —— `DESIGN_RECOMMENDATION`
3. **Analysis ID 是否保持稳定：** 长期应**与 Parser 实现解耦**（改为内容身份），过渡期保持现状并记录双键。 —— `EVIDENCE_CONFIRMED`（耦合已实测）+ `DESIGN_RECOMMENDATION`（解耦方案）
4. **Build Identity 生成原则：** 由运行时计算 `sha256(源码字节)[:16]`，写入记录，可复算；禁止人工填写。 —— `DESIGN_RECOMMENDATION`
5. **Adapter Identity：** 必须独立于 Parser（Batch E 证明会独立变化）。 —— `EVIDENCE_CONFIRMED`
6. **Analysis Schema：** 新增字段只增不改；`schema_version` 仅在结构不兼容时递增。 —— `DESIGN_RECOMMENDATION`
7. **Reanalysis Trigger：** 采用 H 节 12 类与 I 节矩阵，区分 `REUSE / REVALIDATE / RECORD_MIGRATION / REANALYZE / MANUAL_REVIEW / NOT_APPLICABLE`。 —— `DESIGN_RECOMMENDATION`
8. **历史兼容：** 旧记录标记 `NOT_AVAILABLE`，不回填、不改写、不删除。 —— `DESIGN_RECOMMENDATION`
9. **34 条正式 Analysis：** 全部 `REANALYZE`（1 条 shader 为 `NOT_APPLICABLE`），但必须另行授权；当前继续作为只读证据使用。 —— `EVIDENCE_CONFIRMED`
10. **Pilot 条件：** 先完成 G1–G3（契约 + 守卫 + 非破坏写入），再以 3 条样本做隔离 Pilot。 —— `DESIGN_RECOMMENDATION`
11. **下游门禁：** Linkage/Candidate/Seed 必须声明所消费的 Build；Seed 需单独重新评审。 —— `DESIGN_RECOMMENDATION`
12. **后续 Phase 顺序建议：** ①身份契约设计定稿 → ②写入守卫与 `output_digest` → ③3 条样本 Pilot → ④34 条正式重跑（单独授权）→ ⑤Linkage/Candidate 迁移 → ⑥Seed 政策重评 → ⑦Semantic Linkage Tier。 —— `DESIGN_RECOMMENDATION`

---

## R. Phase Readiness

| 判定 | 值 |
|---|---|
| Verdict | **`PASS_WITH_LIMITATIONS`** |
| Readiness | **`READY_FOR_IDENTITY_IMPLEMENTATION_DESIGN`** |

限制（均为设计条件而非执行缺陷）：
- 本阶段未实现任何字段、未修改任何工具（`NOT_VERIFIED`：字段落地后的行为）。
- 1.71 的 Build Identity 不可重建，只能标记缺失。
- 尚未验证“记录级双键”对 150 条 Linkage 的实际迁移成本（`NOT_VERIFIED`）。

### 任务书要求明确回答的 7 个问题

1. **当前 Parser Identity 是否足以安全支持未来 Reanalysis？**
   **不足以。** 同版本内实现变化不可观测（Batch E 已真实发生），Analysis ID 不含 Build，正式记录不含 Build，且写入无覆盖守卫。 —— `EVIDENCE_CONFIRMED`
2. **是否推荐引入独立 Parser Build Identity？**
   **是。** 必须由运行时从源码字节计算并写入每条记录。 —— `DESIGN_RECOMMENDATION`
3. **Analysis ID 是否应与 Parser Build Identity 解耦？**
   **是。** 建议 ID 改为内容身份（repo/commit/path/input_digest/source_digest），实现差异由记录级身份表达。 —— `EVIDENCE_CONFIRMED`（耦合）+ `DESIGN_RECOMMENDATION`（解耦）
4. **34 条正式 Analysis 是否需要未来重跑？**
   **需要。** 全部为 1.71 无 coverage 记录；1 条 shader 为 `NOT_APPLICABLE`。重跑必须另行授权。 —— `EVIDENCE_CONFIRMED`
5. **是否可以安全开展 Limited Pilot？**
   **当前不可以直接开展**；完成“身份契约 + 写入守卫 + 非破坏记录模型”后可以。设计条件已具备，执行授权尚未获得。 —— `DESIGN_RECOMMENDATION`
6. **哪些问题必须先解决？**
   R-02（ID 与版本耦合）、R-03（同 ID 覆盖）、R-08（静默覆盖）、R-04（Adapter 身份）。 —— `EVIDENCE_CONFIRMED`
7. **下一阶段最合理的任务是什么？**
   身份契约实现设计（只设计字段与守卫，不重跑、不写正式数据）。 —— `DESIGN_RECOMMENDATION`

---

## S. Validation & Integrity Evidence

| 检查 | 方式 | 结果 |
|---|---|---|
| Git 基线 | `git rev-parse` / `git status --porcelain` | `master @ d64b1cd5…`，staged 0，deleted 0 |
| Analysis ID 可复算性 | 内存复算 `sha256(repo|commit|path|input_digest|gd_parse|version)` | 1.71: 34/34；1.75: 0/34 |
| `input_digest` 一致性 | 重算 Reference 字节摘要 | 34/34 一致 |
| Batch B 映射 | 用 1.75 复算 `reanalysis_id` | 33/34（例外为 shader，`reanalysis_id=null`） |
| Linkage 身份 | 复算 `linkage_id` | 150/150 |
| 索引一致性 | 比对 `index.json` 与正式记录集合 | 34/34 一致 |
| Build Identity | `corpus_audit_176.parser_build_identity()` | 当前 `3b36069a44beb55c` ≠ Batch B `6b74a6cd20a06033` |
| 受保护数据 | 8 个清单 SHA-256 | 与 Batch E **8/8 IDENTICAL** |
| 阶段内写入 | mtime 界值扫描 | 受保护目录被写入文件数 **0** |
| 测试 | 本阶段未运行（无需修改任何代码；Batch E 的 4 套件结果仍然有效） | 未重跑 |

---

## T. Git State

```
Branch  master
HEAD    d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Staged  0
Deleted 0
Modified 31（既有未提交修改，本阶段未新增）
Untracked 145 行 / 593 文件（既有），新增：.ai/context/PHASE_1_77_PARSER_IDENTITY_REANALYSIS_ARCHITECTURE_REVIEW.md
```

本阶段未执行任何 Git 写操作；`HEAD` 与 Batch E 完成时一致。

临时探测文件（本阶段创建，位于 gitignored 的 `.ai/tmp/`）：
`phase177_probe.py`、`phase177_id_experiment.py`、`phase177_probe3.py`、`phase177_integrity.py`、`phase177_probe_out.json` —— 已在阶段结束时删除。Batch E 遗留的 `batch_e_*.py` 属于上一阶段产物，本阶段未修改、未删除，保留并在此报告。

---

## 验收对照

| AC | 结果 | 证据位置 |
|---|---|---|
| AC-01 基线准确 | 通过 | B、T 节 |
| AC-02 身份来源可追溯 | 通过 | C、D 节（含行号） |
| AC-03 Build Identity 设计（≥2 方案） | 通过 | F、G 节（A/B/C 三方案） |
| AC-04 34 条逐条核对 | 通过 | L.1 表（未知标 NOT_AVAILABLE / NOT_RECORDED） |
| AC-05 Reanalysis 决策模型 | 通过 | H、I 节 |
| AC-06 非破坏历史 | 通过（设计） | J 节 |
| AC-07 下游影响 | 通过 | M 节（含依赖图） |
| AC-08 迁移策略（含 Pilot/回滚） | 通过 | N 节 |
| AC-09 风险透明 | 通过 | O、P 节 |
| AC-10 只读完整性 | 通过 | B.2（8/8 IDENTICAL，0 写入） |
| AC-11 无提前实施 | 通过 | 未修改任何工具/数据 |
| AC-12 证据可复现 | 通过 | Q 节每条标注 EVIDENCE_CONFIRMED / DESIGN_RECOMMENDATION |

**阶段结束，等待人工验收。未进入 Identity Implementation、未进入 Pilot、未改动 Seed Policy、未重跑正式 Analysis、未创建下一阶段任务、未执行 Git 写。**
