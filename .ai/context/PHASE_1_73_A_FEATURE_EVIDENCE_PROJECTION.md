# Phase 1.73 — Batch A
# Feature Evidence Projection Implementation

状态：**PASS_WITH_LIMITATIONS**

阶段模式：Batch A only。未进入 Batch B，未创建 External Analysis Link，未创建 Similarity Classification，未创建 Feature Candidate / Admission Gate，未修改 Scene Intent / Promote，未提交 Git。

---

## A. Execution Baseline

执行前重新读取实际工作区：

```text
Project Root:       F:/Godot_v4.7-stable/game
Branch:             master
HEAD:               d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Staged Files:       0
Modified Files:     29
Untracked Files:    170（本报告写入前）
Porcelain Records:  140
```

与 Preflight 的关系：

- HEAD、Branch、staged 状态与 `.ai/context/PHASE_1_73_PREFLIGHT.md` 一致。
- Modified 数量仍为 Preflight 记录的 **29**。
- Untracked 从 Preflight 的 **162** 增至 **170**，增量恰好为 Phase 1.73 Preflight 报告、Batch A 实现/测试及 5 个 Pilot Projection（共 8 个新文件）；没有发现需要停止实施的基线冲突。
- 工作区原有 Modified / Untracked 文件保持原状，未被清理、覆盖或恢复。

本批次实际新增/修改文件：

```text
新增  .ai/tools/feature_registry/feature_evidence.py
新增  .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
新增  .ai/learning/feature_evidence/health.json
新增  .ai/learning/feature_evidence/health_bar.json
新增  .ai/learning/feature_evidence/openable_door.json
新增  .ai/learning/feature_evidence/attack_emitter.json
新增  .ai/learning/feature_evidence/blackboard.json
新增  .ai/context/PHASE_1_73_A_FEATURE_EVIDENCE_PROJECTION.md
```

`.ai/context/PHASE_1_73_PREFLIGHT.md` 是上一阶段已创建文件，本批次未修改其内容。

---

## B. Implementation

### B.1 新增模块职责

`.ai/tools/feature_registry/feature_evidence.py`

| 能力 | 实现 |
|---|---|
| 单 Feature 构建 | `build_projection(feature_id, ...)` |
| 构建并写入 | `build_and_write(...)` |
| 读取/校验已有 Projection | `validate_projection(...)`、`check_projection(...)` |
| 路径规范化 | `normalize_path(...)` |
| 来源摘要 | `source_reference(...)` |
| CLI | `build --feature`、`build --pilot`、`build --all`、`check --feature`、`check --pilot`、`check --all`、`--json` |
| 安全写入 | 同目录临时文件 → 回读 → Schema Validation → `os.replace` |

### B.2 数据模型

Projection 顶层字段：

```text
schema / schema_version / projection_id / content_digest
feature_id / feature_name / feature_path / generated_at / extractor_version
source_identity
source_references
analysis_references
descriptive_evidence
capability_evidence
interface_evidence
symbol_evidence
dependency_evidence
behavior_evidence
test_evidence
validation_evidence
provenance_evidence
declared_evidence
extracted_evidence
evidence_counts
path_normalization
projection_status
limitations
```

证据状态严格保留：

```text
DECLARED / EXTRACTED / PARTIAL / MISSING / NOT_APPLICABLE / UNSUPPORTED / CONFLICTED
```

`NOT_APPLICABLE` 独立存在，并配有 `applicability` 原因，例如：

```text
NO_BEHAVIOR_CONTRACT
NO_CAPABILITY_DECLARED
NO_SCENE_CAPABILITY_DECLARED
NO_INTERFACE_DECLARED
NO_DEPENDENCY_DECLARED
```

关键边界：

