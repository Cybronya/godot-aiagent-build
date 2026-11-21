# Phase 1.72 — Feature Similarity & Candidate Synthesis Architecture Audit

状态：**PASS_WITH_LIMITATIONS**

阶段类型：只读架构审计（Read-only Architecture Audit）

审计范围：Feature Registry、External Code Understanding、Promote、Feature Admission、Similarity、Capability Extraction、Candidate Workspace、Validation Infrastructure。

本阶段**没有修改任何既有项目文件**，没有创建 Feature/Candidate/Knowledge，没有执行 Fetch、Promote、Reindex、Catalog rebuild、Backfill、Knowledge Approval，也没有执行 Git 写操作。唯一新增文件是本报告。

---

## 1. Executive Summary

### 1.1 总体结论

当前系统已经具备以下真实能力：

- 外部代码采集、Reference Library、Catalog 与内容级去重；
- 14 条 External Analysis Record，以及可查询的 Analysis Index；
- 31 个正式 Feature 的 YAML metadata、Feature Index 与 Feature Graph；
- 23 个 Feature、60 个 Behavior 的静态 Source Analysis；
- 23 个 Feature / 60 个 Behavior 的 Behavior Contract，以及部分 L4 行为证据；
- 31 个 Feature 自测文件，以及统一的 Python/Godot 测试入口；
- 多种可复用的 Candidate/Review 模式，分别用于 Knowledge、Binding、Trace Baseline 和 Asset Review。

但当前系统**不具备**以下能力：

- Feature Similarity Engine；
- Feature Fingerprint / Symbol Fingerprint；
- 从代码提取语义 Capability 的 Capability Extractor；
- Feature Candidate Workspace；
- Feature Review / Admission Gate；
- External Analysis → Feature Registry 的正式关联键；
- 将 Feature Index 作为“已实现、已验证、已准入”事实源的机制。

### 1.2 当前系统最重要的架构缺口

1. **Feature Index 是 Lossy Projection。**
   `feature_index.json` 只保留 `id/version/category/provides/requires/interfaces/signals/validation/relations` 九个字段。`summary`、`capabilities`、`ownership`、`composition`、行为契约、源码引用、验证状态、provenance 都不在索引中。

2. **External Analysis 与 Feature Registry 没有连接键。**
   External Analysis Record 有 `snippet_id`，但没有 `feature_id`；Feature metadata 也没有结构化 `analysis_id`。Promote 从 Catalog snippet 读取，而不是从 Analysis Record 读取。

3. **Promote 不是 Candidate Synthesis，也不是 Admission。**
   它复制原始片段、生成带 `TODO` 的 scaffold、写入恒定 FAIL 的占位测试，然后刷新 Feature Index。没有测试执行、没有人工审批、没有准入状态。

4. **Similarity 证据链不完整。**
   现有搜索是词法/标签匹配；`provides` 标签是人工声明；`discover_feature` 甚至不读取 `summary`。没有可支撑 DUPLICATE / SIMILAR / CONFLICTING 自动判断的结构化证据。

5. **Capability 被两种不同含义混用。**
   `feature.yaml#provides` 是人类声明的功能标签；`feature.yaml#capabilities.required` 是 Scene 能力（实际只有 `Node` 和 `Collision`）。两者都不是从代码中提取并验证的语义 Capability。

6. **没有 Feature Candidate 隔离区。**
   现有 Candidate 机制只服务于 Knowledge、Binding、Trace Baseline 和 Asset Review；Feature 没有候选身份、审查状态、验证结果或准入决定。

### 1.3 下一阶段建议

不建议立即实现完整 Similarity Engine，也不建议先建大型 Candidate 子系统。

建议采用 **Hybrid Incremental Architecture**：

1. 先补齐 Feature Registry / Index 的**证据投影**与 External Analysis 关联；
2. 再建立只输出证据、不自动下结论的 **Similarity Evidence Report**；
3. 再做小范围、可人工确认的 **Capability Extraction**；
4. 最后接入 **Candidate Workspace + Feature Admission Gate**。

推荐下一阶段名称：**Phase 1.73 — Feature Similarity Evidence Foundation**。

---

## 2. Preflight & Read-only Integrity

### 2.1 Git 基线

审计开始时记录：

```text
Project Root:       F:/Godot_v4.7-stable/game
Current Branch:     master
HEAD:               d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Working Tree:       135 条 porcelain 记录
Staged Files:       0
Modified Files:     29
Untracked Files:    161
```

报告创建前复核，结果相同：`staged=0`、`modified=29`、`untracked=161`、HEAD 未变。

### 2.2 Phase 1.71 成果确认

| 项目 | 实际文件 / 数据 | 状态 |
|---|---|---|
| Batch A Provenance | `.ai/tools/external_code/provenance.py`、`provenance_validator.py`、`.ai/tools/external_code/tests/test_batch_a.py` | CONFIRMED |
| Batch B Adapter | `.ai/tools/external_code/external_code_understanding.py` | CONFIRMED |
| External Analysis Records | `.ai/learning/external_code/analysis/*.json`，14 条 | CONFIRMED |
| Analysis Index | `.ai/learning/external_code/index.json`，14 条 `analyses` | CONFIRMED |
| Search Integration | `.ai/tools/feature_registry/search_assets.py` 的 `--analysis`、`--symbols`、`--analysis-status` | CONFIRMED |
| Shared Parser / Analysis | `.ai/tools/learning/gd_parse.py`、`.ai/tools/learning/source_analysis.py`，含 `analyze_external_scripts()` | CONFIRMED |
| Batch B Tests | `.ai/tools/external_code/tests/test_batch_b.py` | CONFIRMED（文件存在，本阶段未运行） |

报告与实际源码的差异：

- Phase 1.71 报告中的部分统计是历史口径；本报告一律以当前实际数据为准。
- 当前 External Analysis Record 实际有 **45 个字段**，不是只包含报告摘要列出的字段。
- 当前 Feature 行为覆盖以 `.ai/context/coverage_matrix.json` 为准（23 Feature / 60 Behavior），不使用旧版 `FEATURE_BEHAVIOR_COVERAGE.md` 的 12 Feature 口径。

### 2.3 只读执行证明

本阶段执行的操作：

- `git status --short`、`git diff`、`git rev-parse` 等只读 Git 命令；
- 只读读取 Python / JSON / YAML / Markdown；
- 只读导入并调用 `build_feature_index.build_index()` / `build_graph()` 做一致性核对，没有调用 `write_index()` 或 CLI 写入入口；
- 执行 `.ai/tools/validator/check_feature_metadata.py`（只读 metadata/index 校验），结果为 `Checked feature metadata: 31`、`PASS: 0 error(s), 0 warning(s)`。

本阶段**没有执行**：

- `test_batch_a.py` / `test_batch_b.py`；
- `run_tests.py`、Godot headless、Feature tests、E2E；
- Promote / Fetch / Reindex / Backfill / Catalog rebuild；
- 任何 Knowledge Approval、Candidate 创建、Feature 创建、Scene Intent 修改。

因此，本报告的验证状态是：

```text
Static source/data audit:        COMPLETED
Feature metadata/index check:    PASS (read-only command)
Dynamic test execution:          NOT_RUN
Godot runtime validation:        NOT_RUN
Promote / Admission execution:   NOT_RUN
```

### 2.4 Preflight 结论

```text
Phase 1.72 Preflight Status:          PASS
Read-only Constraints:                CONFIRMED
Phase 1.71 Implementation:            CONFIRMED
Git Baseline:                         RECORDED
```

---

## 3. Existing Architecture Inventory

### 3.1 实际存在的模块

