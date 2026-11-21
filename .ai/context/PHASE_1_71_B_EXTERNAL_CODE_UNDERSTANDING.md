# Phase 1.71 — Batch B: External Code Understanding

状态：**PASS_WITH_LIMITATIONS**

范围：只实现 External Code Understanding、Analysis Record、Bounded Pilot 与 Search 查询接入。未批准 Knowledge、未创建 Feature、未修改 Scene Intent、未全量分析 6,813 条 Unique Reference、未重建 Catalog、未修改 Source/Reference Library。

## 1. B-1 Existing Parser Capability Audit

审计对象：`.ai/tools/learning/gd_parse.py`

结论：

- 现有 Parser 是无项目依赖的正则 Parser，不是第二套 Parser 的替代品。
- 支持独立 `.gd` 文件、`class_name`、`extends`、函数、信号、`@export`、`var`、`const`、基础调用与连接。
- 给出 `Script`/`Function`/`Signal`/`Variable` 等结构化结果，包含文件与行号，可用于 Analysis Record。
- 明确限制：
  - 没有 AST 与类型推导；
  - 不支持完整 Inner Class 语义；
  - 注解只覆盖 `@export`/`@onready` 等已识别形式；
  - Lambda 只能作为文本/调用上下文出现，不能做语义分析；
  - 多行表达式、复杂语法不能保证完整归属；
  - `.gdshader` 不在 GDScript Parser 范围内。

因此 Batch B **没有新建 Parser**。对于同一个已解码文本，adapter 使用 `gd_parse.parse_text()`，避免重复读文件或引入第二套解析逻辑。

## 2. B-2 Existing Source Analysis Audit

审计对象：`.ai/tools/learning/source_analysis.py`

原 `analyze()` 与 Feature/behavior contract 绑定，不能直接用于外部独立脚本；但其入口选择、调用图、状态变量、事件、条件、副作用、失败路径提取逻辑可复用。

最小修改：

- 提取共享 `_extract_evidence()`；
- 增加 `external_entry_names()`；
- 增加 `analyze_external_scripts()`，只接受已解析的 `Script` 列表；
- 将原 `analyze()` 的重复证据提取块改为调用 `_extract_evidence()`；
- 增加 `_safe_rel()`，跨盘符临时目录仍保留可追溯路径，不伪造项目内相对路径。

没有创建第二套 Code Learning Engine，也没有放宽原 Feature 分析的状态语义。Source Analysis 回归 **17/17 PASS**。

外部入口策略：

1. 生命周期函数（`_ready`、`_process`、`_physics_process`、`_input`、`_notification` 等）；
2. 公开函数；
3. 没有入口时回退到全部函数；没有函数则显式 partial。

## 3. B-3 External Code Understanding Adapter

新增：`.ai/tools/external_code/external_code_understanding.py`

职责：

- 输入 Reference 路径 + Catalog/来源元数据；
- 复用 `gd_parse` 与 `source_analysis`；
- 输出结构化 Analysis Record；
- 不写 Knowledge、不创建 Feature、不修改 Library。

明确状态：

- `parsed`
- `partial`
- `parse_failed`
- `unsupported_shader`
- `unsupported_file_type`
- `not_run`
- `analysis_complete`
- `analysis_partial`
- `analysis_failed`
- `blocked_provenance`
- `blocked_license`
- `unsupported_shader`

`.gd` 与 `.gdshader` 分开处理：`.gdshader` 不做 GDScript 解析，不伪装成成功，固定返回 `unsupported_shader`，同时仍记录来源与 License 状态。

License/Provenance 复用 Batch A 的唯一裁决模块：

- `.ai/tools/external_code/provenance.py`
- SPDX allowlist；
- `license_text_missing` 仍按既有策略允许，但写入风险；
- 未知 License 不允许复制；
- 短 SHA 不升级为完整 SHA；
- 缺失 Commit / 不可追溯来源返回 `blocked_provenance`。

Source/Reference 一致性：

- 记录 `source_file_path`、`source_digest`、`source_exists`、`source_consistent`；
- 对比 Reference 头之后的正文与 Source 文件；
- 不一致或 Source 缺失时进入 `analysis_partial`，不静默通过。