- `provides`、`capabilities.required`、`requires`、Graph edge 均为 `DECLARED`，不转换为源码验证能力。
- 源码符号来自真实 `.gd` 文件，并带 `source_file`、`source_symbol`、`source_line`、`source_digest`。
- Source Analysis 原始 `analysis_status` 保留；`COMPLETE → EXTRACTED`，`PARTIAL / SOURCE_ENTRY_AMBIGUOUS → PARTIAL`。
- 没有 Behavior Contract 的 Feature 标为 `NOT_APPLICABLE`，不标为 `MISSING`。
- `MISSING` 只用于“应有但未找到”，例如声明了 behavior contract 但没有 Source Analysis record。
- `test_evidence` 只记录文件存在与 `execution_status=NOT_RUN`，不声称测试已执行。
- `content_digest` 排除 `generated_at`、`projection_id`、`content_digest` 自身，用于 Freshness 比较。

### B.3 复用的现有系统

- `build_feature_index.build_index()`
- `build_feature_index.build_graph()`
- `build_feature_index.collect_interfaces()`
- `build_feature_index.normalize_relations()`
- `gd_parse.parse_file()` / `parse_text()`
- 现有 `feature_index.json`
- 现有 `feature_graph.json`
- 现有 `coverage_matrix.json`
- 现有 `source_analysis/<feature>/<behavior>.json`

没有新增 Parser、Registry、Knowledge Store、Similarity Engine 或 Candidate 结构。

### B.4 CLI

```bash
python .ai/tools/feature_registry/feature_evidence.py build --feature health
python .ai/tools/feature_registry/feature_evidence.py build --pilot
python .ai/tools/feature_registry/feature_evidence.py check --pilot
python .ai/tools/feature_registry/feature_evidence.py check --feature health
python .ai/tools/feature_registry/feature_evidence.py build --pilot --json
```

### B.5 写入边界

- 只写入 `.ai/learning/feature_evidence/<feature_id>.json`。
- 不修改 `Features/*/feature.yaml`、`feature_index.json`、`feature_graph.json`、Source Analysis、External Analysis、Scene Intent、Promote。
- 单文件替换是原子的；多文件 Pilot 构建 **不是** 批量事务。一个文件失败不会回滚已经成功写入的其他文件。
- 若构建、序列化、回读校验或 replace 失败，原目标文件保持不变；无原文件时不会留下看似有效的半成品。

---

## C. Pilot Results

所有 5 个 Pilot 均成功生成 Projection，并通过 Schema Validation。

说明：`projection_status` 表示“证据投影本身的完整程度”，不是运行时玩法验证结论。

| Feature | Projection | DECLARED | EXTRACTED | PARTIAL | MISSING | NOT_APPLICABLE | UNSUPPORTED | CONFLICTED | Source Analysis 原始状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `health` | PARTIAL | 27 | 17 | 5 | 0 | 0 | 0 | 0 | 5 × PARTIAL |
| `health_bar` | PARTIAL | 17 | 14 | 5 | 0 | 0 | 0 | 0 | 5 × PARTIAL |
| `openable_door` | COMPLETE | 22 | 16 | 0 | 0 | 0 | 0 | 0 | 1 × COMPLETE |
| `attack_emitter` | PARTIAL | 26 | 16 | 2 | 0 | 0 | 0 | 0 | 2 × SOURCE_ENTRY_AMBIGUOUS |
| `blackboard` | COMPLETE | 14 | 12 | 0 | 0 | 3 | 0 | 0 | 无 Source Analysis |

### C.1 `health`

输入来源：

- `Features/health/feature.yaml`
- `Features/health/template.yaml`
- `Features/health/health.gd`
- `Features/health/test_health.gd`
- 5 条 Source Analysis：`damage`、`death`、`heal_clamped`、`overkill_clamps_at_zero`、`post_death_guard`
- Feature Index / Graph / Coverage Matrix

结果：

- 5 个 behavior 全部保持 `PARTIAL`。
- 5 条 Source Analysis 的 `analysis_status=PARTIAL` 原样保留，没有升级。
- 已提取 `class_name`、`extends`、signal、export、函数、变量等真实符号。
- `provides` 保持 `DECLARED`。