| Area | Module / Path | 实际职责 | 状态 |
|---|---|---|---|
| 外部采集 | `.ai/skills/foundation/godot-gdscript/tools/github_collector.py` | GitHub search/fetch/catalog/check/promote | EXISTING |
| Source / Reference Library | `.ai/skills/foundation/godot-gdscript/code_library/sources/`、`references/` | 保存仓库源码与片段引用 | EXISTING |
| Catalog | `code_library/catalog.yaml`、`INDEX.md`、`candidates.json` | 7,270 条 Catalog entries；6,813 条 unique fragments；100 个 repo candidates | EXISTING |
| External Analysis | `.ai/tools/external_code/external_code_understanding.py` | 生成 Analysis Record；复用 `gd_parse` / `source_analysis` | EXISTING |
| Analysis Records | `.ai/learning/external_code/analysis/*.json` | 14 条记录 | EXISTING |
| Analysis Index | `.ai/learning/external_code/index.json` | 14 条索引 | EXISTING |
| Analysis Search | `search_assets.py` | Catalog snippet + Analysis 查询 | EXISTING |
| Feature metadata | `Features/*/feature.yaml` | 31 个 Feature 的声明式契约 | EXISTING |
| Feature Index | `.ai/tools/feature_registry/build_feature_index.py` | 生成 `feature_index.json` / `feature_graph.json` | EXISTING |
| Feature Graph | `.ai/context/feature_graph.json` | 31 nodes / 80 edges | EXISTING |
| Feature Source Analysis | `.ai/learning/source_analysis/<feature>/<behavior>.json` | 23 Feature / 60 Behavior 的静态源码证据 | EXISTING |
| Behavior Contract | `Features/*/template.yaml#behavior` | 23 个 Feature、60 个 Behavior | EXISTING |
| Feature Discovery | `discover_feature.py`、`feature_discovery.py` | 标签/接口/类别匹配 | EXISTING |
| Feature Composition | `compose_features.py`、`dependency_resolver.py` | requires / provides / relations 组合 | EXISTING |
| Scene Intent / Composer | `.ai/tools/scene_composer/*` | Scene Intent、Capability Gate、Scene 生成与验证 | EXISTING |
| Feature Metadata Validator | `.ai/tools/validator/check_feature_metadata.py` | metadata / test path / index 同步检查 | EXISTING |
| Unified Validator | `.ai/tools/validator/validate.py` | Framework / Feature / Asset / Binding / Instance 检查 | EXISTING |
| Behavior Evidence | `feature_behavior_evidence.py` | 真实 Godot 行为证据（L4） | EXISTING |
| Behavior Evidence Validator | `check_behavior_evidence.py` | 独立交叉验证已保存证据 | EXISTING |
| Test Runner | `.ai/tools/run_tests.py` | 发现 Feature tests + Python tests；PASS/FAIL/INCOMPLETE | EXISTING |
| E2E | `.ai/tools/e2e/*` | 多 Feature / Level / Trace 端到端 | EXISTING |
| Knowledge Store | `.ai/tools/learning/knowledge_v2.py` | Behavior Knowledge 的 PENDING_REVIEW → APPROVED 生命周期 | EXISTING |
| Binding Candidates | `.ai/tools/validator/binding_candidates.py` | DRAFT → PENDING_REVIEW → APPROVED → promote | EXISTING |
| Trace Candidates | `.ai/tools/e2e/approve_trace_baselines.py` | candidate → review → apply | EXISTING |
| Asset Reviews | `.ai/context/asset_reviews/*.review.json` | 资源审查记录 | EXISTING |
| Feature Candidate Workspace | — | 无 | **MISSING** |
| Feature Similarity Engine | — | 无 | **MISSING** |
| Capability Extractor | — | 无语义 Capability 提取 | **MISSING** |
| Feature Admission Gate | — | 无 `ADMITTED` 状态、无 Feature review | **MISSING** |

### 3.2 数据规模

| 数据 | 实际数量 |
|---|---:|
| Catalog entries | 7,270 |
| Unique Catalog fragments | 6,813 |
| Repo candidates | 100 |
| External Analysis Records | 14 |
| External Analysis: `analysis_complete` | 5 |
| External Analysis: `analysis_partial` | 8 |
| External Analysis: `unsupported_shader` | 1 |
| Feature directories | 31 |
| Feature YAML metadata | 31 |
| Feature Index entries | 31 |
| Feature Graph nodes / edges | 31 / 80 |
| Feature isolated graph nodes | 6 |
| Feature self-test files | 31 |
| Feature templates with `behavior:` | 23 |
| Supported behaviors | 60 |
| Feature source-analysis records | 60 |
| Source-analysis status: COMPLETE / PARTIAL / SOURCE_ENTRY_AMBIGUOUS | 5 / 50 / 5 |
| Behavior coverage: evidence verified | 8 / 60 |
| Behavior coverage: fully covered | 0 / 60 |
| Knowledge records | 102（APPROVED 59，PENDING_REVIEW 28） |
| Binding candidates | 1（APPROVED） |
| Approval registry records | 62（APPROVED 61，SUPERSEDED 1） |
| Trace candidates | 2 |
| Asset reviews | 19 |

---

## 4. Feature Registry Audit

### 4.1 Registry Schema 与实际字段

`feature.yaml` 是 Feature 的声明式 metadata；`feature_index.json` 是供 Discovery / Search / Scene Composer 消费的投影。

Feature Index 顶层：

```json
{
  "registry_version": "...",
  "generated_at": "...",
  "features": [...]
}
```

单个 Index record 实际只有：

```text
id
version
category
provides
requires
interfaces
signals
validation
relations
```

`build_index()` 的投影位置：`.ai/tools/feature_registry/build_feature_index.py:97` 与 `:120-133`。

### 4.2 字段可靠性

| Field | Exists | Source File | Meaning | Reliability |
|---|---|---|---|---|
| `id` | YES | `feature.yaml`；index | Feature 唯一 ID | HIGH |
| `version` | YES | `feature.yaml`；index | 声明版本字符串 | HIGH |
| `category` | YES | `feature.yaml`；index | 粗粒度类别 | MEDIUM |
| `summary` | YAML YES / Index NO | `feature.yaml` | 人类可读职责描述；31/31 存在 | MEDIUM |
| `provides` | YES | YAML；index | 人工声明的能力标签 | MEDIUM |
| `requires` | YES | YAML；index | 人工声明的依赖/能力需求 | MEDIUM |
| `interfaces` | YAML YES / Index PARTIAL | YAML；index | YAML 中 87 methods / 29 signals / 83 exports；index 只保留扁平名称列表，丢失 signature、description、type、default | MEDIUM |
| `signals` | YES | YAML；index | 扁平信号名列表 | MEDIUM |
| `validation.test_path` | YES | YAML；index | 自测文件路径 | MEDIUM |
| `validation.command` | YAML YES / Index NO | `feature.yaml` | 建议运行命令 | MEDIUM |
| `relations` | YES | YAML；index | 人工 `works_with` / `commonly_used_with` / `conflicts` / `entity_roles` / `requires` | MEDIUM |
| `capabilities` | YAML YES / Index NO | `feature.yaml` | 31/31 有 `capabilities.required`；实际词汇只有 `Node`（23 次）与 `Collision`（8 次） | LOW（作为语义 Capability） |
| `ownership` | YAML YES / Index NO | `feature.yaml` | 状态与职责边界的人类说明 | MEDIUM |
| `composition` | YAML YES / Index NO | `feature.yaml` | entry scene / usage / related features | MEDIUM |
| Script paths | **NO** | — | Registry 不记录实现脚本列表；仅 `.ai/learning/source_analysis` 的 `scripts` 有 23 Feature 的实现引用 | LOW（Registry 视角） |
| Scene / Resource paths | PARTIAL | `feature.yaml#composition.entry_scene`；23 个 `template.yaml` | 不是统一索引字段 | MEDIUM |
| Feature tests | PARTIAL | `Features/*/test_*.gd`，31 个 | 文件存在；Registry 不记录执行结果 | MEDIUM |
| Test status | **NO** | — | 没有 `PASS/FAIL/INCOMPLETE` 字段 | NONE |
| Feature status | **NO** | — | 没有 `status` / `ADMITTED` / review 状态 | NONE |
| Provenance | PARTIAL / LOW | 11 个 `feature.yaml` 注释含来源片段/source URL | 无结构化 provenance 字段 | LOW |
| Static source analysis | SEPARATE | `.ai/learning/source_analysis/<feature>/<behavior>.json` | 60 条静态行为证据，不属于 Registry | MEDIUM |
| Behavior contract | SEPARATE | `Features/*/template.yaml#behavior` | 23 Feature / 60 Behavior | MEDIUM |
| Behavior evidence | SEPARATE | `.ai/context/coverage_matrix.json` | 60 行为中 8 个有 L4 evidence，0 个 fully covered | LOW / PARTIAL |

### 4.3 Feature 的真实描述能力

