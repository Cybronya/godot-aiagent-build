# Learning Engine（Phase 1.66）

行为学习链：**源码/契约 → 分析 → 依赖 → 知识 → 计划**。只读产品代码，写入只发生在
`.ai/learning/**` 与 `.ai/knowledge/behavior_learning/**`。

```text
source_analysis.py → .ai/learning/source_analysis/<f>/<b>.json
dependencies.py    → .ai/learning/behavior_dependency_graph.json
extract.py         → 候选知识（PENDING_REVIEW）
knowledge_v2.py    → 审批 / 冲突 / 版本 / 撤销
planner.py         → .ai/learning/learning_plan.json + .md
pilot.py           → 端到端闭环 + 两轮计划 diff

# Phase 1.66：知识 → 真实测试 → 证据 → 知识回流
scenario_generator.py → .ai/learning/scenarios.json + scenarios/<id>.json
scenario_validate.py  → .ai/learning/scenario_validation.json（7 状态）
scenario_run.py       → Execution Plan + 真实 Godot 执行 + 四层结果
result_analysis.py    → .ai/learning/result_analysis.json（9 分类）
feedback.py           → 候选知识（SCENARIO/EXECUTION/BEHAVIOR/TEST_DESIGN）
mutation_candidates.py→ 已审批守卫知识 → 1.59 harness（只认 MUTANT_KILLED）
```

## 常用命令

```bash
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

# 1) 分析全部 60 个正式 Behavior（动态支持集）
python .ai/tools/learning/source_analysis.py --all
python .ai/tools/learning/source_analysis.py --feature openable_door --behavior open

# 2) 依赖图 + 查询
python .ai/tools/learning/dependencies.py --build
python .ai/tools/learning/dependencies.py --query downstream --behavior i_frames/iframes_block_damage_within_window
python .ai/tools/learning/dependencies.py --query upstream --behavior health/damage

# 3) 抽知识（matrix 必须显式给，禁止默认扫描）
python .ai/tools/learning/extract.py \
  --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
  --behaviors openable_door/open,i_frames/iframes_expire_and_damage_resumes

# 4) 计划
python .ai/tools/learning/planner.py \
  --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
  --label phase_1_65 --out .ai/learning/learning_plan.json

# 5) Pilot（不给 sandbox 就写正式知识库；给 sandbox 就是可重复演示）
python .ai/tools/learning/pilot.py \
  --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
  --behaviors openable_door/open,i_frames/iframes_expire_and_damage_resumes,\
save_game/save_slot_persists_world_state,trigger_switch/latch_once,health/damage \
  --sandbox-dir .ai/tmp/p165/pilot_sandbox

# 6) Phase 1.66：生成 → 验证 → 真实执行 → 分析 → 回流 → 计划
python .ai/tools/learning/scenario_generator.py --behaviors openable_door/open,health/damage --prune
python .ai/tools/learning/scenario_validate.py --all --write
python .ai/tools/learning/scenario_run.py --all --label P4      # 每个场景真实启动 Godot
python .ai/tools/learning/result_analysis.py --all
python .ai/tools/learning/feedback.py --all --review            # 显式本地审批
python .ai/tools/learning/planner.py \
  --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
  --label p166_after_feedback --out .ai/learning/learning_plan.json

# 7) 知识驱动的 Mutation（隔离副本 + Control/Mutation/Recovery）
python .ai/tools/learning/mutation_candidates.py --generate
python .ai/tools/learning/mutation_candidates.py --execute mc-55bda008e9123f41
```

`scenario_run` 只在**批次开始**时清理本批次自己的 evidence 目录；单场景运行与被拒绝的
运行绝不清理（早期实现曾因此误删真实证据，已修复）。

## 知识 Schema（v1）

文件：`.ai/knowledge/behavior_learning/{candidates,records,conflicts}/<id>.json`

