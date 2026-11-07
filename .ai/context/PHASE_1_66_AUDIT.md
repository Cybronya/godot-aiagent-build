# Phase 1.66 审计报告 — Knowledge-Driven Test Generation & Execution

日期：2026-11-06。审计为只读：本阶段到此刻未修改任何文件。
HEAD `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`，分支 `master`。

## 1. 仓库状态（与磁盘对账）

| 项 | 实测值 | 说明 |
| --- | --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` | 与 1.65 完成时一致，未被改动 |
| 分支 | `master` | — |
| 已跟踪修改 | 20 | 均来自其他 Agent（skills 清理、`feature.yaml`、`project.godot`、`evaluation/runner.py` 等），非本阶段 |
| 已跟踪删除 | 33 | 其他 Agent 删除的 `.ai/skills/.../gut__*.gd` |
| 未跟踪 | 982 | 981（1.65 结束时）+ `learning/README.md` 之外为本次审计无新增 |
| 暂存区 | 0 | 无 `git add` |
| Godot | `F:\Godot_v4.7-stable\Godot_v4.7-stable_win64_console.exe` | `env_paths.require_godot()` 可解析（1.64 同一二进制，4.7-stable） |
| Python | 3.12.10 | `yaml` 可用；无新增依赖 |

## 2. Phase 1.65 实际交付（逐项核对磁盘）

| 交付 | 声称 | 实测 |
| --- | --- | --- |
| Source Analysis | 60/60 | `ls .ai/learning/source_analysis/*/*.json` = **60** |
| Dependency Graph | 60 节点 / 118 边 | JSON `summary.nodes=60, edges=118` |
| Knowledge Store | 45 条 | `knowledge_v2.summary()` = **45**（40 APPROVED + 5 SUPERSEDED），冲突 5 全 RESOLVED |
| Learning Plan | 277 任务 | JSON `summary.tasks=277`，`excluded_completed=10` |
| Pilot | 5 Behavior | `pilot_result.json` 5 条，4 有 run_id |
| 新增测试 | 68 | 四套件重跑：17/16/20/15 全 PASS |
| 回归 | 77 | 18/15/26/18 全 PASS |

## 3. 现有场景生成能力（1.65 的候选场景）

`.ai/learning/pilot/scenarios.json`：**12 条**，实际字段：

```json
{"behavior": "...", "kind": "guard_boundary|persistence_roundtrip",
 "guard": "if _is_open == value:", "source_reference": "Features/...gd:33",
 "proposed_action": "构造…", "derived_from": "SOURCE_OBSERVATION:guards",
 "executed": false, "existing_run_id": "...", "execution_note": "..."}
```

结论（缺口确认）：

1. **没有 `scenario_id`**，无法被引用、无法被结果反向绑定。
2. **没有可执行的动作/期望列表**：`proposed_action` 是自然语言，`guard` 是源码片段。
3. 没有 `contract_version`、`knowledge_refs`、`dependency_refs`、`environment_requirements`。
4. 没有 Validator、没有 Execution Planner、没有执行记录；`executed=false` 是唯一状态。
5. 生成规则是 `pilot._scenarios()` 内联的启发式（guard→"构造边界"），不是独立 Generator。

## 4. 现有测试执行能力（可直接复用）

| 能力 | 模块 | 结论 |
| --- | --- | --- |
| 契约构造 | `scene_composer/feature_behavior_evidence.build_contracts` | 从 `Features/*/template.yaml#behavior` 读取 actions/preconditions/expected，严格校验 |
| 隔离执行 | `feature_behavior_evidence.BehaviorWorkspace` | 临时复制 Features + 探针 + manifest，独立 `project.godot`，`use_custom_user_dir` 做 `user://` 隔离 |
| 真实执行 | `feature_behavior_evidence.verify_contract` | 启动真实 Godot `-s res://.ai/tools/scene_composer/probes/feature_behavior_probe.gd`，写 `result.json` |
| 判定 | `feature_behavior_evidence.judge` | 超时/无结果/动作未执行/无检查均不得 PASS |
| 证据 | `build_bundle` / `bundle_digest` / `write_bundle` | artifact digests 进 bundle |
| 签名 | `validator/provenance/{signing,verification}` | Ed25519，独立信任根（`PROVKEY-5aa9912c2dbb6587`） |
| 清单/Attestation | `validator/execution/{manifest,attestation,fingerprint,identity}` | 四类指纹 + `LOCAL_ISOLATED` |
| 评估 | `evaluation/evidence_eval.py --no-collect` | expect 来自 Binding（1.64）或调用方给出 |
| Mutation | `evaluation/mutation/{harness,workspace,operators,catalog}` | 隔离副本 + Control/Mutation/Recovery + 逐字节恢复 |

**实测冒烟（真实执行，只读产品源码）**：用 `verify_contract` 跑 `openable_door/open`，`replay=1`：

```
STATUS PASS  runs=1  checks=2 (door.is_open=true, door.state_changed count=1)
workspace import 12.9s，总耗时 13.2s
```

结论：**执行链可用**；单个场景预算 ≈ 13–16 s（workspace import 占大头），5 个场景 ≈ 1–2 分钟。

