# Phase 1.73 — Preflight

状态：**PASS**

阶段模式：Preflight only。未开始 Batch A，未实现 Feature Evidence Projection，未创建 External Analysis Link，未创建 Candidate，未修改 Feature Registry / Analysis Record / Scene Intent / Promote。

---

## 1. Preflight Gate

```text
PHASE_1_73_PREFLIGHT

Status:                    PASS
Feature Registry:          CONFIRMED
Feature Source Analysis:   CONFIRMED
External Analysis:         CONFIRMED
Existing Search:           CONFIRMED
Working Tree:              RECORDED
Write Safety:              CONFIRMED（Batch A 计划范围内）
```

Batch A 尚未执行；本报告只确认基线、复用边界、写入边界和最小实现方案。

---

## 2. Git Baseline

Preflight 开始时实际读取：

```text
Project Root:       F:/Godot_v4.7-stable/game
Branch:             master
HEAD:               d64b1cd5b576a44dcfafd7becbb2d2a7f1fd6a84
Staged Files:       0
Modified Files:     29
Untracked Files:    162
Working Tree:       136 条 porcelain 记录
```

与 Phase 1.72 历史基线的差异：

- Phase 1.72 结束时为 `modified=29`、`untracked=162`，其中包含 Phase 1.72 审计报告。
- 当前 Preflight 前仍为同一 HEAD、同一分支、同一 staged/modified/untracked 数量。
- 未发现审计目标文件被覆盖；Phase 1.73 的 7 个目标报告全部 `ABSENT`。

本阶段结束时只允许新增本 Preflight 报告，不应出现其他项目文件改动。

---

## 3. Phase 1.72 报告确认

已读取：

```text
.ai/context/PHASE_1_72_FEATURE_SIMILARITY_CANDIDATE_SYNTHESIS_AUDIT.md
```

确认以下关键事实与当前源码/数据一致：

| 事实 | 当前状态 |
|---|---|
| Feature Index 只有 9 个投影字段 | CONFIRMED |
| `summary` / `capabilities` / `ownership` / `composition` / provenance / status 不在 Index | CONFIRMED |
| 31 个 Feature test 路径为绝对 Windows 路径 | CONFIRMED |
| 60 条 Feature behavior source analysis 存在 | CONFIRMED |
| External Analysis 与 Feature Registry 无连接键 | CONFIRMED |
| Promote 直接写 `Features/` 并刷新 Index | CONFIRMED |
| 无 Feature Similarity Engine | CONFIRMED |
| 无 Feature Candidate Workspace | CONFIRMED |
| 无 Feature Admission Gate | CONFIRMED |

本次 Preflight 没有重新实施 Phase 1.72 的审计，也没有把 Phase 1.72 的历史统计强行套到当前数据上。

---

## 4. Current Data Baseline

### 4.1 Feature Registry

| 数据 | 当前实际值 |
|---|---:|
| Feature directories | 31 |
| `feature.yaml` | 31 |
| Feature Index entries | 31 |
| Feature Graph nodes | 31 |
| Feature Graph edges | 80 |
| Feature self-test files | 31 |
| `template.yaml` | 23 |

Feature Index 生成时间：

```text
2026-10-31T13:29:04Z
```

### 4.2 Feature Source Analysis

| 数据 | 当前实际值 |
|---|---:|
| Source-analysis records | 60 |
| Features represented | 23 |
| `COMPLETE` | 5 |
| `PARTIAL` | 50 |
| `SOURCE_ENTRY_AMBIGUOUS` | 5 |

实际目录：

```text
.ai/learning/source_analysis/<feature_id>/<behavior_id>.json
```

每条记录实际包含：

```text
analysis_status
behavior_category
behavior_id
conditions
contract_reference
contract_version
entry_points
events
failure_paths
feature_id
generated_at
implementation_references
schema
schema_version
scripts
side_effects
state_variables
static_only
unresolved_questions
```

### 4.3 External Analysis