## 4. B-4 External Code Analysis Record

输出目录：

`.ai/learning/external_code/analysis/<analysis_id>.json`

索引：

`.ai/learning/external_code/index.json`

Record 关键字段：

- `schema` / `schema_version`
- `analysis_id`（Repository + Commit + Path + 输入摘要 + Parser 版本的确定性哈希）
- `snippet_id`
- `repo`
- `source_path`
- `reference_path`
- `domain`
- `commit_sha`
- `commit_sha_full`
- `source_url`（完整 SHA 固定链接）
- `provenance_status` / `provenance`
- `license` / `license_status` / `license_text_present` / `license_basis` / `license_risk` / `copy_allowed`
- `file_type`
- `parser_name` / `parser_version`
- `input_digest`
- `parse_status`
- `analysis_status`
- `source_analysis_status`
- `symbols`
- `entry_points`
- `state_changes`
- `conditions`
- `signals_events`
- `side_effects`
- `failure_paths`
- `unresolved_questions`
- `limitations`
- `knowledge_status = NOT_KNOWLEDGE`
- `approved_knowledge = false`
- `feature_created = false`

写入语义：相同输入产生相同 `analysis_id` 与相同记录路径；不同 Commit 或不同文件内容产生不同记录。记录是证据，不是正式 Knowledge，也不创建 Feature。

## 5. B-5 Bounded Analysis Pilot

### 样本选择

候选 15 条，实际分析 14 条。唯一跳过项：

- `Ark2000__PankuConsole__addons__panku_console__modules__keyboard_shortcuts__env.gd`
- Catalog 标记 `duplicate_of = Ark2000__PankuConsole__addons__panku_console__modules__history_manager__env.gd`
- 该 duplicate 没有独立 Reference 文件；因此不伪造分析记录，改分析其目标 `history_manager__env.gd`。

### 来源解析

通过 GitHub API 只读解析完整 SHA；所有完整 SHA 均与 Catalog 的 12 位短 SHA 前缀一致。

特别验证：

- `foxssake/netfox` 当前 `main` head 为 `a482c975...`，与 Catalog 短 SHA `cf5189d18e98` 不同；
- 因此没有使用当前分支 head，而是按 Catalog 短 SHA 解析为
  `cf5189d18e98766022c8c1c5e637a6a30c4c3703`。

### Pilot 结果

| Reference | Commit (short) | parse / analysis | entries / functions | provenance | license | source consistent |
|---|---|---|---|---|---|---|
| `Ark2000__PankuConsole__addons__panku_console__modules__history_manager__env.gd` | `863324dfb752` | parsed / analysis_partial | 1 / 1 | complete | eligible | yes |
| `Ark2000__PankuConsole__addons__panku_console__modules__interactive_shell__mini_repl_2.gd` | `863324dfb752` | parsed / analysis_partial | 1 / 1 | complete | eligible | yes |
| `Ark2000__PankuConsole__addons__panku_console__res__shader__simple_fast_blur.gdshader` | `863324dfb752` | unsupported_shader / unsupported_shader | 0 / 0 | complete | eligible | yes |
| `alfredbaudisch__Godello__addons__uuid__uuid.gd` | `4458a143644f` | parsed / analysis_complete | 4 / 4 | complete | eligible | yes |
| `alfredbaudisch__Godello__scripts__board_card.gd` | `4458a143644f` | parsed / analysis_partial | 3 / 4 | complete | eligible | yes |
| `alfredbaudisch__Godello__scripts__board_member_button.gd` | `4458a143644f` | parsed / analysis_partial | 3 / 7 | complete | eligible | yes |
| `alfredbaudisch__Godello__scripts__drag_utils.gd` | `4458a143644f` | parsed / analysis_complete | 3 / 3 | complete | eligible | yes |
| `alfredbaudisch__Godello__scripts__events.gd` | `4458a143644f` | partial / analysis_partial | 0 / 0 | complete | eligible | yes |
| `blackears__cyclopsLevelBuilder__godot__addons__cyclops_level_builder__actions__cyclops_action.gd` | `ea41feaab5dd` | partial / analysis_partial | 2 / 4 | complete | eligible | yes |
| `ceceppa__anima__addons__anima__motion__runtime__anima_race_instance.gd` | `f4a454ebd4d5` | parsed / analysis_complete | 3 / 4 | complete | eligible | yes |
| `cis-ash__TEXTREME__Scenes__EffectParameterSelector__EffectParameterSelector.gd` | `673dc09d9132` | parsed / analysis_complete | 4 / 4 | complete | eligible | yes |
| `derkork__godot-statecharts__addons__godot_state_charts__animation_tree_state.gd` | `76d226a3efac` | partial / analysis_partial | 1 / 3 | complete | license_text_missing | yes |
| `foxssake__netfox__examples__forest-brawl__scripts__play-random-3d.gd` | `cf5189d18e98` | parsed / analysis_complete | 2 / 2 | complete | eligible | yes |
| `foxssake__netfox__examples__multiplayer-state-machine__scripts__character-states__Idle.gd` | `cf5189d18e98` | parsed / analysis_partial | 2 / 2 | complete | eligible | yes |

