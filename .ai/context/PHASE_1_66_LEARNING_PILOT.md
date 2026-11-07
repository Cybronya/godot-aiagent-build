# Phase 1.66 — Learning Pilot（5 个 Behavior 的端到端闭环）

## 1. 选择依据

来自当前磁盘状态（支持集 + 已审批知识 + 真实环境能力），不是照搬历史名单：

| Behavior | 类别 | 选择理由 |
| --- | --- | --- |
| `openable_door/open` | A 状态转换 | 有 `_open` 守卫知识 → 幂等场景 |
| `trigger_switch/latch_once` | A 状态转换 / 事件 | 有 `_triggered` 守卫 + 组过滤 → 外来组场景，且是 Mutation 锚点 |
| `save_game/save_slot_persists_world_state` | C 持久化 | 有槽位校验知识 → 非法槽位场景 |
| `health/damage` | A/F 终态 | 有终态守卫知识 → 终态后输入场景 |
| `i_frames/iframes_expire_and_damage_resumes` | B/D 依赖 | 依赖图存在 upstream→downstream 边 → 前置/后置场景 |

## 2. 每个 Behavior 的 13 步执行情况

| 步骤 | 结果 |
| --- | --- |
| 1 读 Knowledge | 5/5 有已审批来源知识 |
| 2 生成 Scenario | 5/5（4 条规则族） |
| 3 验证 Scenario | 5/5 VALID |
| 4 Execution Plan | 5/5，四指纹 + 唯一 Run ID + 隔离目录 |
| 5 真实执行 | 5/5 真实 Godot（11.6–12.5s/场景） |
| 6 Evidence | 5/5 `EVIDENCE_VERIFIED`，bundle 现存可校验 |
| 7 Validator | 5/5 PASS（Artifact Cross-Validation / digest / Run 绑定） |
| 8 Attestation | 5/5 `ATTESTED_VERIFIED`（`LOCAL_ISOLATED`） |
| 9 Evaluation | 5/5 `VERIFIED_PASS` |
| 10 Result Analysis | 1 CONTRACT_CONFIRMED / 3 SOURCE_CONFIRMED / 1 BEHAVIOR_CONFIRMED |
| 11 Candidate Knowledge | 15 条（场景/执行/行为各 5） |
| 12 审核状态 | 15/15 APPROVED（`phase_1_66_local_review`，LOCAL_REVIEW） |
| 13 更新 Learning Plan | 277 → 276，移除 `NO_TEST_SCENARIO` 设计任务 |

## 3. 端到端证据链（示例：`openable_door/open`）

```text
k-…（SOURCE_OBSERVATION:guards, APPROVED）
  → s-16f6576c8683f7bc（GUARD_IDEMPOTENCE, VALID）
  → run cbb98cef-…（plan.json，四指纹，隔离 user://）
  → .ai/tmp/p166/evidence/5428-3ce13e58-bundle.json（EVIDENCE_VERIFIED）
  → attestation.json + .sig.json（ATTESTED_VERIFIED, LOCAL_ISOLATED）
  → evaluation VERIFIED_PASS（官方契约 PASS）
  → CONTRACT_CONFIRMED
  → SCENARIO_OBSERVATION + EXECUTION_OBSERVATION + BEHAVIOR_OBSERVATION（APPROVED）
  → Planner：该 Behavior 不再生成 DESIGN_TEST_SCENARIO
```

## 4. 计划变化（真实数据驱动）

| 项 | before（`learning_plan_before_p166.json`） | after（`learning_plan.json`） |
| --- | --- | --- |
| tasks | 277 | 276 |
| DESIGN_TEST_SCENARIO | 48 | 47 |
| scenario_evidenced_behaviors | 0 | 5 |

唯一变化任务：`T-TRIGGER_SW-LATCH_ONCE-DESIGNTEST`（gap `NO_TEST_SCENARIO`）被移除，
因为 `scenario_results.json` 中该 Behavior 已有
`VALID + EVIDENCE_VERIFIED + ATTESTED_VERIFIED + VERIFIED_PASS` 的真实场景结果。

诚实说明：`driven_by_knowledge` 非空任务由 1 变 0——被移除的正是那一条；其余 47 条设计任务
所属 Behavior 目前没有可引用的守卫/依赖知识。机制仍可用（`test_planner.P9b`）。

## 5. 未完成 / 限制

- 52 个 Behavior 未进入本阶段（任务书允许 3–5 个）。
- 没有 FAILED 场景，因此没有 `FAILURE_KNOWLEDGE` / `INVESTIGATE_FAILURE` 任务变化。
- 全部证据为 `LOCAL_ISOLATED`；未部署独立可信执行环境，未升级信任级别。
- 自动知识已由本地 reviewer 审批（`LOCAL_REVIEW`），**不代表**人类审批者身份已验证。
