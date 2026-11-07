# Phase 1.66 — Knowledge Feedback

## 1. 新增知识类型（复用 1.64 Schema）

| 类型 | 必需来源 | 说明 |
| --- | --- | --- |
| `SCENARIO_OBSERVATION` | 已执行场景必须有 `EVIDENCE_REFERENCE` + `run_id` | 场景级观测与分类 |
| `EXECUTION_OBSERVATION` | `ATTESTATION_REFERENCE` + `run_id`（+ Evidence） | 一次真实执行的执行事实 |
| `BEHAVIOR_OBSERVATION` | Evidence + `run_id` | 行为结论（分类/理由） |
| `TEST_DESIGN_KNOWLEDGE` | 仅 `TEST_DESIGN_ERROR` 时生成 | 测试设计错误记录 |

未新增 `FAILURE_KNOWLEDGE`（本阶段无 FAILED 场景）。

## 2. 入库门禁（代码强制）

1. 声称已执行 → 必须有真实 Evidence 工件；只有 Attestation 不够（F7）。
2. `EXECUTION_OBSERVATION` 必须有 Attestation（F6）。
3. 引用文件必须存在且 digest 匹配（1.64 校验 + 本阶段 isfile 前置）。
4. 自动候选一律 `PENDING_REVIEW`（F2）；只有显式 `--review` 才 APPROVED（F8/F9）。
5. 重复写入幂等（F10）；同槽不同结论建 OPEN 冲突、双方保留（F11）。
6. 已归档的同内容记录被再次观察 → `revive()`：`ARCHIVE → REOPEN`，证据更换时记录
   `REFRESH_REFERENCES`，仍需显式审批（F13）。

## 3. 运行结果

```text
candidates=15  written=15  rejected=0  reviewed=5 (本轮新增审批；其余 10 条前序已审)
```

15 条 = 5 × `SCENARIO_OBSERVATION` + 5 × `EXECUTION_OBSERVATION` + 5 × `BEHAVIOR_OBSERVATION`。
`final 状态：15/15 APPROVED`（reviewer=`phase_1_66_local_review`，scope=`LOCAL_REVIEW`）。

知识库当前：

```json
{"records": 71, "by_type": {"SCENARIO_OBSERVATION": 10, "EXECUTION_OBSERVATION": 10,
 "BEHAVIOR_OBSERVATION": 5, "SOURCE_OBSERVATION": 17, "DEPENDENCY_KNOWLEDGE": 8,
 "CONTRACT_FACT": 5, "TEST_OBSERVATION": 4, "RUNTIME_OBSERVATION": 4,
 "MUTATION_OBSERVATION": 6, "FAILURE_KNOWLEDGE": 2},
 "by_status": {"APPROVED": 55, "SUPERSEDED": 5, "ARCHIVED": 10, "PENDING_REVIEW": 1},
 "conflicts_open": 0}
```

- 10 条 `ARCHIVED` = 5 条 P3 记录（因证据被误删而退役）+ 5 条更早同内容版本。
- 5 条 `SUPERSEDED` = 1.65 阶段被新版本替代。
- 1 条 `PENDING_REVIEW` = 本阶段 Mutation 知识（等待人工审核）。

## 4. 发现并修复的缺陷

| 缺陷 | 现象 | 修复 |
| --- | --- | --- |
| 证据被测试误删 | P3 的 5 个 bundle 消失，回流全部被拒 | 批次级清理 + archive 退役 + P4 重跑 |
| 归档记录冒充写入 | 同内容命中 ARCHIVED，`written` 却报告成功 | `revive()` 重开（F13） |
| 复活后引用过期 | 复活记录仍指向已删除 bundle，审批被拒 | `revive(source_references=...)` 刷新并留痕 |

## 5. 第二轮 Planner 影响（真实数据驱动）

| 指标 | 1.65 结束时 | 本阶段后 |
| --- | --- | --- |
| 任务总数 | 277 | 276 |
| `DESIGN_TEST_SCENARIO` | 48 | 47 |
| `scenario_evidenced_behaviors` | 0 | 5 |
| `driven_by_knowledge` 非空任务 | 1 | 0 |

- 减少的 1 个任务是 `T-TRIGGER_SW-LATCH_ONCE-DESIGNTEST`（`NO_TEST_SCENARIO`），
  由 P4 真实执行证据消解；不是手改任务文件。
- `driven_by_knowledge` 变 0 的诚实解释：唯一带该字段的任务正是被移除的那条；剩余 47 条
  设计任务所属 Behavior 尚无守卫/依赖知识可引用。机制仍在（`test_planner.P9b` 在
  “无执行结果”输入下验证引用会出现），但本阶段**没有**新的知识引用型任务。