未解决：

- Source Analysis 本身有未决问题，Projection 只转述，不补齐。
- 静态分析不能证明运行时结果。

### C.2 `health_bar`

输入来源：

- `Features/health_bar/feature.yaml`
- `Features/health_bar/template.yaml`
- `Features/health_bar/health_bar.gd`
- `Features/health_bar/test_health_bar.gd`
- 5 条 Source Analysis，全部 `PARTIAL`
- Feature Index / Graph / Coverage Matrix

结果：

- 5 个 behavior 全部保持 `PARTIAL`。
- `health_state` 依赖关系作为 `DECLARED` 结构证据保留，没有被解释为源码实现。
- 已提取真实 GDScript 符号。

未解决：

- 依赖关系仍只有 metadata/graph 级证据。
- 5 条 behavior 仍为静态部分证据。

### C.3 `openable_door`

输入来源：

- `Features/openable_door/feature.yaml`
- `Features/openable_door/template.yaml`
- `Features/openable_door/openable_door.gd`
- `Features/openable_door/test_openable_door.gd`
- 1 条 Source Analysis：`open`，`COMPLETE`
- Feature Index / Graph / Coverage Matrix

结果：

- `open` behavior 映射为 `EXTRACTED`。
- Source Analysis 原始状态保留为 `COMPLETE`。
- 符号证据可追溯到真实文件和行号。

未解决：

- `COMPLETE` 只代表现有静态 Source Analysis 完整，不代表运行时验证或测试通过。
- 测试执行状态仍为 `NOT_RUN`。

### C.4 `attack_emitter`

输入来源：

- `Features/attack_emitter/feature.yaml`
- `Features/attack_emitter/template.yaml`
- `Features/attack_emitter/attack_emitter.gd`
- `Features/attack_emitter/raycast_attack_emitter.gd`
- `Features/attack_emitter/test_attack_emitter.gd`
- 2 条 Source Analysis，均为 `SOURCE_ENTRY_AMBIGUOUS`
- Feature Index / Graph / Coverage Matrix

结果：

- 2 条 Source Analysis 的 `SOURCE_ENTRY_AMBIGUOUS` 原样保留在 `analysis_references`。
- 2 个 behavior 统一映射为 `PARTIAL`，没有升级为 `EXTRACTED`。
- 两个真实 GDScript 文件均被解析并生成可追溯符号证据。

未解决：

- 行为入口仍然歧义，无法据现有证据选定唯一入口。
- 不通过猜测补齐入口。

### C.5 `blackboard`

输入来源：

- `Features/blackboard/feature.yaml`
- `Features/blackboard/blackboard.gd`
- `Features/blackboard/test_blackboard.gd`
- Feature Index / Graph / Coverage Matrix
- 无 `template.yaml#behavior`
- 无 Source Analysis record

结果：

- 没有 Behavior Contract，behavior evidence 为 `NOT_APPLICABLE`，不是 `MISSING`。
- 没有 Source Analysis record，`analysis_references` 为空，不伪造记录。
- 扫描范围仅限 `Features/blackboard/*.gd`，未扫描整个项目。
- 已提取 12 条 `EXTRACTED` 符号证据。
- 没有 capability 声明时，capability evidence 为 `NOT_APPLICABLE`。

未解决：

- 因为没有 behavior contract，无法进行 behavior 级证据对照。
- Graph 关系仅为结构证据，不能证明功能。

---

## D. Freshness

统一执行：

```bash
python .ai/tools/feature_registry/feature_evidence.py check --pilot
```

实际结果：

```text
health:          FRESH
health_bar:      FRESH
openable_door:   FRESH
attack_emitter:  FRESH
blackboard:      FRESH
Exit Code:       0
```

各 Projection 的来源 Digest（显示前 12 位；完整 SHA-256 保存在 JSON 的 `source_digest` / `analysis_digest`）：