## 5. 现有协议能力（Generator 能表达什么）

`.ai/context/behavior_protocol.yaml`（v2）：**17 actions / 16 observations / 19 signals**。
`limits`: `max_total_frames=600`、`max_frames_per_action=300`、`max_fixture_actions=4`。

与本阶段相关的动作：`door.set_open`、`health.take_damage`、`health.heal`、`physics.overlap(group)`、
`simulation.advance_frames`、`state.set_property`、`savegame.save_slot(slot)`、`savegame.load_slot`。
观测：`door.is_open`、`health.current`、`health.is_dead`、`trigger.is_triggered`、`savegame.last_slot`、
`signal(entry,count,last_args)`。

重要：`probes/feature_behavior_probe.gd` 的 `physics_overlap` 会把 body 加入**任意** group，
因此「非 players 组不得触发」这类负向场景可以真实执行。

## 6. Knowledge 侧能力与缺口

- 记录字段：`knowledge_id / knowledge_type / key / content / source_references(digest) /
  contract_version / implementation_digest / evidence_digest / run_id / confidence /
  verification_status / lifecycle_events / conflict_ids`。
- 已有类型 9 种；**缺** `SCENARIO_OBSERVATION`、`EXECUTION_OBSERVATION`、`BEHAVIOR_OBSERVATION`、
  `TEST_DESIGN_KNOWLEDGE`。
- `staleness()` 已能检 contract_version / implementation_digest 变化。
- `add_candidate()` 已强制 `PENDING_REVIEW`、同槽冲突不覆盖；`approve()` 需 reviewer+reason。
  本阶段可直接复用，不新建 Store。

## 7. 当前缺口清单（本阶段要补的）

1. 无稳定 Scenario Schema / ID / 索引。
2. 无 Scenario Generator（知识 → 可执行 actions/expected）。
3. 无 Scenario Validator（7 种状态）。
4. 无 Execution Planner（指纹、唯一 Run ID、隔离输出根）。
5. 无「场景 → 真实执行 → Evidence → Attestation → Evaluation」的统一入口。
6. 无 Result Analyzer（9 类结论、失败分类）。
7. 无 Knowledge Feedback（新类型 + 候选区 + 审核 + 第二轮 Planner 输入）。
8. 无 Knowledge-Driven Mutation Candidate。
9. Planner 只读矩阵，不消费真实执行结果（`NO_TEST_SCENARIO` 无法被真实执行消解）。

## 8. Phase 1.64 技术债复现

| 债 | 复现结果 | 处置 |
| --- | --- | --- |
| #1 矩阵评估归因 P2 | `coverage_matrix.py:564` 仍是 `eval_dirs = args.eval_dir or [EVAL_REPORT_DIR]` | **不修**：改 1.63 评估语义会影响其他 Agent；Planner/本阶段始终显式传目录，已隔离 |
| #2 `i_frames.gd:78` 缩进 | 仍为 1 tab（`_active = false` 在 2-tab 的 `if` 体内） | **不修**：任务书 §1.13 禁止自动修改产品源码；仅登记 |
| #3 全量入口 FAIL/INCOMPLETE | 现存日志：`full_regression_133b.log` 失败于 `test_end_to_end_generation.py` 的 **ownership 拒绝删除**（其他 Agent 预先存在的 `Scenes/StageBoss.tscn` 等）；`full_regression_133c.log` 为 **83/83 ALL PASS** | 属于工作区所有权冲突，不是代码缺陷；本阶段不重跑 57 分钟全量，改为跑与本阶段相关的定向回归，并如实登记 |

## 9. 推荐实现方案

新增 `.ai/tools/learning/` 六个模块（复用现有链，不建平行 Runner）：

```text
scenario_rules.yaml       规则目录（数据，不含 Behavior 名）
scenario_generator.py     知识 + 契约 + 分析 + 依赖 → 场景（结构化、可执行）
scenario_validate.py      7 状态验证（contract/source/knowledge/dependency/feasibility/env）
scenario_run.py           Execution Plan + 真实执行 + Evidence/签名/Manifest/Attestation/Evaluation
result_analysis.py        9 类结论 + 失败分类（不猜根因）
feedback.py               新知识类型候选（PENDING_REVIEW）+ 显式审核 + 结果索引
mutation_candidates.py    知识驱动 Mutation Candidate（隔离执行留给 Harness 门禁）
```

Planner 扩展一个输入：`.ai/learning/scenario_results.json`（只认 VALID + 真实 PASS +
`ATTESTED_VERIFIED` + `VERIFIED_PASS` 的场景），用于消解 `NO_TEST_SCENARIO`。
这样「真实执行结果改变下一轮计划」由真实数据驱动，而不是手改任务文件。

产出目录（全部隔离，不覆盖 1.64/1.65 产物）：

```text
.ai/learning/scenarios/**            场景（未执行）
.ai/learning/scenario_results.json   执行结果索引（结果分析后的权威摘要）
.ai/learning/results/**              逐场景分析结论
.ai/tmp/p166/{evidence,runs,evaluation,workspaces}   真实执行产物
```