### 解析成功率

GDScript 13 条：

- `parsed`：10 / 13 = **76.9%**
- `partial`：3 / 13 = **23.1%**
- `parse_failed`：0 / 13 = **0%**

全部 14 条（含 shader）：

- `parsed`：10
- `partial`：3
- `unsupported_shader`：1
- `parse_failed`：0

### 部分解析数量与原因

3 条 GDScript `partial`：

1. `events.gd`：信号-only 文件，正则 Parser 没有找到函数，显式 partial；没有伪造成成功。
2. `animation_tree_state.gd`：存在未完全解释的注解（第 4、5 行）；同时该仓库没有 root License 文本，记录 `license_text_missing`。
3. `cyclops_action.gd`：存在未完全解释的注解（第 27、28 行）。

没有 `parse_failed`。缺失文件、未知来源、License 阻断等失败路径已由隔离测试覆盖，但真实 Pilot 中均未触发。

### Analysis 结果统计

- Analysis Record：14
- `analysis_complete`：5
- `analysis_partial`：8
- `unsupported_shader`：1
- 发现的入口点：29
- 解析函数：39
- 状态变化：8
- 条件：34
- 信号/事件：2
- 副作用：0（当前样本的入口函数未命中共享副作用提取模式）
- 失败路径：3

`analysis_partial` 的 8 条原因归类：

- 缺少 `class_name`，无法做跨类静态归属：5 条
  - `board_card.gd`
  - `board_member_button.gd`
  - `mini_repl_2.gd`
  - `Idle.gd`
  - `history_manager/env.gd`
- 注解未完全解释：2 条
  - `animation_tree_state.gd`
  - `cyclops_action.gd`
- 没有函数：1 条
  - `events.gd`

这些记录仍保留已解析的函数、入口、条件与失败路径；partial 表示证据不完整，不表示文件不可读或分析失败。

### Source Analysis 示例

- `drag_utils.gd`：3 个入口 `get_drag_data`、`find_closest_horizontal_child`、`find_closest_vertical_child`。
- `anima_race_instance.gd`：入口 `advance`、`restore_initial`、`force_complete`；捕获 2 条失败路径（`early_return` 与 `guard_return`）。
- `animation_tree_state.gd`：入口 `_ready`；捕获状态变量 `_animation_tree_state_machine` 与一条 `guard_return`。
- `Idle.gd`：入口 `display_enter`、`tick`；捕获状态变量 `character`、`input`。
- `EffectParameterSelector.gd`：入口 `get_random_vector`、`_ready`、`_notification`、`_process`。

## 6. B-6 Search Integration

修改：`.ai/tools/feature_registry/search_assets.py`

新增：

- `--analysis`：附加完整 Analysis Record；
- `--symbols <text>`：按 Analysis 中的函数/类/信号/变量/入口符号过滤；
- `--analysis-status <status>`：按 `analysis_complete` / `analysis_partial` / `unsupported_shader` 等过滤；
- `--analysis-index <path>`：测试或自定义索引；
- `--query` 在仅使用符号/状态过滤时可省略。

实际验证：

```text
python .ai/tools/feature_registry/search_assets.py --symbols "_state" --limit 5 --json
```

返回：