| 数据 | 当前实际值 |
|---|---:|
| Analysis Records | 14 |
| Analysis Index entries | 14 |
| `analysis_complete` | 5 |
| `analysis_partial` | 8 |
| `unsupported_shader` | 1 |

实际目录：

```text
.ai/learning/external_code/analysis/*.json
.ai/learning/external_code/index.json
```

### 4.4 Existing Evidence / Candidate Modules

Preflight 搜索确认：

- 没有 `feature_evidence`、`feature_evidence_projection` 或 Feature projection 实现；
- 没有 Feature Candidate Workspace；
- 现有 Candidate/Review 实现只面向 Knowledge、Binding、Trace Baseline 和 Asset Review；
- 没有现成的 Feature Similarity Engine。 

---

## 5. Integrity and Freshness Checks

### 5.1 Feature Index / Graph 与 Metadata 的一致性

只读调用：

```text
build_feature_index.build_index("Features")
build_feature_index.build_graph(records)
```

结果：

```text
build_errors:       []
record_count:       31
index_count:        31
graph_nodes:        31
graph_edges:        80
graph_equal:        true
graph_unknown:      []
```

重要观察：

- 31 条重建记录与现有 `feature_index.json` 的语义字段一致；
- **唯一差异是 31/31 条 `validation.test_path` 的绝对路径与相对路径形式**；
- 当前 Index 保存 `F:/Godot_v4.7-stable/game/Features/...`；
- 用相对 `Features` 目录重建得到 `Features/...`；
- 这不是 Metadata 内容冲突，但确认了 Index 的可移植性问题。

Batch A 不得为了修正这个差异而重写正式 `feature_index.json`。Projection 应在自身输出中规范化路径，并记录：

```text
path_form: ABSOLUTE_IN_INDEX
portability: PARTIAL
```

### 5.2 Feature Source Analysis Freshness

对 60 条 records 的 `scripts[].digest` 与当前文件做 SHA-256 对比：

```text
records:             60
stale_records:       0
missing_records:     0
stale_files:         0
missing_files:       0
```

对 60 条 records 的 `contract_version` 与：

```text
.ai/context/coverage_matrix.json
```

逐条比较：

```text
source_rows:         60
coverage_rows:       60
missing_in_coverage: 0
contract_version_mismatch: 0
```

结论：

- 60 条 Feature Source Analysis 当前与实现文件一致；
- 60 条 `contract_version` 与当前 coverage matrix 一致；
- Batch A 可以优先复用这 60 条记录，不需要重新运行全量 source analysis；
- 但 `analysis_status=PARTIAL` / `SOURCE_ENTRY_AMBIGUOUS` 仍必须原样传递，不能因为脚本 digest 一致就提升为完整语义证据。

### 5.3 External Analysis Freshness

对 14 条 records：

```text
source_file_path exists:             14 / 14
source_digest == current source:     14 / 14
reference_path exists:               14 / 14
input_digest == current reference:   14 / 14
```

结论：

- External Analysis Record 的 source 与 reference 当前均未漂移；
- 14 条记录仍可作为 Batch B 的 Pilot；
- External Record 中没有 `feature_id`；
- 14 条 `snippet_id` 没有任何一条直接等于现有 Feature ID；
- 没有现有 Link 文件或 Link 数据。

### 5.4 Test / Behavior 数据

- 31 个 Feature self-test 文件存在；
- 23 个 Feature 有 `template.yaml`；
- 23 个 Feature / 60 个 Behavior 有契约；
- 8 个 Feature 没有 behavior contract：
  `anima_behaviour`、`attribute_editor`、`audio_player_pool`、`blackboard`、`clean_copy`、`flying_letter`、`pedestal_interaction`、`pickable_audio`。
- 没有把“测试文件存在”记录为“测试通过”；
- 本 Preflight 未运行 Feature tests 或 Godot。

---

## 6. Reusable Modules