| 问题 | 当前答案 | 证据性质 | 结论 |
|---|---|---|---|
| 实际实现什么功能？ | YAML `summary` 31/31；README 31/31；Index 不包含 summary | 人工声明 | PARTIALLY_IMPLEMENTED |
| 对外暴露哪些接口？ | YAML 87 methods、29 signals、83 exports；Index 只保留名称 | 人工声明，未经源码静态核验 | PARTIALLY_IMPLEMENTED |
| 需要什么输入？ | 方法参数、exports、ownership 分散声明 | 人工声明 | PARTIALLY_IMPLEMENTED |
| 产生什么输出？ | methods/signals/exports 声明 | 人工声明 | PARTIALLY_IMPLEMENTED |
| 依赖哪些 Feature？ | `requires`、`relations`；`feature_graph` 80 条边 | 人工声明 + 索引生成 | PARTIALLY_IMPLEMENTED |
| 具备什么 Capability？ | `provides` 标签 + `capabilities.required` Scene 能力 | 人工声明 | PARTIALLY_IMPLEMENTED |
| 适用哪些场景？ | `entity_roles`、`composition`、README | 人工声明 | PARTIALLY_IMPLEMENTED |
| 有哪些限制？ | `ownership.rules`、README、少量 unresolved | 人工文本 | PARTIALLY_IMPLEMENTED |
| 已知缺陷？ | 没有 Feature 级 defect/status 字段；coverage/mutation 结果未回写 Feature | 无结构化记录 | NOT_IMPLEMENTED |

必须区分四类信息：

- **Metadata 声明**：summary、provides、requires、interfaces、signals、capabilities、ownership、composition、relations。
- **源码静态分析**：`.ai/learning/source_analysis` 的 60 条 behavior-level records（入口、状态变量、条件、事件、失败路径、脚本 digest）。
- **测试验证**：31 个 Feature 测试文件；本阶段未执行；Registry 不保存结果。
- **名称/描述推测**：`discover_feature` 的同义词匹配、`provides` 标签匹配、`feature_discovery` 的 role/tag 匹配。它们不是已验证能力。

### 4.4 Registry 查询能力

| 查询方式 | 现有工具 | 实际支持 | 限制 |
|---|---|---|---|
| 按名称 | `search_assets.py`、`discover_feature.py` | YES | 名称/ID 词法匹配 |
| 按分类 | 两者 | YES | category 只作为低权重词 |
| 按 Capability | `provides` / `feature_discovery` | PARTIAL | 只有人工标签；不查询 `capabilities.required` |
| 按依赖 | `compose_features.py`、`dependency_resolver.py` | PARTIAL | 依赖是声明式；无运行时验证 |
| 按接口 | `search_assets.py`、`discover_feature.py` | PARTIAL | 只按名称；Index 无签名 |
| 按脚本符号 | — | **NO** | Feature Registry 没有符号索引 |
| 按功能描述 | — | **NO** | `summary` 不在 Index；`discover_feature.py "temporary invulnerability window"` 返回 no matches（实测） |
| 按行为 | `template.yaml` / source_analysis | PARTIAL | 不在统一 Search；没有行为查询入口 |
| 按验证状态 | — | **NO** | 没有 status 字段 |

### 4.5 Feature Registry 结论

- Registry **可以**作为相似性分析的**候选数据源**，但不能单独作为判定源。
- 缺少的关键字段：结构化 summary、scripts、symbols、API signatures、semantic capability tags、behavior IDs、validation status、provenance、admission status。
- 存在损失：Index 丢掉 summary、capabilities、ownership、composition、签名细节、行为与源码引用。
- 存在可移植性问题：31/31 个 `validation.test_path` 是绝对 Windows 路径（例如 `F:/Godot_v4.7-stable/game/Features/health/test_health.gd`），不利于跨工作区 Candidate 验证。
- 不需要新建 Feature Registry；应扩展现有 `feature.yaml` + Index projection。

---

## 5. External Analysis Audit

### 5.1 Analysis Record Schema

实际位置：

```text
.ai/tools/external_code/external_code_understanding.py
.ai/learning/external_code/analysis/*.json
.ai/learning/external_code/index.json
```

实际记录包含 **45 个字段**。按职责分组：

| Group | Fields | 来源 / 提取方式 | 可靠性 | 可追溯性 | 验证状态 |
|---|---|---|---|---|---|
| Identity | `analysis_id`、`snippet_id`、`repo`、`source_path`、`reference_path`、`domain` | Catalog metadata + input digest + parser version | HIGH | 可回溯到 snippet/reference | 静态生成 |
| Version | `commit_sha`、`commit_sha_full`、`source_url`、`input_digest`、`source_digest`、`parser_name`、`parser_version`、`created_at` | Catalog / SHA-256 | HIGH | 可回溯到源码版本与字节 | 静态生成 |
| Provenance | `provenance_status`、`provenance`、`license`、`license_status`、`license_text_present`、`license_source`、`license_basis`、`license_risk`、`copy_allowed`、`source_exists`、`source_file_path` | `provenance.py` / `assess_license` / `assess_provenance` | HIGH | 有来源、许可证、复制裁决 | 14/14 provenance complete |
| Parse state | `file_type`、`parse_status`、`analysis_status`、`source_analysis_status` | Parser / adapter 状态机 | HIGH（作为状态，不是能力证明） | 可回溯 | 14 条 |
| Symbols | `symbols.class_name`、`extends`、`functions`、`signals`、`exports`、`variables`、`constants`、`calls`、`connections` | `gd_parse.parse_text()` + `_symbols()` | MEDIUM | 有文件/行号 | 静态提取 |
| Evidence | `entry_points`、`functions_analyzed`、`state_changes`、`conditions`、`signals_events`、`side_effects`、`failure_paths` | `source_analysis.analyze_external_scripts()` | MEDIUM / PARTIAL | 有 source_reference / line | 静态、启发式 |
| Gaps | `limitations`、`unresolved_questions` | `_syntax_limitations()` + analysis | MEDIUM | 有文本原因 | 14 条中 6 条有 unresolved |
| Lifecycle | `knowledge_status`、`approved_knowledge`、`feature_created` | 固定初值 / 下游未回写 | HIGH | — | 14/14 `NOT_KNOWLEDGE`，14/14 `feature_created=false` |

当前数据：

```text
records: 14
file_type: gdscript 13, gdshader 1
parse_status: parsed 10, partial 3, unsupported_shader 1
analysis_status: analysis_complete 5, analysis_partial 8, unsupported_shader 1
provenance_status: complete 14
license_status: eligible 13, license_text_missing 1
copy_allowed: true 14
source_exists: true 14
unresolved_questions non-empty: 6
```

### 5.2 Parser 能力边界

`gd_parse.py` 是正则解析器，不是 AST Parser。关键正则位于 `.ai/tools/learning/gd_parse.py:19-48`，解析入口为 `parse_text()`（`:115`）。

| 信息 | 分类 | 说明 |
|---|---|---|
| `class_name` | **EXTRACTED** | 顶层 `class_name` 正则 |
| `extends` | **EXTRACTED** | 只记录直接 base 文本；不解析继承链 |
| 函数名 / 参数 / 返回文本 / 行号 | **EXTRACTED** | `FUNC_RE`；参数是原始文本，无类型归一化 |
| 信号 / 参数 | **EXTRACTED** | `SIGNAL_RE` |
| `@export` / `@onready` / `var` / `const` | **EXTRACTED** | 只覆盖已识别形式 |
| 调用 / 连接 / emit | **EXTRACTED** | 正则收集；不保证动态调用可解析 |
| 文件 / 资源 / 节点访问 | **EXTRACTED** | `FileAccess`、`load/preload`、`get_node` |
| 守卫 / return | **EXTRACTED** | 行级正则 |
| 状态变量、条件、事件、副作用、失败路径 | **INFERRED** | 由 `source_analysis._extract_evidence()` 启发式汇总 |
| 入口选择 | **INFERRED** | 生命周期函数 / 公开函数 / 回退全部函数 |
| `analysis_status` / `analysis_partial` | **INFERRED** | 依赖 unresolved / limitations |
| AST、类型推导、完整注解语义 | **UNSUPPORTED** | `_syntax_limitations()` 明确 `regex_parser_without_ast_or_type_inference` |
| Inner class | **UNSUPPORTED** | 只记录 limitation，不解析内部类语义 |
| Lambda 语义 | **UNSUPPORTED** | 只记录 limitation |
| 非 `@export` / `@onready` 注解 | **UNSUPPORTED** | 记录 `annotation_not_fully_interpreted` |
| 多行复杂表达式 | **UNSUPPORTED** | 正则行级解析 |
| `.gdshader` | **UNSUPPORTED** | 固定 `unsupported_shader` |
| 动态调用目标 | **UNKNOWN** | 写入 unresolved |
| 跨文件依赖 / 继承链 / 类型系统 | **UNKNOWN / NOT_IMPLEMENTED** | 单文件分析；没有 dependency graph |
| 运行时行为 | **UNKNOWN** | 没有运行即不能声称行为 |
| 语义 Capability | **UNKNOWN** | 没有 Capability 字段或提取器 |

关键限制：`analyze_external_code()` 当前只把**单个** `Script` 传给 `source_analysis.analyze_external_scripts([script])`。这意味着它不分析多文件项目、跨文件类归属或完整依赖图。