| Feature | 来源 | 状态 | Digest 前缀 |
|---|---|---|---|
| health | `Features/health/feature.yaml` | FOUND | `b47add8c4d3f` |
| health | `Features/health/template.yaml` | FOUND | `5c6cfa3ea3df` |
| health | `Features/health/health.gd` | FOUND | `a436c28bbea1` |
| health | `Features/health/test_health.gd` | FOUND | `290b4ac63b27` |
| health | `damage.json` | FOUND | `f79e96afe127` |
| health | `death.json` | FOUND | `95e07cc193f3` |
| health | `heal_clamped.json` | FOUND | `09cd784bb1fa` |
| health | `overkill_clamps_at_zero.json` | FOUND | `147fe2152c68` |
| health | `post_death_guard.json` | FOUND | `041b328f8b28` |
| health_bar | `Features/health_bar/feature.yaml` | FOUND | `37e3ee7544f8` |
| health_bar | `Features/health_bar/template.yaml` | FOUND | `8280c691a218` |
| health_bar | `Features/health_bar/health_bar.gd` | FOUND | `a8583ec29be7` |
| health_bar | `Features/health_bar/test_health_bar.gd` | FOUND | `6c55cd3d5307` |
| health_bar | `damage_updates_health_bar.json` | FOUND | `28fc759f4e5b` |
| health_bar | `death_empties_health_bar.json` | FOUND | `ed67f60b65fe` |
| health_bar | `healing_updates_health_bar.json` | FOUND | `ef3632ac5ca6` |
| health_bar | `initial_health_bar_ratio.json` | FOUND | `ba55889d3762` |
| health_bar | `unbound_bar_reports_no_fill.json` | FOUND | `6649cea27361` |
| openable_door | `Features/openable_door/feature.yaml` | FOUND | `0c03bad77e6f` |
| openable_door | `Features/openable_door/template.yaml` | FOUND | `a3b1dd5a428d` |
| openable_door | `Features/openable_door/openable_door.gd` | FOUND | `8df8e057cac6` |
| openable_door | `Features/openable_door/test_openable_door.gd` | FOUND | `11f6d17c0017` |
| openable_door | `open.json` | FOUND | `30a231148cd2` |
| attack_emitter | `Features/attack_emitter/feature.yaml` | FOUND | `0de5e071fdc7` |
| attack_emitter | `Features/attack_emitter/template.yaml` | FOUND | `f56fabb4c205` |
| attack_emitter | `Features/attack_emitter/attack_emitter.gd` | FOUND | `1ac9da495bcf` |
| attack_emitter | `Features/attack_emitter/raycast_attack_emitter.gd` | FOUND | `74a308826ec9` |
| attack_emitter | `Features/attack_emitter/test_attack_emitter.gd` | FOUND | `bdb97eb44b58` |
| attack_emitter | `raycast_hit_deals_damage.json` | FOUND | `14e94adf5241` |
| attack_emitter | `repeated_attack_can_kill.json` | FOUND | `9f5db1fab2c7` |
| blackboard | `Features/blackboard/feature.yaml` | FOUND | `bf51e91395af` |
| blackboard | `Features/blackboard/blackboard.gd` | FOUND | `77b5ff5badd0` |
| blackboard | `Features/blackboard/test_blackboard.gd` | FOUND | `73c39dfabc34` |
| 共用 | `.ai/context/feature_index.json` | FOUND | `1fdce0264e29` |
| 共用 | `.ai/context/feature_graph.json` | FOUND | `b4ace8a9b069` |
| 共用 | `.ai/context/coverage_matrix.json` | FOUND | `507f4665f6d2` |

Freshness 测试同时验证了：

- 未变化时 `FRESH`。
- 源码 Digest 变化时 `STALE`。
- 新增/删除 Source Analysis record 时 `STALE`。
- 缺失源码被标记为 `MISSING` 并记录 limitation。
- 不存在的 Projection 返回 `MISSING`，无效 Projection 返回 `INVALID`。

---