| Module | Path | Reuse for Batch A | 约束 |
|---|---|---|---|
| Feature metadata | `Features/*/feature.yaml` | 读取 declarative evidence | 只读；不重写 |
| Feature Index builder | `.ai/tools/feature_registry/build_feature_index.py` | 复用 `build_index()`、`build_graph()` | 不调用 CLI 写入正式 Index/Graph |
| Feature Index | `.ai/context/feature_index.json` | 交叉核对 9 字段投影 | 不作为完整事实源 |
| Feature Graph | `.ai/context/feature_graph.json` | Dependency / relation evidence | 只读 |
| Feature source analysis | `.ai/learning/source_analysis/*/*.json` | 复用 60 条 behavior-level evidence | 只读；不调用 `write()` |
| GDScript Parser | `.ai/tools/learning/gd_parse.py` | 从 source-analysis 的 `scripts[].path` 提取 symbol | 不新建 Parser |
| Source Analysis | `.ai/tools/learning/source_analysis.py` | 读取现有记录；理解状态语义 | 不运行 `--all` / `write()` |
| External Analysis | `.ai/tools/external_code/external_code_understanding.py` | Batch B 关联来源 | 不调用 `write_record()` / `build_index()` |
| Search | `.ai/tools/feature_registry/search_assets.py` | 后续查询扩展 | 只读 |
| Metadata Validator | `.ai/tools/validator/check_feature_metadata.py` | 只读 baseline 校验 | 不修改文件 |
| Behavior contracts | `Features/*/template.yaml#behavior` | behavior identity / contract version | 只读 |
| Coverage matrix | `.ai/context/coverage_matrix.json` | contract version / behavior status 对照 | 只读 |

### 6.1 已确认的写副作用

| Tool | 写入行为 | Batch A 使用规则 |
|---|---|---|
| `check_feature_metadata.py` | 搜索不到写文件调用；只读校验 | 可调用 |
| `build_feature_index.py` | `main()` 写 Index + Graph；`build_index()` / `build_graph()` 只读 | 只用函数；禁止 CLI 写正式路径 |
| `source_analysis.py` | `write()` 直接写 `.ai/learning/source_analysis/`；`main()` 可全量写入 | 只读 records；禁止 `write()` / `main()` |
| `external_code_understanding.py` | `write_record()` 写 Analysis；`build_index()` 写 index | Batch A 不调用；Batch B 也只读 |
| `search_assets.py` | 搜索不到写文件调用；只读 | 可调用 |
| `run_tests.py` | 会刷新 Godot import cache、创建临时 evidence | Preflight 不运行；Batch A 不使用 |
| `test_feature_pipeline.py` | 使用系统临时目录；读取真实 Index 作为附加检查 | 可在 Batch A 回归中运行 |
| `test_phase169_tooling.py` | 使用 `.ai/tmp` 临时目录 | 非 Preflight；Batch E 前复核 |

**写入安全结论：**

- Batch A 可以安全读取现有 Registry、Source Analysis、External Analysis；
- Batch A 的输出必须写入新的派生目录，不写 `Features/`、`feature_index.json`、`feature_graph.json`、`source_analysis/`、`external_code/`；
- 原子写入只在 Projection 输出目录内进行，不得跨正式 Registry 做事务承诺。

---

## 7. Batch A Minimal Implementation Plan

### 7.1 Placement

建议新增：

```text
.ai/tools/feature_registry/feature_evidence.py
.ai/learning/feature_evidence/
.ai/tools/feature_registry/tests/test_feature_evidence_projection.py
```

理由：

- `feature_registry` 已是 Feature metadata / index / discovery 的现有工具目录；
- `.ai/learning` 已是派生 evidence 的现有根目录（`source_analysis`、`external_code` 均在此）；
- 不新建第二个 Feature Registry、第二个 Parser、第二个 Source Analysis Engine 或第二个 Knowledge Store；
- Projection 只读正式 Registry，输出派生数据。

### 7.2 Module responsibilities

`feature_evidence.py` 只做以下事情：