### 5.3 Analysis Record 是否足够支持 Similarity

| 分析维度 | 已有 | 可靠性 | 是否适合用于 Similarity |
|---|---|---|---|
| Symbol Similarity | External YES；Feature Registry NO；Feature source_analysis PARTIAL | LOW / MEDIUM | 只适合候选召回，不适合自动判定 |
| Function Name Similarity | External functions；Feature interfaces | LOW / MEDIUM | 词法辅助证据 |
| API / Signature Similarity | External params/returns；Feature YAML signatures | MEDIUM（但 Index 丢失签名） | 需要归一化后才可用 |
| Inheritance Similarity | External `extends`；Feature 无继承字段 | LOW | 不能作为主要证据 |
| Dependency Similarity | Feature graph 80 edges；External 只有 calls/connections | LOW（External） | 只能作为辅助 |
| Capability Similarity | Feature `provides`；External 无 capability | LOW | 当前不能做语义比较 |
| Behavior Similarity | 60 条 Feature source analysis；8/60 L4 evidence；External 无行为契约 | LOW / PARTIAL | 只能人工辅助 |
| Structural Similarity | External class/functions/calls；Feature source_analysis entry/state/conditions | LOW | 无 fingerprint、无归一化 |
| Semantic Similarity | — | NONE | NOT_IMPLEMENTED |

结论：当前 External Analysis 可以支持**符号级检索、结构证据汇总和人工审查**，不能支持可靠的自动语义 Similarity。

### 5.4 Analysis Index

实际结构：

```json
{
  "schema": "external_code_analysis_index",
  "schema_version": 1,
  "generated_at": "...",
  "analyses": [...]
}
```

Index 每条实际字段：

```text
analysis_id
analysis_status
commit_sha
commit_sha_full
entry_points
file_type
license_status
parse_status
provenance_status
reference_path
repo
snippet_id
source_path
symbols
unresolved_questions
```

核对结果：

- 14 条 records / 14 条 index entries；ID 集合完全一致；
- 没有 index-only 或 file-only 记录；
- Index **不包含** `source_digest`、`source_exists`、`license_basis`、`license_risk`、`copy_allowed`、`limitations`、`functions_analyzed`、`state_changes`、`conditions`、`side_effects`、`failure_paths`；
- 因此 Index 可以定位记录，但不能独立验证源码与记录是否一致；
- `build_index()` 由 `write_record()` 的 record 目录生成，不在本阶段执行 Reindex；
- Search 以 `snippet_id` / `analysis_id` 为键加载；当前无重复 snippet，但 `_load_analysis_index()` 的 dict 构造会在同一 snippet 有多条 Analysis 时只保留后出现的一条（当前数据未触发）。

Search 实际能力：

- `--analysis`：附加 Analysis Record；
- `--symbols`：匹配 class/extends/functions/signals/exports/variables/constants/entry_points 的名称字符串；
- `--analysis-status`：按状态过滤；
- 默认 snippet 搜索不读取 Analysis；
- Feature 搜索不读取 Analysis，也不读取 `summary`；
- 没有 Feature ↔ Analysis 的 join 查询。

### 5.5 Batch B 结论

**可以直接使用的字段：**

- `analysis_id`、`snippet_id`、`repo`、`source_path`、`source_url`、`commit_sha(_full)`；
- `source_digest`、`input_digest`、`provenance_status`、`license_status`、`copy_allowed`；
- `parse_status`、`analysis_status`、`source_analysis_status`；
- `symbols` 的 class/functions/signals/exports/variables/constants；
- `entry_points`、`limitations`、`unresolved_questions`。

**只能作为辅助证据的字段：**

- `state_changes`、`conditions`、`signals_events`、`side_effects`、`failure_paths`；
- `calls`、`connections`；
- `extends`（只有直接 base）。

**不能用于自动判断的字段：**

- `analysis_status=analysis_complete`：不等于功能正确、可复用或已验证；
- `analysis_partial`：不能自动降级为“相似”；
- `symbols` 名称：不能单独证明功能相同；
- `side_effects` / `conditions` 的空值：不能证明没有副作用。

**当前缺少：**

- `feature_id`、`feature_candidate_id`；
- `capabilities` / semantic tags；
- 多文件 dependency graph；
- 跨文件 class attribution；
- normalized API signature；
- symbol fingerprint；
- behavior contract / test evidence；
- Feature-side provenance 对账。

---

## 6. Promote & Admission Audit

### 6.1 Promote 实际调用链

入口：`.ai/skills/foundation/godot-gdscript/tools/github_collector.py:1049` 的 `cmd_promote()`。

实际流程：

```text
cmd_promote(args)
  -> 校验 name（snake_case）与目标目录不存在
  -> _read_catalog_entries()
  -> 检查 snippet 存在、duplicate_of、reference 文件存在
  -> assess_license()
  -> assess_provenance()
  -> dest.mkdir()
  -> 写 <name>.gd：原始片段拷贝 + "TODO(agent): 以上是原始片段拷贝，抽象重写为正式实现"
  -> 写 feature.yaml：FEATURE_YAML_TEMPLATE（summary/TODO、provides TODO、空 interfaces/ownership）
  -> 写 README.md：README_TEMPLATE
  -> 写 test_<name>.gd：TEST_TEMPLATE（恒定 FAIL 占位）
  -> subprocess 调用 FEATURE_INDEX_BUILDER
  -> 打印下一步提示
```

关键事实：

- Promote 从 **Catalog snippet** 读取，不从 External Analysis Record 读取；
- 没有调用 `external_code_understanding.py`；
- 没有调用 `check_feature_metadata.py`；
- 没有运行 Feature test；
- 没有调用 `run_tests.py`；
- 没有人工 review / approval 记录；
- 没有 admission status；
- 索引刷新发生在 scaffold 写完以后，所以 scaffold 可以进入 `feature_index.json`。

### 6.2 Promote 输出性质

| 产物 | 实际内容 | 是否经过验证 |
|---|---|---|
| Raw Code Copy | 原始 snippet + TODO 标记 | NO |
| Feature Scaffold | `feature.yaml` 模板，含 TODO | NO |
| Metadata | summary/provides/interfaces 等大量 TODO/空值 | NO |
| README | 使用说明脚手架 | NO |
| Placeholder Test | 恒定 `FAIL ... test not implemented (scaffold placeholder)` | NO |
| Feature Index entry | `build_feature_index.py` 生成 | 只验证 metadata 可解析，不验证实现 |
| Actual Implementation | 无自动生成 | NO |
| Validated Implementation | 无 | NO |

结论：**Promote = 原始代码复制 + Scaffold 生成 + Index refresh**，不是 Candidate Synthesis，不是 Feature Validation，更不是 Feature Admission。

### 6.3 Feature Admission Gate 现状

| 检查项 | 是否存在 | 实际证据 |
|---|---|---|
| 明确 Feature Review | **NO** | 无 feature review 文件/状态/命令 |
| 人工批准记录 | **NO** | 只有 Binding / Knowledge / Trace 的 approval registry |
| 测试通过要求 | **NO** | Promote 不运行测试；Registry 不记录测试结果 |
| Compatibility 检查 | **NO（针对 Feature admission）** | Scene Composer 有场景兼容性，不是 Feature 准入 |
| Provenance 检查 | PARTIAL（Promote 时） | `assess_provenance()`；不写入 Feature status |
| License 检查 | PARTIAL（Promote 时） | `assess_license()`；不写入 Feature status |
| 正式 Admission Status | **NO** | 31 个 `feature.yaml` 没有 `status`；全局 `grep admission/ADMITTED` 无结果 |
| 阻止未验证 Feature 进入 Registry | **NO** | 只要 metadata 可解析即可进入 Index |
| Feature Tests 结果进入 Index | **NO** | `feature_index` 只有 `validation.test_path` |

`check_feature_metadata.py` 的真实职责是：

- metadata 存在；
- `id` 与目录名一致；
- 必填字段存在；
- test 文件存在；
- relations 目标 Feature 存在；
- `requires` 有 provider（warning）；
- Index ID/version 同步。

它**不验证**测试通过、不验证运行时行为、不验证代码实现、不验证 provenance、不验证 admission。

### 6.4 状态边界建议（FUTURE DESIGN）

