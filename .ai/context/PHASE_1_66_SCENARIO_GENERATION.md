# Phase 1.66 — Scenario Generation

## 1. 输入（全部真实磁盘数据）

- `.ai/tools/learning/paths.py` 动态支持集（不写死 60 / 名单）。
- 正式契约：`fbe.build_contracts(feature, "Features")`。
- 源码分析：`.ai/learning/source_analysis/<feature>/<behavior>.json` 衍生知识。
- 依赖图：`.ai/learning/behavior_dependency_graph.json`（60 节点 / 118 边）。
- 知识库：`.ai/knowledge/behavior_learning/**`，只接受 `APPROVED` 记录。
- 学习任务：`.ai/learning/learning_plan.json` 的目标 Behavior。

## 2. 生成规则（知识事实匹配器 + 契约参数化模板）

代码中没有任何 Behavior 名；每条规则只在**知识事实满足**时触发，并从契约取动作/目标。

| rule_id | 触发知识事实 | 场景类型 | 观测重点 |
| --- | --- | --- | --- |
| `idempotent_repeat` | `SOURCE_OBSERVATION:guards` 含已置位守卫 | GUARD_IDEMPOTENCE | 重复触发不得产生额外信号 |
| `foreign_group_ignored` | 守卫依赖 `group`/成员判定 | GUARD_MEMBERSHIP | 外来组接触不推进状态 |
| `invalid_slot_rejected` | 守卫含输入/槽位校验 | GUARD_INPUT_VALIDATION | 非法输入不写入持久化状态 |
| `post_terminal_input_ignored` | 守卫含终态判断 | GUARD_TERMINAL_STATE | 终态后输入不再改变状态 |
| `dependency_postcondition_after_death` | 依赖图存在 upstream→downstream 边 | DEPENDENCY_PRECONDITION | 上游前置结束后下游后置成立 |

## 3. 生成的 5 个场景（全部 VALID）

| scenario_id | Behavior | 规则 | 动作 | 期望 | 知识引用 | 来源/依赖引用 |
| --- | --- | --- | --- | --- | --- | --- |
| `s-16f6576c8683f7bc` | openable_door/open | idempotent_repeat | 2 | 2 | 1 | 1 / 0 |
| `s-37cd4dc9f084950e` | trigger_switch/latch_once | foreign_group_ignored | 4 | 2 | 1 | 1 / 0 |
| `s-7771e41885fcd58e` | health/damage | post_terminal_input_ignored | 3 | 4 | 1 | 1 / 0 |
| `s-8b9f108ecb56beb2` | save_game/save_slot_persists_world_state | invalid_slot_rejected | 2 | 3 | 1 | 1 / 0 |
| `s-e6eb3fc5c8e82e32` | i_frames/iframes_expire_and_damage_resumes | dependency_postcondition_after_death | 4 | 4 | 1 | 1 / 1 |

覆盖 4 个行为类别：状态转换（door/health/trigger）、事件传播（i_frames）、持久化（save_game）。

## 4. 场景 Schema（与项目现状一致，未另造）

```json
{
  "scenario_id": "s-<sha256 16>",
  "feature_id": "...", "behavior_id": "...", "behavior_category": "A|B|C|D",
  "scenario_type": "GUARD_*|DEPENDENCY_*",
  "rule_id": "...",
  "title": "...", "derivation": "为什么这条知识能推出该场景",
  "knowledge_refs": ["k-..."],
  "contract_version": "<real>",
  "source_refs": [{"file": "Features/..."}],
  "dependency_refs": [{"upstream": "...", "downstream": "..."}],
  "preconditions": [...], "actions": [{"type": "...", ...}],
  "expected_observations": [{"check": "...", "target": "...", "...": "..."}],
  "cleanup": [...], "environment_requirements": [...],
  "execution_status": "NOT_EXECUTED", "validation_status": "PENDING"
}
```

动作/期望使用 1.41 行为协议词汇（`physics.overlap`、`simulation.advance_frames`、
`signal`、`health.current` 等），因此可直接交给现有采集器，不需要第二套 Runner。

## 5. ID 与幂等

- `scenario_id = "s-" + sha256(feature|behavior|rule|actions|expected)[:16]`；
  同一知识与同一模板重跑得到同一 ID（测试 G3/G4/G16）。
- `--prune` 只删除“不再被任何已审批知识支持”的场景文件与索引项，不动其他阶段产物。

## 6. 边界

Generator 只写 `.ai/learning/scenarios*`。不改源码、契约、Binding、基线、Golden Trace，
不批准知识，也不执行场景。

## 7. 已知限制（不得当成已完成）

1. 失败驱动与变异驱动场景模板尚未实装：当前唯一 `MUTATION_OBSERVATION` 为
   `PENDING_REVIEW`（入库门禁要求已审批知识才驱动生成），因此本阶段没有 mutation-driven 场景。
2. 规则族只覆盖“守卫/依赖前置”两类事实；无守卫事实的 Behavior 不会生成场景（宁缺勿造）。
3. 契约参数化依赖现有契约词汇；新增动作类型会被 Validator 拒绝（V15）。