## E. Path Normalization

Pilot 合计 **48** 条来源路径：

| 结果 | 数量 |
|---|---:|
| `CONVERTED`（Windows 绝对路径 → 项目相对路径） | 43 |
| `RELATIVE`（原本已是项目相对路径） | 5 |
| `RELATIVE_NORMALIZED` | 0 |
| `OUTSIDE_PROJECT` | 0 |
| `UNRESOLVED` | 0 |
| `MISSING` | 0 |

分 Feature：

| Feature | CONVERTED | RELATIVE | 总计 |
|---|---:|---:|---:|
| health | 11 | 1 | 12 |
| health_bar | 11 | 1 | 12 |
| openable_door | 7 | 1 | 8 |
| attack_emitter | 8 | 2 | 10 |
| blackboard | 6 | 0 | 6 |

处理规则：

- `original_path` 始终保留。
- `normalized_path` 使用项目相对 POSIX 路径。
- 转换失败不会丢弃来源，而是保留原始路径并标记 `OUTSIDE_PROJECT` / `UNRESOLVED`。
- 正式 `feature_index.json` 未被重写；Projection 中的路径规范化是派生结果。

---

## F. Tests

### F.1 新增测试

命令：

```bash
python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
```

结果：

```text
Ran 31 tests
OK
Exit Code: 0
```

覆盖范围：

| 类别 | 测试内容 |
|---|---|
| Schema | 必填字段、Schema 版本、Evidence Status、来源追溯字段、非法 Projection 拒写 |
| Evidence | DECLARED 不升级、EXTRACTED 可追溯、PARTIAL 不升级、SOURCE_ENTRY_AMBIGUOUS 保持、MISSING / NOT_APPLICABLE 区分、Graph 不转为源码实现 |
| Path | Windows 绝对路径、相对路径稳定、项目外路径保留原值、不修改 Feature Index |
| Freshness | FRESH、Digest 变化、新增/删除来源、缺失来源 |
| Atomic Write | 构建失败、JSON 写入失败、Schema 失败、Replace 失败时旧文件保持不变；成功时无临时文件残留 |
| Pilot | `health`、`health_bar`、`openable_door`、`attack_emitter`、`blackboard` 各有独立断言 |

Pilot 测试不是只检查文件存在；测试直接对真实只读输入构建 Projection，并断言状态、数量、来源和路径。

### F.2 现有回归

| 命令 | 结果 |
|---|---|
| `python .ai/tools/feature_registry/tests/test_feature_pipeline.py` | 24 checks PASS，0 failures，Exit 0 |
| `python .ai/tools/learning/tests/test_source_analysis.py` | 17 checks PASS，0 failures，Exit 0 |
| `python .ai/tools/validator/check_feature_metadata.py` | 31 Features，0 errors，0 warnings，Exit 0 |

### F.3 CLI 验证

| 命令 | 结果 |
|---|---|
| `python .ai/tools/feature_registry/feature_evidence.py build --pilot` | 5/5 成功，Exit 0 |
| `python .ai/tools/feature_registry/feature_evidence.py check --pilot` | 5/5 FRESH，Exit 0 |

未把“测试文件存在”当作“测试通过”；本报告中的通过结果均来自实际命令退出码与输出。

---

## G. Safety Verification

| 检查项 | 结果 |
|---|---|
| `Features/*/feature.yaml` | 未由 Batch A 修改；工作区仍有 29 个既有 Modified，与 Preflight 一致 |
| `.ai/context/feature_index.json` | 未由 Batch A 修改；测试前后 Digest 一致 |
| `.ai/context/feature_graph.json` | 未由 Batch A 修改 |
| Feature Source Analysis Records | 未由 Batch A 修改；仅读取 |
| External Analysis Records | 未读取/未修改；未执行 6,813 条 External Reference |
| Scene Intent / Promote | 未修改 |
| Candidate / Similarity / Admission | 未创建 |
| 第二套 Parser / Registry | 未创建 |
| Git add/commit/push/reset/checkout/merge/rebase | 未执行 |
| 非本阶段文件清理/覆盖/恢复 | 未执行 |
| Staged Changes | 0 |