| 状态 | 当前支持 | 说明 |
|---|---|---|
| `EXTERNAL_REFERENCE` | EXISTING | Catalog / Reference Library |
| `ANALYZED` | EXISTING（External only） | Analysis Record / Index |
| `SIMILARITY_REVIEWED` | **MISSING** | 无 Similarity Result / review |
| `CANDIDATE` | PARTIAL（其他领域） | Knowledge/Binding/Trace 有候选模式，Feature 无 |
| `HUMAN_REVIEW` | PARTIAL（其他领域） | Binding/Knowledge/Trace 有审批；Feature 无 |
| `VALIDATION` | PARTIAL | 有验证工具，无 Feature candidate orchestration |
| `VALIDATED` | **MISSING** | 无 Feature 级 validated 状态 |
| `ADMITTED` | **MISSING** | 无 Admission Gate / 状态字段 |

这张状态模型是建议，不是现有实现；不得把 `feature_index` 收录解释为任何后续状态。

### 6.5 Batch C 结论

1. **Promote 应继续保留吗？**
   建议保留，但应明确定位为低层 **scaffold/import utility**，不是 Candidate 或 Admission。
2. **Promote 与 Candidate Synthesis 是否应分离？**
   是。Candidate 需要独立身份、证据、相似性结论、审查和验证；Promote 不应直接触碰正式 Feature Index。
3. **Candidate 是否需要独立 Workspace？**
   是，至少需要与 `Features/` 和 `feature_index.json` 隔离的存储。
4. **Feature Admission 是否需要独立 Gate？**
   是。当前“写入 Index”不能被称为 Admission。
5. **哪些现有模块可复用？**
   `assess_license` / `assess_provenance`、`build_feature_index`、`check_feature_metadata`、`feature_behavior_evidence`、`run_tests.py`、`binding_candidates` 的审批模式、`knowledge_v2` 的 candidate 生命周期。

---

## 7. Similarity & Capability Gap Analysis

### 7.1 六种 Similarity 关系

| Relation | 当前状态 | 现有证据 | 关键缺口 |
|---|---|---|---|
| `DUPLICATE` | **NOT_IMPLEMENTED（Feature）** | Catalog `duplicate_of` 是外部片段内容级重复标记；不是 Feature 功能重复 | 无功能 fingerprint、无 Feature 去重、无人工 review |
| `SIMILAR` | **NOT_IMPLEMENTED** | `provides`/interface/category 词法匹配；`discover_feature` 同义词表 | 无 summary 索引、无语义/行为证据、无 confidence |
| `COMPLEMENTARY` | **PARTIALLY_IMPLEMENTED（声明式）** | `relations.works_with` / `commonly_used_with`；`compose_features` / `dependency_resolver` | 关系是人工声明，不是从代码/证据推导 |
| `CONFLICTING` | **PARTIALLY_IMPLEMENTED（声明式）** | `relations.conflicts`；Scene composition 检查 | 没有自动跨 Feature 状态/接口/所有权冲突检测 |
| `UNRELATED` | **NOT_IMPLEMENTED（显式）** | 无关系边/无匹配即不返回 | 没有“负证据”或置信度；6 个孤立节点只是图事实 |
| `UNKNOWN` | **NOT_IMPLEMENTED（显式）** | 没有 confidence/status 字段 | 搜索无命中被当作“无关”，而不是“证据不足” |

重要限制：

- 符号名相同不等于功能相同；
- 函数名相似不等于行为相似；
- 结构相似不等于可以合并；
- 当前没有任何机制能输出 `DUPLICATE` / `UNKNOWN` 的正式判定。

### 7.2 Similarity Evidence

| Evidence | 当前来源 | 提取方法 | 可靠性 | 局限 | 可自动匹配 | 需人工确认 |
|---|---|---|---|---|---|---|
| Symbol Match | External `symbols`；Feature source_analysis 部分入口 | 正则提取 | MEDIUM | Feature Registry 无符号索引 | 仅候选召回 | 是 |
| API Match | Feature YAML interfaces；External functions params/returns | YAML + 正则 | MEDIUM | Index 丢签名；无类型归一化 | 需先归一化 | 是 |
| Structural Match | External class/functions/calls；Feature source_analysis entry/state/conditions | 正则 + 启发式 | LOW | 无 AST、无 fingerprint | 否 | 是 |
| Dependency Match | `feature_graph` 80 edges；`requires`；External calls/connections | 人工 + 正则 | LOW / MEDIUM | External 无正式 dependency graph | 部分 | 是 |
| Capability Match | Feature `provides`；`capabilities.required` | 人工标签 | LOW | External 无 capability；标签粒度粗 | 仅标签匹配 | 是 |
| Behavioral Evidence | 23 Feature / 60 Behavior source_analysis；8/60 L4 evidence | 静态/运行时 | LOW / PARTIAL | 52/60 无 L4；External 无行为契约 | 否 | 是 |
| Test Evidence | 31 Feature tests；`coverage_matrix` | 文件/覆盖矩阵 | LOW / PARTIAL | 无 Feature 级 test result；本阶段未运行 | 否 | 是 |
| Provenance Evidence | External 45-field records；Feature 注释 11/31 | 结构化 + 文本 | HIGH（External）/ LOW（Feature） | Feature 无结构化 provenance | 对账可以 | 是 |

### 7.3 Capability Extraction

| 层级 | 当前状态 | 证据 |
|---|---|---|
| Script Name | EXISTING | `snippet_id` / `reference_path` / `repo_path` |
| Class Name | EXTRACTED（External） | `symbols.class_name`；10/14 有 `extends` |
| Function Name | EXTRACTED（External） | `symbols.functions`；Feature YAML methods |
| Technical Structure | PARTIAL | functions/calls/connections/state/conditions；无 AST/依赖图 |
| Actual Capability | **NOT_IMPLEMENTED** | 无 `capabilities` 提取字段；`provides` 是人工声明 |
| Validated Capability | **NOT_IMPLEMENTED** | 无 Capability validation / admission |

现有“Capability”相关模块的真实边界：

- `.ai/tools/scene_composer/capability_registry.py`：Scene 能力词表（`Node`、`Collision` 等），不是代码功能语义；
- `.ai/tools/scene_composer/feature_capabilities.py`：只读取 `feature.yaml#capabilities.required`，禁止推断；
- `.ai/tools/feature_registry/compose_features.py:107` `capability_score()`：对 `provides` 标签做匹配；
- `.ai/tools/feature_registry/feature_discovery.py`：`feature_capabilities` 就是 `provides` 的映射；
- `.ai/tools/scene_composer/behavior_protocol.py`：`probe_capabilities()` 探测的是 behavior protocol 的已实现 action，不是 Feature 的语义 Capability；
- `.ai/tools/runtime/repair_engine.py:129` `name_similarity()`：节点名编辑距离，和 Feature Similarity 无关。

**直接回答：当前系统只能提取名称与部分静态结构，不能从代码结构可靠推断“实际功能能力”；更不能把函数名当作已验证 Capability。**

### 7.4 Similarity 数据基础

| 数据 | 现状 | 判断 |
|---|---|---|
| Normalized Feature Metadata | `feature.yaml` 存在；Index 丢失 summary/capabilities/ownership/composition | PARTIAL |
| Symbol Fingerprint | Feature 无；External 有 file digest，但不是 symbol fingerprint | MISSING |
| API Signature | YAML 有；Index 只保留名称 | PARTIAL |
| Dependency Graph | `feature_graph` 31/80；External 无 | PARTIAL |
| Capability Tags | `provides` 存在；External 无；语义层缺失 | PARTIAL / MISSING |
| Evidence References | External 有 source/line/digest；Feature source_analysis 有 scripts；Feature YAML 无 | PARTIAL |
| Validation Status | coverage matrix 8/60；无 Feature status | PARTIAL |
| Provenance | External HIGH；Feature 11/31 注释 | PARTIAL |
| Version Identity | Feature version 整数；External SHA/digest；无统一身份 | PARTIAL |

结论：这些数据可以支撑“候选检索 + 人工判断”，不足支撑自动 Similarity 判定。**不需要新造一整套数据结构；应先扩展现有 Feature metadata/index 和 Analysis index 的字段投影。**

---

## 8. Candidate Workspace Audit

### 8.1 现有 Workspace / 候选目录

| Path | 实际对象 | 数量 | 是否 Feature Candidate |
|---|---|---|---|
| `.ai/knowledge/behavior_learning/candidates/` | Behavior Knowledge candidate（PENDING_REVIEW） | 28 files | NO |
| `.ai/tools/validator/bindings/binding_candidates.json` | Behavior Binding candidate | 1 APPROVED | NO |
| `.ai/tools/validator/bindings/approval_registry.json` | Binding approval records | 62 | NO |
| `.ai/trace_candidates_p24/` | E2E Trace baseline candidates | 2 | NO |
| `.ai/context/asset_reviews/` | Asset review records | 19 files | NO |
| `.ai/learning/mutation_candidates.json` | Mutation candidate | 1 file | NO |
| `.ai/learning/pilot/review_log.json` | Pilot review log | 1 file | NO |
| `Features/` | 正式 Feature | 31 | 正式资产，不是候选区 |
| `.ai/context/feature_index.json` | 正式 Feature Index | 31 | 正式索引，不是候选区 |