1. 读取一个 Feature 的 `feature.yaml`；
2. 读取现有 `feature_index.json` 中的对应条目用于交叉核对；
3. 读取 `feature_graph.json` 中的节点/边；
4. 读取该 Feature 的现有 `.ai/learning/source_analysis/<feature>/*.json`；
5. 从 source-analysis 的 `scripts[].path` 使用 `gd_parse.parse_file()` 做**定向** symbol extraction；
6. 读取 `template.yaml#behavior` 与 coverage matrix 的 behavior/contract identity（只读）；
7. 收集 test file 存在性与声明命令（不执行）；
8. 生成并原子写入一份 Projection；
9. 生成 `content_digest`、`projection_status`、`limitations`；
10. 支持单 Feature 重建、全部 Feature 重建、stale 检查。

明确不做：

- 不执行 `source_analysis.analyze()` 或 `source_analysis.write()`；
- 不运行 `build_feature_index.py` CLI；
- 不修改 Feature metadata / Index / Graph；
- 不执行 Promote / Fetch / Reindex；
- 不比较 Feature 与 External Analysis；Batch B/C 才做；
- 不生成 Similarity Classification；
- 不创建 Candidate；
- 不写 Scene Intent。

### 7.3 Projection Schema（Batch A 目标）

逻辑结构：

```json
{
  "schema": "feature_evidence_projection",
  "schema_version": 1,
  "projection_id": "fep-<stable-digest>",
  "content_digest": "<sha256>",
  "feature_id": "health",
  "generated_at": "<ISO8601>",
  "extractor_version": "phase-1.73-a/1",
  "source_identity": {
    "metadata_path": "Features/health/feature.yaml",
    "metadata_sha256": "<sha256>",
    "feature_version": "1",
    "index_path": ".ai/context/feature_index.json",
    "index_sha256": "<sha256>",
    "graph_path": ".ai/context/feature_graph.json",
    "graph_sha256": "<sha256>",
    "source_analysis_records": [
      {
        "path": ".ai/learning/source_analysis/health/damage.json",
        "contract_version": "562bbb4f6bd7",
        "script_digests": []
      }
    ]
  },
  "descriptive_evidence": [],
  "capability_evidence": [],
  "interface_evidence": [],
  "symbol_evidence": [],
  "dependency_evidence": [],
  "behavior_evidence": [],
  "test_evidence": [],
  "validation_evidence": [],
  "provenance_evidence": [],
  "projection_status": "COMPLETE",
  "limitations": []
}
```

这是 Batch A 的最小结构，不要求在本 Preflight 中固定每个可选字段的最终命名。

### 7.4 Evidence entry shape

每条 Evidence 至少保留：

```json
{
  "evidence_id": "desc:summary",
  "evidence_type": "DESCRIPTIVE",
  "value": {},
  "source_type": "FEATURE_METADATA",
  "source_record_id": "Features/health/feature.yaml",
  "source_file": "Features/health/feature.yaml",
  "source_symbol": null,
  "source_line": null,
  "extraction_method": "yaml.safe_load",
  "extraction_status": "DECLARED",
  "reliability": "HIGH",
  "provenance": {},
  "limitations": []
}
```

规则：

- 能定位到行号时才写 `source_line`；YAML 不伪造行号；
- `DECLARED` 表示人工 metadata 声明；
- `EXTRACTED` 表示现有 Parser 从源码提取；
- `INFERRED` 只用于确实由明确规则推导的内容；
- `PARTIAL` / `MISSING` / `UNSUPPORTED` / `CONFLICTED` 原样记录；
- 不把 `provides` 标签写成“源码验证能力”；
- 不把 `capabilities.required` 写成语义功能 Capability。

### 7.5 Evidence source priority

同一字段出现多个来源时：