```text
derkork__godot-statecharts__addons__godot_state_charts__animation_tree_state.gd
analysis_partial
```

```text
python .ai/tools/feature_registry/search_assets.py --query "" --analysis-status analysis_complete --limit 10 --json
```

返回 5 条 `analysis_complete`：

- `play-random-3d.gd`
- `uuid.gd`
- `drag_utils.gd`
- `EffectParameterSelector.gd`
- `anima_race_instance.gd`

缺失 Analysis Index 时显式抛出 `Analysis Index Missing`，不会静默退化成普通搜索。

## 7. B-7 Batch B Tests

新增隔离测试：`.ai/tools/external_code/tests/test_batch_b.py`

覆盖 33 项：

- 正常 `.gd`：函数、类、信号、export、变量、常量、入口；
- 状态、条件、事件、副作用、失败路径；
- 完整 Commit SHA 与固定 Source URL；
- Source 与 Reference 一致性；
- `.gdshader` → `unsupported_shader`；
- 非支持文件类型；
- 缺失 Reference → `parse_failed`；
- 不完整语法 → `partial`；
- 无 `class_name` → parsed + `analysis_partial`；
- 未知/短 Provenance；
- 允许/阻断/待审 License；
- Source 缺失或内容不一致；
- 不同 Commit 生成不同 Analysis ID；
- 幂等写入；
- Analysis Index；
- Search 符号查询、Analysis 附加、状态过滤、索引缺失；
- 不创建 Feature、不生成 Approved Knowledge。

全部测试结果：

```text
python .ai/tools/external_code/tests/test_batch_b.py
PASS: Batch B 33 checks

python .ai/tools/learning/tests/test_source_analysis.py
===== test_source_analysis: 17 checks, 0 failures =====

python .ai/tools/feature_registry/tests/test_phase169_tooling.py
PASS: Phase 1.69-A tooling hardening tests

python .ai/tools/external_code/tests/test_batch_a.py
PASS: Batch A 38 checks
```

`py_compile` 对 adapter、search、Batch B 测试通过。

## 8. 来源追溯验证

14/14 条记录：

- `provenance_status = complete`
- `commit_sha_full` 为 40 位完整 SHA
- `source_url` 为包含完整 SHA 的固定 GitHub 链接
- 原始 Reference 文件存在
- Source 文件存在
- `source_consistent = true`

示例固定链接：

```text
https://github.com/alfredbaudisch/Godello/blob/4458a143644fbadec23ae0cee99578ad3b811eb8/scripts/events.gd
```

Analysis Record 同时保留 `reference_path`、`source_path`、`source_file_path`、`source_digest`、`input_digest`，可回溯到 Repository、Commit、原始文件与本次输入内容。

## 9. 边界与未做事项

- 未自动批准任何 Knowledge：14/14 `knowledge_status = NOT_KNOWLEDGE`，`approved_knowledge = false`。
- 未创建任何正式 Feature：14/14 `feature_created = false`。
- 未修改 Scene Intent 职责。
- 未分析全部 6,813 条 Unique Reference，只做了 14 条 Bounded Pilot。
- 未执行 Catalog 全量重建。
- 未修改 Source/Reference Library。
- 未执行 Git Commit / Push。
- `.gdshader` 只标记状态，不实现 Shader 语义分析。
- Source Analysis 仍是静态证据，不是运行时验证；没有宣称运行时行为已观测。
- `class_name` 缺失的跨类归属仍是限制；这 5 条保持 partial，没有猜测。
- `statecharts` 的 `license_text_missing` 按既有 SPDX 策略允许，但风险已记录。

## 10. 结论

Batch B 已完成 B-1 至 B-7：

- Parser 与 Source Analysis 的现有能力已审计；
- 复用现有 Parser，没有第二套解析器；
- 外部分析通过最小 adapter 接入；
- Analysis Record 可追溯且不进入 Knowledge/Feature；
- 真实 14 条 Pilot 已完成并有真实统计；
- Search 已能按 Analysis 和 Symbol 查询；
- 隔离测试与既有回归全部通过。

剩余限制是正则 Parser 的语义上限与 5 条缺 `class_name` 的跨类归属问题，不是 Batch B 阻塞项。