```json
{
  "knowledge_id": "k-<16 hex>",
  "feature_id": "openable_door",
  "behavior_id": "open",
  "behavior_category": "A",
  "knowledge_type": "SOURCE_OBSERVATION",
  "key": "entry_points",
  "content": {"entry_points": ["..."], "static_only": true},
  "content_digest": "<sha256 of canonical content>",
  "source_references": [
    {"kind": "SOURCE_REFERENCE",
     "reference": "Features/openable_door/openable_door.gd:32#func=set_open",
     "digest": "<sha256 of file>"}
  ],
  "contract_version": "0550357495e5",
  "implementation_digest": "<sha256 concatenation>",
  "evidence_digest": "", "run_id": "",
  "confidence": "HIGH",
  "verification_status": "APPROVED",
  "supersedes": "", "superseded_by": "",
  "derivations": [],
  "review": {"reviewer": "...", "reason": "...", "at": "...", "scope": "LOCAL_REVIEW"},
  "lifecycle_events": [{"at": "...", "event": "CREATE"}, {"at": "...", "event": "APPROVE"}]
}
```

类型与门禁（代码强制）：

| 类型 | 必需来源 | 规则 |
| --- | --- | --- |
| CONTRACT_FACT | CONTRACT_REFERENCE | 必须 `Features/` |
| SOURCE_OBSERVATION | SOURCE_REFERENCE | 文件存在；digest 必须匹配当前文件 |
| TEST_OBSERVATION | EVIDENCE_REFERENCE | 必须 `run_id` |
| RUNTIME_OBSERVATION | ATTESTATION_REFERENCE | 必须 `run_id` |
| MUTATION_OBSERVATION | MUTATION_REFERENCE | 只接受 `MUTANT_KILLED` |
| FAILURE_KNOWLEDGE | MUTATION/TEST/EVIDENCE | 必须可追溯 |
| DEPENDENCY_KNOWLEDGE | SOURCE/CONTRACT | — |
| INFERENCE | derivations | 不能 `VERIFIED`；derivation 必须存在 |
| UNKNOWN | — | 必须 `reason` |
| SCENARIO_OBSERVATION | EVIDENCE_REFERENCE | 声称已执行时必须有真实 Evidence + `run_id` |
| EXECUTION_OBSERVATION | ATTESTATION_REFERENCE | 必须 `run_id`（+ Evidence） |
| BEHAVIOR_OBSERVATION | EVIDENCE_REFERENCE | 必须 `run_id` |
| TEST_DESIGN_KNOWLEDGE | — | 仅来自 `TEST_DESIGN_ERROR` |

状态：`PENDING_REVIEW → APPROVED → SUPERSEDED / REVOKED / ARCHIVED`。旧记录永不删除；
冲突双方都保留；冲突未解决时拒绝审批。

## 事实边界

- `SOURCE_OBSERVATION` 是静态事实（`static_only=true`），不是运行结果。
- 没有 evidence → 不写 `TEST_OBSERVATION`；没有 attestation → 不写 `RUNTIME_OBSERVATION`；
  没有 KILLED → 不写 `MUTATION_OBSERVATION`。
- `confidence` 是知识可信度，不代表 Behavior 覆盖状态；`Fully Covered` 仍由 1.64 八维定义。
- 本地审批（`LOCAL_REVIEW`）≠ 人类审批者身份已验证。

## 测试

```bash
python .ai/tools/learning/tests/test_source_analysis.py    # 17
python .ai/tools/learning/tests/test_dependency_graph.py   # 16
python .ai/tools/learning/tests/test_knowledge_store.py    # 20
python .ai/tools/learning/tests/test_planner.py            # 16

# Phase 1.66
python .ai/tools/learning/tests/test_scenario_generator.py   # 16
python .ai/tools/learning/tests/test_scenario_validator.py   # 18
python .ai/tools/learning/tests/test_scenario_run.py         # 12
python .ai/tools/learning/tests/test_result_analysis.py      # 14
python .ai/tools/learning/tests/test_feedback.py             # 13
python .ai/tools/learning/tests/test_mutation_candidates.py  # 16
```

## 生命周期

`PENDING_REVIEW → APPROVED → SUPERSEDED / REVOKED / ARCHIVED`。
已归档的同内容记录被再次观察时用 `revive()` 重开（`ARCHIVE → REOPEN`，证据更换时
`REFRESH_REFERENCES`），仍需显式审批；历史事件不删除。