| Field | Primary | Secondary | Conflict handling |
|---|---|---|---|
| Feature identity | `feature.yaml` | Index | 不一致 → `CONFLICTED` |
| Summary | `feature.yaml` | README（不解析为权威） | 缺失 → `MISSING` |
| Interfaces | `feature.yaml` | `gd_parse` source symbols | 不一致 → `CONFLICTED` / `PARTIAL`，不自动修正 |
| Provides | `feature.yaml` | source analysis 不能直接验证 | 标记 `HUMAN_DECLARED` |
| Scene capabilities | `feature.yaml#capabilities.required` | capability registry（只判断注册） | 不推断 |
| Dependencies | `feature.yaml` / graph | source analysis 的脚本引用 | 区分 declared / graph-derived / inferred |
| Behavior | source analysis | coverage matrix / template | 只读交叉核对 |
| Test | test file existence | validation command | 文件存在 ≠ 测试通过 |
| Validation result | 无可靠执行记录 | — | `NOT_RUN` |
| Provenance | feature metadata digest | external link（Batch B） | 缺失 → `MISSING`，不补造 |

### 7.6 Projection identity, staleness, atomicity

**Identity：**

```text
content_digest = sha256(
  schema_version
  + canonical(feature metadata)
  + canonical(index record)
  + canonical(graph node/edges)
  + canonical(source_analysis records)
  + extractor_version
)
projection_id = "fep-" + content_digest[:16]
```

`generated_at` 不参与 `content_digest`，因此同一内容不会因为生成时间不同而改变身份。

**Staleness：**

- metadata SHA 变化 → stale；
- source-analysis `scripts[].digest` 变化 → stale；
- contract version 变化 → stale；
- index/graph 语义字段变化 → stale；
- 只有 test path 的绝对/相对形式变化 → 记录 `PATH_FORM_DIFFERENCE`，不提升为 stale；
- Projection schema/extractor version 变化 → rebuild required。

**Atomic write：**

- 在目标目录创建临时文件；
- `os.replace(temp, target)` 替换；
- 失败时删除临时文件并保留旧 Projection；
- 不宣称跨多个 Feature 文件的全局事务原子性；每个 Projection 文件独立原子替换。

### 7.7 CLI / API plan

Batch A 计划提供最小入口：

```text
python .ai/tools/feature_registry/feature_evidence.py --feature health
python .ai/tools/feature_registry/feature_evidence.py --pilot
python .ai/tools/feature_registry/feature_evidence.py --all
python .ai/tools/feature_registry/feature_evidence.py --check-stale
```

`--out` 默认：

```text
.ai/learning/feature_evidence/
```

测试必须显式传入临时输出目录。

### 7.8 Status semantics

Projection overall status：

- `COMPLETE`：metadata/index/graph 可读且一致，适用的 source evidence 完整，无冲突；
- `PARTIAL`：存在缺失、partial、ambiguous 或不适用但已明确记录的 evidence；
- `MISSING`：Feature identity / metadata 缺失，无法形成可追溯 Projection；
- `UNSUPPORTED`：存在无法解析的源类型或现有 Parser 不支持的必要输入；
- `CONFLICTED`：metadata、Index、Graph、source analysis 之间存在实质冲突。

`blackboard` 这类没有 behavior contract 的 Feature 不伪造 behavior evidence；其 Projection 应为 `PARTIAL` 或明确 `NOT_APPLICABLE`，不得写成 `COMPLETE` 的“已验证行为”。

---

## 8. Batch A Pilot Selection

从当前 31 个 Feature 中预选 5 个，覆盖不同证据形态：

| Feature | 选择理由 | 当前证据 |
|---|---|---|
| `health` | 完整 metadata、Capability、5 个 behavior source analysis | 5 × PARTIAL；6 methods；Node |
| `health_bar` | 有明确依赖 `health_state` | 5 × PARTIAL；requires `health_state`；Node |
| `openable_door` | 有 `COMPLETE` source analysis | 1 × COMPLETE；Node + Collision |
| `attack_emitter` | 有 `SOURCE_ENTRY_AMBIGUOUS` | 2 × SOURCE_ENTRY_AMBIGUOUS；Node |
| `blackboard` | 无 behavior contract、无 source analysis、Graph 孤立节点 | 0 behavior；0 source analysis；7 methods；0 Capability |

Pilot 预期：

```text
Projection count:       5
Source-analysis records: 13
COMPLETE:               1（openable_door，若其余 evidence 无冲突）
PARTIAL:                4（health / health_bar / attack_emitter / blackboard）
MISSING:                0（不存在 metadata 缺失的真实 Feature）
UNSUPPORTED:            0
CONFLICTED:             0（预计；发现冲突则必须记录）
Stale:                  0
```