**没有 Feature Candidate Workspace、Feature Candidate ID 或 Feature Candidate Schema。**

### 8.2 Candidate 隔离要求

| 要求 | 当前支持 | 说明 |
|---|---|---|
| Candidate Identity | PARTIAL（其他领域） | Binding/Knowledge/Trace 有 ID；Feature 无 |
| Original Reference | PARTIAL | External Record 有；Feature candidate 无 |
| Provenance | PARTIAL | External Record 有；Feature candidate 无 |
| Source Commit | PARTIAL | External Record 有；Feature candidate 无 |
| Extracted Capability | **MISSING** | 无语义能力提取 |
| Similarity Results | **MISSING** | 无 Similarity Result |
| Original Feature References | **MISSING** | 无 candidate→Feature 对照 |
| Proposed Changes | **MISSING** | 无 candidate diff/抽象记录 |
| Human Review Status | PARTIAL（其他领域） | 只有 binding/knowledge/trace 的审批 |
| Validation Results | PARTIAL | 验证工具存在，candidate 结果模式缺失 |
| Admission Decision | **MISSING** | 无 Feature admission |

### 8.3 安全边界

| 边界 | 当前能力 | 结论 |
|---|---|---|
| 不修改原始 Reference | Catalog/Reference 只读；Analysis 只读 | 可以 |
| 不修改正式 Feature | 需要新 candidate 目录 | 当前 Promote 不符合 |
| 不直接进入正式 Feature Index | 当前 Promote 不符合 | 必须隔离 |
| 不自动成为 Knowledge | 当前 `knowledge_status=NOT_KNOWLEDGE` | 可以 |
| 不自动触发 Scene Intent | 当前无连接 | 可以 |
| 不覆盖用户已有内容 | `cmd_promote` 拒绝同名 `Features/<name>` | 仅限 Promote，不构成完整 Candidate 安全 |
| 可人工审查 | Feature 无 review 流程 | **MISSING** |
| 验证失败后保留审计记录 | 其他领域有 append/registry 模式；Feature 无 | PARTIAL |

### 8.4 Batch E 结论

现有系统**不能**安全容纳 Feature Candidate。它只能容纳其他对象的候选。

最小需要增加的不是“大型子系统”，而是：

1. 一个与 `Features/` 和 `feature_index.json` 隔离的 candidate 目录；
2. 一个 candidate metadata schema（candidate id、reference/analysis id、provenance、proposed feature id、similarity evidence、review state、validation result）；
3. 一条 lifecycle（例如 DRAFT → PENDING_REVIEW → APPROVED/REJECTED），复用 `binding_candidates.py` 的显式状态与 digest 模式；
4. 一个不会自动刷新 `feature_index.json` 的 candidate 验证入口。

优先扩展现有目录/模式，而不是新建独立 Candidate Manager。

---

## 9. Validation Infrastructure Audit

### 9.1 Validation Coverage

| Validation Type | Existing Tool | Input | Output | Can Validate Candidate? |
|---|---|---|---|---|
| GDScript 正则解析 | `learning/gd_parse.py` | source text | `Script` / functions / symbols | PARTIAL：只提取，不是真正语法验证 |
| Godot Headless Import / Parse | `run_tests.py` 启动时 `--import` | project root | cache refresh / process status | PARTIAL：固定 project root |
| Feature metadata | `validator/check_feature_metadata.py` | `project_root`、`index_path` | failures/warnings/checked | YES（可传临时 root/index），但只验证 metadata |
| Feature Index 生成 | `feature_registry/build_feature_index.py` | `features_dir`、`out` | index/graph | YES（临时目录），但不构成 admission |
| Feature self-tests | `run_tests.py` | `Features/*/test_*.gd` + `Tests/` | PASS/FAIL/INCOMPLETE | PARTIAL：runner 固定项目根，candidate 需临时项目 |
| Behavior Evidence | `scene_composer/feature_behavior_evidence.py` | `--features-dir`、contracts、Godot | behavior reports/bundles | YES（`BehaviorWorkspace` 复制 Feature 到临时 workspace） |
| Behavior Evidence cross-check | `validator/check_behavior_evidence.py` | persisted bundles + contracts | status / artifact cross-validation | PARTIAL：依赖 bundle 位置 |
| Binding schema | `validator/check_binding_schema.py` | `asset_bindings/*.yaml` | schema failures | PARTIAL：不是 Feature validation |
| Feature instance evidence（静态） | `validator/check_instance_evidence.py` | `template.yaml` + entry `.tscn` | PASS/MISMATCH/INVALID/INSUFFICIENT | YES（若临时 Feature/template） |
| Feature instance evidence（运行时） | `scene_composer/runtime_instance_evidence.py` | `--features-dir`、project root、Godot | runtime report | YES（可传临时 root/features dir） |
| Scene validation | `scene_composer/scene_validator.py` / `validator/unified.py` | Scene Intent / blueprint / scene | layer diagnostics | PARTIAL：场景级，不是 Feature 语义 |
| Compatibility Gate | `scene_composer/compatibility_gate.py` | Scene Intent + Feature index | PASS/BLOCKED | PARTIAL：candidate 需要临时 index |
| Scene artifact evidence | `scene_composer/artifact_evidence_validator.py` | Scene Intent + generated `.tscn` | PASS/BLOCKED | PARTIAL：只读文本；要求 `res://Features/...` 结构 |
| Capability Contract | `scene_composer/capability_contract_validator.py` | Scene Intent / plan | PASS/BLOCKED | PARTIAL：Scene 能力，不是语义 Capability |
| E2E multi-feature | `.ai/tools/e2e/*` | 固定 `PROJECT_ROOT`、真实 Godot | trace/level assertions | **NO（直接）**：固定项目根且会写 probe 文件 |
| Human Review | — | — | — | **NO** |
| Feature Admission | — | — | — | **NO** |

### 9.2 未来 Candidate 验证流程可行性

待评估流程：

```text
Candidate
  -> Syntax Validation
  -> Static Analysis
  -> Dependency Check
  -> Compatibility Check
  -> Test Generation / Existing Tests
  -> Godot Headless Validation
  -> Human Review
```

| Stage | 状态 | 可复用工具 | 说明 |
|---|---|---|---|
| Syntax Validation | PARTIAL | `gd_parse.py` / Godot import | 正则解析不是语法校验；Godot import 可捕获部分错误 |
| Static Analysis | PARTIAL | `source_analysis.py` | 可生成 entry/state/conditions/evidence；无 AST |
| Dependency Check | PARTIAL | `feature_graph` / `compose_features` / Scene dependency resolver | 依赖声明式；External 无依赖图 |
| Compatibility Check | PARTIAL | `compatibility_gate.py` | 需要 Scene Intent 和 Feature index；不是 Feature 级 |
| Test Generation | PARTIAL | `test_generator/generate_scene_test.py` | 只生成 Scene 测试，不生成 Feature 实现测试 |
| Existing Tests | PARTIAL | `run_tests.py` | 固定根；candidate 需临时项目 |
| Godot Headless Validation | EXISTING / PARTIAL | `run_tests.py`、`feature_behavior_evidence.py` | 可运行；不是 candidate 原生入口 |
| Human Review | **MISSING** | 其他领域的 approval 模式 | Feature 无 review schema/registry |
| Admission | **MISSING** | — | 无 Feature admission |

### 9.3 Validation 结论

**可以复用：**

- `check_feature_metadata(project_root, index_path)`；
- `build_feature_index(features_dir)`（临时输出）；
- `feature_behavior_evidence --features-dir` 及 `BehaviorWorkspace`；
- `runtime_instance_evidence --features-dir`；
- `check_instance_evidence`；
- `compatibility_gate(known_features/index_path)`；
- `artifact_evidence_validator`（只读生成物）；
- `gd_parse` / `source_analysis` 的静态证据；
- `binding_candidates` / `knowledge_v2` 的显式审核状态模式。

**必须新增：**

- Feature candidate 验证编排；
- candidate 级 test result / behavior evidence 记录；
- Feature admission gate；
- candidate 与正式 Feature 的隔离路径；
- 可移植的 Feature test path / source reference。

**应始终保留人工判断：**