原子写入失败测试结果：

| 失败场景 | 结果 |
|---|---|
| 构建过程异常 | 旧 Projection 保持原内容 |
| JSON 写入异常 | 旧 Projection 保持原内容 |
| Schema Validation 失败 | 旧 Projection 保持原内容 |
| 原子 Replace 失败 | 旧 Projection 保持原内容 |
| 成功后临时文件 | 无残留 |

需要明确：以上是**单文件**替换保证。`build --pilot` 是多文件顺序写入，不具备批量事务原子性；若第 3 个文件失败，前 2 个已成功文件不会回滚。

---

## H. Limitations

1. **正则 Parser 限制**：`gd_parse` 不是完整 GDScript AST，不能可靠进行类型推断、复杂表达式求值或动态调用解析。相应证据只标为静态符号级 `EXTRACTED`，并带 `regex_parser_without_ast_or_type_inference` limitation。
2. **没有运行时验证**：Projection 不能证明 behavior 在 Godot 运行时成立。`openable_door` 的 `COMPLETE` 也不等于运行时验证完成。
3. **Source Analysis 原状态保留**：现有 `PARTIAL` / `SOURCE_ENTRY_AMBIGUOUS` 不会被 Projection 修复或升级。Projection 成功不等于 Feature 行为验证完成。
4. **无 Behavior Contract 的 Feature**：只能标记 `NOT_APPLICABLE`；没有自动推断 behavior，也没有生成伪 Source Analysis。
5. **无 Source Analysis 的 Feature**：只扫描自身目录的非 `test_*.gd` 文件；不扫描全项目，不保证覆盖跨目录调用。
6. **声明关系不等于源码实现**：`provides`、`requires`、composition、Graph edge 只作为 `DECLARED` / 结构证据，未进行源码语义验证。
7. **测试未执行**：`test_evidence` 的 `execution_status` 固定为 `NOT_RUN`，只记录测试文件是否存在。
8. **External Analysis 未连接**：本批次没有建立 Feature 与 External Reference 的链接，也没有读取或分析 External Analysis Records。
9. **路径转换边界**：项目外路径不会被强行改写；保留原始值并标记 `OUTSIDE_PROJECT`。当前 Pilot 未出现此类路径。
10. **批量写入非事务**：单文件原子替换，多文件 Pilot 构建不是事务。

---

## I. Final Verdict

**PASS_WITH_LIMITATIONS**

判定依据：

- 5 个 Pilot 全部成功生成 Projection。
- 每个 Projection 通过统一 Schema Validation。
- DECLARED 与 EXTRACTED 严格分离；`provides` 和 Graph edge 未被当作源码验证能力。
- PARTIAL 与 SOURCE_ENTRY_AMBIGUOUS 均保持原状态，没有错误升级。
- MISSING 与 NOT_APPLICABLE 已区分；`blackboard` 正确使用 `NOT_APPLICABLE`。
- Windows 绝对路径规范化成功，原始路径保留，正式 Feature Index 未修改。
- Freshness Check 可识别 Digest、新增、删除和缺失来源。
- 4 类 Atomic Write 失败测试全部通过，旧 Projection 未被破坏。
- 新增 31 项测试全部通过；现有 Pipeline / Source Analysis / Metadata Validator 回归全部通过。
- 未修改禁止范围内的 Feature Metadata、Feature Index、Feature Graph、Source Analysis、External Analysis、Scene Intent 或 Promote；未创建 Candidate / Similarity / Admission。

限制主要来自现有正则 Parser、静态分析边界、未执行运行时测试，以及 External Analysis 尚未连接。这些限制已明确记录，未被伪装为已验证能力。

**Batch A 到此停止。未进入 Batch B。等待人工验收和下一步明确授权。**