`MISSING` / `UNSUPPORTED` 的真实分支由 Batch A 临时 fixture 测试覆盖，不通过修改正式 Feature 制造。

---

## 9. Batch A Test Plan

新增测试至少覆盖：

1. 完整 Feature metadata。
2. 缺失 summary。
3. 缺失 capability。
4. metadata / Index 之间的实质冲突。
5. 缺失 source analysis。
6. `PARTIAL` source analysis。
7. 不完整 interface evidence。
8. Feature dependencies / graph edges。
9. Graph inconsistency。
10. 源文件变化导致 stale。
11. schema version 变化导致 rebuild。
12. 构建失败时旧 Projection 保留。
13. 不修改原始 `feature.yaml`。
14. 不修改 `feature_index.json`。
15. 不修改 `feature_graph.json`。

计划命令（Batch A 实施后执行，不在本 Preflight 执行）：

```bash
python .ai/tools/feature_registry/tests/test_feature_evidence_projection.py
python .ai/tools/feature_registry/tests/test_feature_pipeline.py
python .ai/tools/validator/check_feature_metadata.py
```

测试约束：

- fixture 使用临时目录；
- 不修改正式 31 个 Feature；
- 不写正式 `feature_index.json` / `feature_graph.json`；
- 不启动 Godot；
- 不运行 Source Analysis 写入口；
- 不运行 External Analysis 写入口。

---

## 10. Batch A Risks / Known Limitations

| Risk | Impact | Mitigation |
|---|---|---|
| Feature Index absolute test paths | Projection portability / false conflict | Normalize and record `PATH_FORM_DIFFERENCE`; do not rewrite Index |
| Feature Index is generated at old timestamp | Might look stale | Compare semantic content; only path-form difference currently found |
| 8 Features have no behavior contract | Missing behavior evidence is expected | Record `NOT_APPLICABLE` / `PARTIAL`, not failure |
| 50/60 source analyses are PARTIAL | Cannot claim full static behavior | Preserve status and unresolved questions |
| 5 source analyses are SOURCE_ENTRY_AMBIGUOUS | Entry mapping uncertainty | Preserve ambiguity; do not infer entry point |
| Source Analysis covers behavior, not semantic capability | Capability overclaim risk | Capability evidence remains `HUMAN_DECLARED` |
| `gd_parse` is regex-based | Symbol extraction partial | Mark extraction status; no AST claims |
| No Feature provenance in 20/31 metadata | Provenance evidence incomplete | `MISSING` / `UNSUPPORTED`; Batch B external provenance later |
| No test execution record | Cannot claim test pass | `PRESENT_NOT_RUN` / `NOT_RUN` |
| Projection adds untracked data | Git baseline changes | Expected new files only; no formal Registry writes |

---

## 11. Stop Conditions Review

No stop condition is currently triggered:

- Existing modules do not already implement Feature Evidence Projection.
- Feature metadata authority is clear: `feature.yaml` is Source of Truth; Index/Graph are derived.
- 60 source analyses are script/contract fresh.
- External identities and digests are consistent.
- Provenance is traceable for the 14 external records.
- Projection can write to a new derived directory only.
- Link/admission implementation is deferred.
- Batch A does not require semantic judgment.
- Tests can use temporary fixtures.
- No Scene Intent or Promote change is needed.

If Batch A finds a real source/metadata conflict, it must record `CONFLICTED` and stop rather than silently choosing a winner.

---

## 12. Preflight Verdict

```text
PHASE_1_73_PREFLIGHT_VERDICT: PASS

Batch A approved to start only after explicit user approval.
Batch A scope: Feature Evidence Projection only.
Batch B/C/D remain blocked until Batch A acceptance.
```

**当前不执行 Batch A。**

等待用户明确批准后，才允许创建 `feature_evidence.py`、输出 Projection 和 Batch A 测试。