- `DUPLICATE` / `SIMILAR` 的最终确认；
- `COMPLEMENTARY` / `CONFLICTING` 的合并或组合决策；
- Capability 的语义命名与抽象；
- Candidate 是否进入正式 Feature。

---

## 10. Current Architecture Diagram

### 10.1 Data Flow（实际存在）

```text
[GitHub repositories]
        |
        | github_collector.py: search / fetch
        v
[code_library/sources/<repo>]
        |
        | github_collector.py: catalog
        v
[code_library/catalog.yaml + INDEX.md + candidates.json]
        |                                   \
        |                                    \ (snippet_id)
        |                                     v
        |                          [external_code_understanding.py]
        |                                     |
        |                                     v
        |                          [.ai/learning/external_code/analysis/*.json]
        |                                     |
        |                                     v
        |                          [.ai/learning/external_code/index.json]
        |                                     |
        +------------------+------------------+
                           |
                           v
                 [search_assets.py]
                 (Feature index + Catalog + Analysis index)

[Features/*/feature.yaml]
        |
        | build_feature_index.py
        v
[feature_index.json + feature_graph.json]
        |
        +--> discover_feature.py / feature_discovery.py
        +--> compose_features.py / dependency_resolver.py
        +--> compatibility_gate.py / scene_composer.py

[Features/*/template.yaml#behavior]
        |
        +--> feature_behavior_evidence.py
        +--> source_analysis.py -> .ai/learning/source_analysis/<feature>/*.json
```

### 10.2 Control Flow（实际存在）

```text
github_collector.py
  -> cmd_search / cmd_fetch / cmd_catalog / cmd_check / cmd_backfill_meta
  -> cmd_promote
       -> assess_license / assess_provenance
       -> write Features/<name>/<name>.gd
       -> write feature.yaml / README.md / test_<name>.gd
       -> build_feature_index.py

external_code_understanding.py
  -> analyze_external_code()
       -> gd_parse.parse_text()
       -> source_analysis.analyze_external_scripts()
       -> write_record()
  -> build_index() (CLI --reindex)

Feature consumers
  -> build_feature_index.build_index()
  -> discovery / composition / scene composer
```

当前**没有**：

```text
External Analysis
  -> Similarity Analysis
  -> Capability Extraction
  -> Candidate
```

### 10.3 Validation Flow（实际存在）

```text
Feature metadata
  -> check_feature_metadata.py
       -> feature.yaml schema / test path / index sync

Feature tests
  -> run_tests.py --godot-only
       -> Godot headless --path PROJECT_ROOT -s res://Features/<id>/test_*.gd
       -> PASS / FAIL / INCOMPLETE

Behavior
  -> feature_behavior_evidence.py
       -> BehaviorWorkspace (copy Features to temp)
       -> Godot headless
       -> behavior reports / bundles
  -> check_behavior_evidence.py
       -> cross-validate persisted bundles

Scene
  -> compatibility_gate.py
  -> capability_contract_validator.py
  -> scene_builder.py
  -> artifact_evidence_validator.py
  -> scene_validator.py / unified.py

Instance
  -> check_instance_evidence.py (static)
  -> runtime_instance_evidence.py (opt-in, Godot)
```

### 10.4 当前架构的关键断点

```text
External Analysis --X--> Feature Registry
  (no feature_id / analysis_id link)

Feature Registry --X--> Similarity Engine
  (no similarity module)

Feature Registry --X--> Candidate Workspace
  (Promote writes directly to Features)

Feature --X--> Admission Gate
  (index insertion is not admission)

Source Analysis --X--> Search Assets
  (60 behavior source-analysis records are not indexed by search)
```

---

## 11. Proposed Future Architecture

以下全部是 **FUTURE DESIGN**，本阶段未实现。

```text
[External Reference / Catalog]                         EXISTING
              |
              v
[External Analysis Record + Analysis Index]            EXISTING
              |
              +------------------------------+
              |                              |
              v                              v
[Feature Evidence Projection]           [Similarity Evidence]        PARTIAL / FUTURE
  - summary / scripts / symbols           - symbol/API/structure
  - capabilities / provenance             - dependency/capability
  - behavior / validation status          - behavior/provenance
              |                              |
              +--------------+---------------+
                             |
                             v
                   [Similarity Result]                           MISSING
                   DUPLICATE / SIMILAR
                   COMPLEMENTARY / CONFLICTING
                   UNRELATED / UNKNOWN
                   (evidence + confidence)
                             |
                             v
                [Capability Extraction Candidate]                MISSING
                (human-named, evidence-backed)
                             |
                             v
                [Feature Candidate Workspace]                    MISSING
                - candidate_id
                - source analysis / provenance
                - proposed feature change
                - similarity evidence
                - review status
                - validation results
                             |
                             v
                   [Human Review]                                PARTIAL
                   (reuse binding/knowledge patterns)
                             |
                             v
                [Candidate Validation]                           PARTIAL
                - metadata / index (temp)
                - static source analysis
                - tests / behavior evidence
                - scene compatibility
                             |
                             v
                   [Feature Admission Gate]                      MISSING
                   - provenance / license
                   - test/behavior evidence
                   - review record
                   - admission status
                             |
                             v
                   [Feature Registry]                            EXISTING
```

### 11.1 现有 / 部分存在 / 缺失 / 未来设计

| Component | Classification | 说明 |
|---|---|---|
| External Reference / Catalog | **EXISTING** | 7,270 entries / 6,813 unique |
| External Analysis + Index | **EXISTING** | 14 records |
| Feature Registry + Index + Graph | **EXISTING** | 31 features；但 Index 是 lossy |
| Feature source analysis | **EXISTING** | 60 behavior records，未接入 Search/Registry |
| Feature behavior contracts | **EXISTING** | 23 features / 60 behaviors |
| Similarity Engine | **MISSING** | 无模块、无 fingerprint、无结果 schema |
| Capability Extraction | **MISSING** | 只有 Scene 能力词表和人工 `provides` |
| Candidate Workspace | **MISSING（Feature）** | 其他领域有模式 |
| Feature Human Review | **MISSING** | 其他领域有审批 |
| Validation tools | **EXISTING / PARTIAL** | 工具齐全，candidate orchestration 缺失 |
| Feature Admission Gate | **MISSING** | 无状态、无审批、无阻断 |
| Feature status | **FUTURE DESIGN** | 不应直接把 Index 收录当状态 |

### 11.2 边界原则

- 不新建第二套 Parser：继续使用 `gd_parse.py`。
- 不新建第二套 Source Analysis：继续使用 `source_analysis.py`。
- 不新建第二套 Knowledge Store：继续使用 `knowledge_v2.py`。
- 不新建第二套 Feature Registry：扩展现有 `feature.yaml` / Index projection。
- 不新建独立 Decision Agent：Similarity 只输出证据和候选关系。
- 不把 Scene Intent 扩展为代码学习系统。
- Candidate 不能直接写入 `Features/` 或 `feature_index.json`。
- Admission 必须是独立、可审计、可拒绝的步骤。

---

## 12. Recommended Roadmap

### 12.1 Option A–E 评估

| Dimension | A. Similarity Engine | B. Capability Extraction | C. Candidate Workspace | D. Feature Admission Gate | E. Hybrid Incremental |
|---|---|---|---|---|---|
| Current Prerequisites | Feature index 存在但 lossy；External analysis 仅 14 条 | 可用 Parser/Source Analysis；无语义层 | 其他领域 candidate 模式存在；Feature 无 | metadata/behavior/validation 工具存在；无 status | 现有模块最多，缺口可拆分 |
| Missing Components | fingerprint、normalized metadata、capability tags、similarity schema | semantic taxonomy、multi-file analysis、approval | candidate schema、隔离目录、review、validation record | feature status、review registry、blocking policy | 各阶段缺少量组件 |
| Reuse Potential | 高（Search/Index/Graph） | 高（gd_parse/source_analysis） | 中高（binding/knowledge） | 高（validator/run_tests/behavior） | **最高** |
| Implementation Complexity | 高 | 高 | 中 | 中 | 中 |
| Risk | 高：误判 duplicate/similar | 高：把名称当能力 | 中：候选污染/审核绕过 | 中：阻塞合法 Feature | 低到中：分阶段可回退 |
| Dependency | 依赖 Registry 证据补齐 | 依赖 Similarity/证据 | 依赖 Similarity/Capability | 依赖 Candidate/Validation | 自身可分阶段 |
| Expected Benefit | 高但过早 | 中高但易过度承诺 | 中 | 高 | **最高且可控** |

### 12.2 推荐顺序

**推荐：Option E，按以下顺序分批实施。**

#### Phase 1.73 — Feature Similarity Evidence Foundation（建议下一阶段）

