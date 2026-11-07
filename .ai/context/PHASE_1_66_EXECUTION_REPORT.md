# Phase 1.66 — 真实执行报告（label `P4`）

## 1. 执行环境

| 项 | 值 |
| --- | --- |
| 引擎 | Godot 4.7-stable（console 版，路径来自 `env_paths.require_godot`） |
| 数据采集 | `scene_composer/feature_behavior_evidence.py`（真实启动 Godot、加载项目、跑 fixture） |
| 验证/评估 | `evaluation/evidence_eval.py`（1.57/1.58） |
| Attestation | 1.62 `execution_attestation`（LOCAL_ISOLATED） |
| 隔离 | `.ai/tmp/p166/{runs,evidence,evaluation,results}`；每 Run 独立目录 + `user://` 标签 |
| 时间 | 2026-11-07，单场景 11.6–12.5s（含 workspace import） |

## 2. Execution Plan 字段（每场景一份）

`execution_plan_id`、`scenario_id`、`feature_id`、`behavior_id`、`run_id`、
`environment_fingerprint`、`source_fingerprint`、`collector_fingerprint`、
`execution_config_fingerprint`、`output_root`、`prerequisites`、`timeout_policy`、
`cleanup_policy`。四指纹均来自真实文件/环境，测试 R3/R4/R5/R7 校验非空与隔离范围。

## 3. 真实执行结果（5/5）

| scenario | Behavior | Execution | Evidence | Attestation | Evaluation | 时长 | 官方契约 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `s-16f6576c8683f7bc` | openable_door/open | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | 11.8s | PASS |
| `s-37cd4dc9f084950e` | trigger_switch/latch_once | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | 12.5s | FAIL |
| `s-7771e41885fcd58e` | health/damage | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | 11.6s | INCOMPLETE |
| `s-8b9f108ecb56beb2` | save_game/save_slot_persists_world_state | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | 11.8s | FAIL |
| `s-e6eb3fc5c8e82e32` | i_frames/iframes_expire_and_damage_resumes | PASSED | EVIDENCE_VERIFIED | ATTESTED_VERIFIED | VERIFIED_PASS | 12.2s | INCOMPLETE |

Run ID / Evidence Bundle：

```text
cbb98cef-…  .ai/tmp/p166/evidence/5428-3ce13e58-bundle.json
a39a4ce5-…  .ai/tmp/p166/evidence/5428-e7f2ec3f-bundle.json
07abd604-…  .ai/tmp/p166/evidence/5428-3f4723e0-bundle.json
083e4b6b-…  .ai/tmp/p166/evidence/5428-ac7ca98f-bundle.json
b2bf66a0-…  .ai/tmp/p166/evidence/5428-cc9e82ad-bundle.json
```

## 4. 执行安全核对

- 产品源码未修改：执行前后 `Features/**` 未变（mutation 侧另有 265 文件 repo_guard 快照）。
- 正式契约/Binding/基线未修改。
- 未删除历史 Evidence；本阶段新增目录全部位于 `.ai/tmp/p166/**`。
- 每个 Run ID 唯一；输出目录互不覆盖；失败场景也不会被后续运行“顺手清空”。

### 本阶段发现并修复的真实缺陷（重要）

`scenario_run._prepare_dirs()` 原来对**任何**调用都清理 evidence 目录。一次“被拒绝场景”的
单元测试（R10）因此删除了 P3 的 5 个真实 Evidence Bundle，导致回流门禁正确拒绝了 15 条候选
（`evidence artifact missing`）。

修复：
1. 清理只发生在批次开始（`run_batch → _prepare_dirs(label, clean=True)`）；
2. 单场景/被拒绝运行永不清理；
3. 受影响记录用 `archive()` 正常退役（不删除历史），随后 P4 重跑重建证据并重新生成候选；
4. 回归用例 R10/R11 保留，并新增 `test_feedback.F13` 与 `test_mutation_candidates` 覆盖生命周期。

## 5. 官方契约差异（双结论，必须分开看）

| 场景 | 官方契约结论 | 原因 |
| --- | --- | --- |
| door/open | PASS | 期望条目与契约一致 |
| trigger_switch/latch_once | FAIL | 扩展场景观测 4 项检查，契约声明 2 项（数量不同 → 官方判定 FAIL） |
| health/damage | INCOMPLETE | 契约缺少扩展场景所需的终态后输入条目，无法逐条对齐 |
| save_game/save_slot | FAIL | 同上：扩展了非法槽位观测 |
| i_frames/... | INCOMPLETE | 依赖前置观测超出契约声明 |

这些差异是“扩展场景 vs 正式契约”的设计差，不是行为缺陷；`scenario_results.json` 单独保存
`official_contract_status` 与 `official_contract_detail`，不并入 Evaluation PASS。

## 6. 未执行 / 阻塞

- `blocked=0`：5 个场景全部真实执行。
- 未执行：其他 52 个 Behavior（本阶段不追求全覆盖）。
- 未重跑 1.64 全量入口（见 COMPLETION §技术债）。