目标：先建立“可比较的证据”，不急着做“自动判断”。

范围建议：

1. 扩展 Feature metadata / Index projection（后续实现，不在本阶段）：
   - summary；
   - scripts / source references；
   - normalized interfaces（至少名称 + signature）；
   - structured provenance；
   - behavior IDs / source_analysis references；
   - validation status（区分 declared / source-analyzed / test-evidenced）。
2. 建立 External Analysis ↔ Feature 的可追溯关联：
   - 用 `snippet_id`、`analysis_id`、`source_path`、`source_digest` 做明确链接；
   - 不修改现有 Analysis Records。
3. 建立只读的 Similarity Evidence 输出：
   - 输出证据、关系候选、置信度、未决原因；
   - 明确 `UNKNOWN`，不把无命中当 `UNRELATED`；
   - 不自动创建 Candidate，不自动合并。
4. 对 31 个 Feature + 14 条 Analysis 做小规模验证，优先使用已有 60 条 Feature source_analysis。

理由：当前最缺的不是“判定算法”，而是可追溯、可比较、可审查的 Feature 证据。

#### Phase 1.74 — Capability Extraction (bounded)

目标：从已分析代码中提取**候选** Capability，不直接写成正式标签。

- 复用 `gd_parse` / `source_analysis`；
- 必须多文件感知或明确限制为单文件；
- 输出 `capability_candidate`，由人工确认；
- 不把函数名直接当 Capability；
- 不自动写入 `feature.yaml#provides`。

#### Phase 1.75 — Feature Candidate Workspace

目标：建立隔离候选区与生命周期。

- 复用 `binding_candidates.py` 的 `DRAFT → PENDING_REVIEW → APPROVED/REJECTED`；
- 复用 `knowledge_v2.py` 的人工 reviewer/reason 要求；
- 不自动刷新 `feature_index.json`；
- 保存原始 Reference、Analysis ID、provenance、similarity evidence、proposed changes、validation results。

#### Phase 1.76 — Feature Admission Gate

目标：把“进入正式 Registry”变成显式、可审计的决定。

- 要求 provenance / license；
- 要求 metadata / source analysis / test or behavior evidence；
- 要求人工 review 记录；
- 明确 `VALIDATED` / `ADMITTED` 状态；
- 阻止 scaffold / placeholder test / 未验证 Candidate 进入正式 Registry。

### 12.3 不建议的路线

- 不建议先做完整 Similarity Engine：输入证据不足，误判风险高。
- 不建议先做 Capability 自动标注：会把名称和结构误当语义。
- 不建议先做大型 Candidate Manager：现有 binding/knowledge 模式足够复用。
- 不建议继续让 Promote 直接刷新正式 Index：这会绕过 Candidate 与 Admission。

---

## 13. Risks & Limitations

| Risk / Limitation | 影响 | 证据 / 说明 |
|---|---|---|
| 未运行测试套件 | 无法确认当前测试是否全绿 | 只运行了只读 metadata 检查；`run_tests.py`、Feature tests、Godot 未执行 |
| 未运行 Godot / E2E | 无法验证运行时行为 | 本阶段只读，避免写入 `.godot`、临时场景与证据 |
| External Analysis 覆盖极小 | 14 / 6,813 unique fragments（约 0.2%） | 不能据此推断全库能力 |
| Feature Index 丢字段 | Similarity 输入不完整 | `summary`、`capabilities`、`ownership`、`composition`、签名、provenance、status 不在 Index |
| 31/31 test_path 绝对路径 | Candidate/跨工作区验证不可移植 | 例如 `F:/Godot_v4.7-stable/game/...` |
| Parser 无 AST | 结构/语义证据有限 | `_syntax_limitations()`；Inner class、lambda、注解、多行语法均受限 |
| 单文件分析 | 跨文件依赖/归属缺失 | `analyze_external_code()` 只传单个 `Script` |
| `analysis_complete` 被误读 | 把分析完成当能力验证 | 状态只说明静态分析完成，无测试/能力验证 |
| `side_effects` 14/14 为空 | 不能证明无副作用 | 只能说明当前提取器未产出 |
| 8/60 evidence verified | 行为证据覆盖低 | `coverage_matrix.json`；fully_covered=0 |
| 8 个 Feature 无行为契约 | 行为相似性缺失 | `anima_behaviour`、`attribute_editor`、`audio_player_pool`、`blackboard`、`clean_copy`、`flying_letter`、`pedestal_interaction`、`pickable_audio` 共 8 个无 behavior（与 23/31 一致） |
| Catalog `duplicate_of` 非功能重复 | 不能当 Feature duplicate | 它是外部片段内容级标记 |
| Promote 直接进入 Index | Candidate/Admission 被绕过 | `cmd_promote` 写 scaffold 后调用 `FEATURE_BUILDER` |
| 无 Feature status / review | 无法区分声明、验证、准入 | 31 个 YAML 无 status；全局无 admission 记录 |
| 现有 candidate 只覆盖其他对象 | 不能直接承载 Feature Candidate | binding/knowledge/trace/asset 均非 Feature |
| E2E 固定 PROJECT_ROOT | 不能直接验证 Candidate | E2E 写入固定项目根下的 probe/scene 文件 |
| 本报告发现与 Phase 1.71 历史统计存在口径差异 | 旧报告不能作为当前数据源 | 以当前实际文件与 JSON 为准 |

### 13.1 未验证事项

明确标注：

```text
Feature self-tests:                   NOT_VERIFIED（本阶段未运行）
Behavior evidence current freshness:  NOT_VERIFIED（未重跑）
Godot headless parse of candidates:   NOT_VERIFIED（未运行）
Promote end-to-end behavior:          NOT_VERIFIED（未执行 Promote）
Feature Admission absence:            CONFIRMED（源码/数据无 admission）
Similarity engine absence:            CONFIRMED（源码搜索无模块）
Capability extraction absence:        CONFIRMED（无字段/提取器；只有人工 provides 与 Scene 能力）
```

---

## 14. Final Verdict

**Verdict: `PASS_WITH_LIMITATIONS`**

判定理由：

- Feature Registry、External Analysis、Promote、Similarity/Capability 边界、Candidate Workspace、Validation Infrastructure 均已通过源码与数据审计；
- 关键接口和职责有明确源码证据；
- 没有影响后续架构设计的重大未知问题；
- 但未运行 Feature tests、Godot、E2E、Promote；部分行为/运行时结论只能标为 `NOT_VERIFIED`；
- External Analysis 覆盖率低、Feature Index lossy、Parser 无 AST，这些限制已明确记录，不妨碍制定下一阶段计划。

### 14.1 最终架构判断

```text
EXISTING:
  External Reference / Catalog
  External Analysis Record / Index
  Feature Registry / Index / Graph
  Feature source analysis (60 records)
  Behavior contracts (23 features / 60 behaviors)
  Validation tools
  Candidate patterns for Knowledge / Binding / Trace

PARTIALLY EXISTING:
  Feature descriptions and interfaces
  Feature capability tags (human-declared)
  Dependency graph (declared)
  Behavior evidence (8/60)
  Feature source analysis (50/60 PARTIAL)
  Candidate review patterns (not Feature-specific)

MISSING:
  Feature Similarity Engine
  Feature fingerprint / symbol fingerprint
  Semantic Capability Extraction
  Feature Candidate Workspace
  Feature Admission Gate
  Feature status / review records
  External Analysis ↔ Feature Registry link

FUTURE DESIGN:
  Similarity Evidence Report
  Capability Candidate + human approval
  Feature Candidate lifecycle
  Feature Admission lifecycle
  Validated / Admitted Feature states
```

### 14.2 Acceptance Checklist

- [x] Preflight 完成。
- [x] Git 工作区基线已记录。
- [x] Phase 1.71 关键实现已核实。
- [x] Feature Registry Schema 已审计。
- [x] External Analysis Record Schema 已审计。
- [x] Parser 能力边界已审计。
- [x] Analysis Index 和 Search 能力已审计。
- [x] Promote 完整调用链已追踪。
- [x] Feature Admission 现状已确认。
- [x] 六种 Similarity 关系已分析。
- [x] Capability Extraction 能力已评估。
- [x] Candidate Workspace 现状已评估。
- [x] Validation Infrastructure 已审计。
- [x] 当前架构图已完成。
- [x] 未来架构图已完成。
- [x] 后续 Roadmap 已提出。
- [x] 所有关键结论具有源码/数据证据。
- [x] 最终报告已创建。
- [x] Git 工作区结束状态已核实（见最终回复）。
- [x] 未修改任何原有项目文件。
- [x] 未执行 Commit / Push / Fetch。
