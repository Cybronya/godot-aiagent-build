# Phase 1.65 完成报告 — Behavior Learning & Knowledge Expansion

完成时间：2026-11-06。分支 `master`，HEAD `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（**未提交**）。
未执行任何 Git 写操作。

配套文档：`PHASE_1_65_AUDIT.md`、`_ARCHITECTURE.md`、`_SOURCE_ANALYSIS.md`、`_DEPENDENCY_REPORT.md`、
`_KNOWLEDGE_REPORT.md`、`_LEARNING_PLAN.md`、`_LEARNING_PILOT.md`、`_ATTACK_TESTS.md`（本文件为第 9 份）。

---

## 1. 仓库状态

| 项 | 值 |
| --- | --- |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8`（与审计一致，未变） |
| 分支 | `master` |
| 已跟踪修改 | 20（**全部来自其他 Agent**：skills 清理、feature.yaml、project.godot、evaluation/runner.py 等；本阶段未修改任何既有文件） |
| 已跟踪删除 | 33（其他 Agent 的 `.ai/skills/.../gut__*.gd` 清理；未还原） |
| 未跟踪 | 971 → 981（+10 顶层条目，全部是本阶段产物） |
| 暂存区 | 0 |
| 新增文件 | `.ai/tools/learning/{paths,gd_parse,source_analysis,dependencies,knowledge_v2,extract,planner,pilot}.py`（2816 行）+ `tests/` 4 套、`.ai/context/PHASE_1_65_*.md` 9 份、`.ai/learning/**`、`.ai/knowledge/behavior_learning/**`（45 条 + 5 冲突）、`.ai/tmp/p165/**` |
| 修改文件 | 无（本阶段只新增；`CURRENT_TASK.md` / `WORK_STATE.md` / README 的更新见 §9） |
| 删除文件 | 无 |
| Git 写操作 | **无** |

## 2. 架构审计结论（详见 `_AUDIT.md`）

- 项目里只有**一个** Knowledge Store（1.64 的 `behavior_verification/store.py`），没有第二个知识库、
  没有 Learning Planner、没有 Knowledge Graph。
- 复用：来源类型语义、历史不覆盖、契约版本规则（`binding_candidates.contract_digest`）、
  覆盖矩阵、Provenance/Attestation、`env_paths` 环境探测。
- 新增：按类型的记录层 + 审批/冲突/版本/撤销（`knowledge_v2.py`）、源码分析、依赖图、Planner、Pilot。
- 为什么不是重建：1.64 的存储已把"来源+历史"做对，缺的是记录粒度与生命周期；新增记录层风险更小，
  且 7 条旧记录保持原样，无迁移、无覆盖。
- 遗留技术债：**P2 评估归因**（矩阵默认扫描）在 Planner/Extractor 侧做了显式校验（必需 matrix 参数 +
  bundle digest 归属检查），未改 1.63 矩阵实现；`i_frames.gd:78` 缩进未修（登记）；全量入口未重跑（登记）。

## 3. Source Analysis

| 指标 | 值 |
| --- | --- |
| 分析 Behavior | **60 / 60** |
| 找到确认入口 | **57** |
| `COMPLETE` | 5 |
| `PARTIAL` | 50 |
| `SOURCE_ENTRY_AMBIGUOUS` | 5（`attack_emitter` ×2 双定义、`condition_gate` ×3 组合场景） |
| `SOURCE_NOT_FOUND` | 0 |
| 未解决问题条目 | 见每份 JSON 的 `unresolved_questions`（契约/源码命名不一致、harness 驱动方法、动态调用） |

事实边界：全部 `static_only=true`；没有把"源码里有 emit"写成"运行时发射成功"。

## 4. Dependency Analysis

| 指标 | 值 |
| --- | --- |
| 节点 | 60 |
| 边 | **118**（97 `SOURCE_OBSERVED` + 21 `CONTRACT_DERIVED`） |
| 依赖类型 | EMITS 21、RECEIVES 21、REQUIRES_PRECONDITION 21、SHARES_STATE 50、WRITES_STATE 3、PERSISTS 1、RESTORES 1、CALLS 0、USES_RESOURCE 0 |
| 有出边的 Behavior | 41 |
| 循环/SCC | 2：`hub_component`（Health 生态 17 节点 / 62 边，note）、`persistence_pair`（save↔load，expected） |
| 未解析契约依赖 | 1（`heal_pickup.requires=health_state`，源码无可归属出边） |

每条边都有 `source_reference`；契约推导与源码确认严格分离（测试 D6 强制）。

## 5. Knowledge

| 指标 | 值 |
| --- | --- |
| 原有（1.64） | 7 条（未改动） |
| 新增记录 | **45**（40 `APPROVED` + 5 `SUPERSEDED`） |
| 待审核 | 0（全部经门禁审批后入库） |
| 冲突 | 5（全部 `RESOLVED`，双方记录保留） |
| 撤销 | 0 |
| 来源分布 | CONTRACT_FACT 5、SOURCE_OBSERVATION 17、DEPENDENCY_KNOWLEDGE 8、MUTATION_OBSERVATION 5、TEST_OBSERVATION 4、RUNTIME_OBSERVATION 4、FAILURE_KNOWLEDGE 2 |
| 覆盖 Behavior | 5 / 60 |
| 置信度 | VERIFIED 5、HIGH 27、MEDIUM 13 |

## 6. Learning Planner

| 指标 | 值（当前正式库） |
| --- | --- |
| 任务数 | **277** |
| 覆盖 Behavior | 57 / 60 |
| 阻塞 | 0 |
| 因已完成排除 | 10 |
| 类型分布 | ANALYZE_SOURCE 60、UPDATE_KNOWLEDGE 55、DESIGN_MUTATION 50、EXECUTE_BEHAVIOR 48、DESIGN_TEST_SCENARIO 48、ANALYZE_DEPENDENCIES 16 |
| 最高优先级 | `health/post_death_guard` ANALYZE_DEPENDENCIES / ANALYZE_SOURCE = **18.5**（风险 15 + 上游 6） |

知识更新前后（隔离根，可重复）：任务 **287 → 277**，`excluded_completed` 0 → 10，5/5 Pilot Behavior 的任务集合变化。

## 7. Learning Pilot（5 个 Behavior / 3 类）

| Behavior | 类型 | Run ID | Signature | Attestation | Evaluation | Mutation | Knowledge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `openable_door/open` | A | `11964-ad881e33-open` | VERIFIED | VERIFIED | VERIFIED_PASS | M12 KILLED | 7 |
| `i_frames/iframes_expire_and_damage_resumes` | A | `11964-79c99c5e-…` | VERIFIED | VERIFIED | VERIFIED_PASS | M11 KILLED | 8 |
| `save_game/save_slot_persists_world_state` | C | `11964-26505382-…` | VERIFIED | VERIFIED | VERIFIED_PASS | M06 KILLED | 10 |
| `trigger_switch/latch_once` | F | **无** | NO_SIGNATURE | NO_ATTESTATION | NOT_EVALUATED | M08 KILLED | 7 |
| `health/damage` | A | `11984-263d1383-damage` | VERIFIED | VERIFIED | VERIFIED_PASS | M01 KILLED | 8 |

- 第二轮计划变化：见 `_LEARNING_PILOT.md` §3（代码读库产出，非手改）。
- 候选场景 12 条，全部 `executed: false`；**本阶段没有新跑 Godot**，已执行结论只来自 1.64 真实产物。
- 审批 40 条（`LOCAL_REVIEW`），本地审批不等于人类身份验证。

## 8. 测试

| 类别 | 套件 | 结果 |
| --- | --- | --- |
| 新增 | source / dependency / knowledge / planner | **17 + 16 + 20 + 15 = 68 项，全 PASS** |
| 回归 | 1.64 knowledge、coverage matrix、binding candidates、env_paths | **18 + 15 + 26 + 18 = 77 项，全 PASS** |
| E2E | 无新增（复用 1.64 真实 Run 关联） | 未执行新采集 |
| 未执行 | `run_tests.py` 全量、Godot 新 Run、mutation 重跑 | 已登记，不算通过 |

唯一测试用例：**145**（68 新增 + 77 回归）。重复执行：新增 4 套在开发中多次重跑（≥3 次），回归各 1 次。

## 9. 未完成事项与风险

1. **60 条里只对 5 条建立了完整知识**；其余 55 条只有分析/依赖，没有入库知识。
2. **5 条入口歧义未解**（`attack_emitter` 双定义、`condition_gate` 组合场景）——需要场景级/跨 Feature 分析。
3. **`trigger_switch/latch_once` 仍无真实 Run**；知识里的 `MUTATION_OBSERVATION` 来自 1.64，没有 `TEST/RUNTIME`。
4. **候选场景没有执行**：12 条只是设计，不是已验证测试。
5. **1.64 技术债**：矩阵 P2 只做了周边校验（未改 1.63 实现）；`i_frames.gd:78` 缩进未修；
   全量入口 3 FAIL / 2 INCOMPLETE 未处理。
6. **本地审批**：reviewer 是脚本身份（`phase_1_65_local_review`），不构成人类审批；`LOCAL_ISOLATED` 边界仍在。
7. **依赖图静态**：动态调用、跨 Feature 静态类调用、场景组合依赖未覆盖。
8. **未提交**：所有产物在工作区，按任务书要求不做 Git 写操作。

## 10. 下一步建议

1. 按 `learning_plan.json` 前 10 条任务推进：先 `health/post_death_guard`（枢纽、风险最高），
   再补 `save_game/load_slot_restores_world_state` 与 `stun/hit_stuns_and_freezes_host`。
2. 执行候选场景（需要 Godot 采集预算），把 `DESIGN_TEST_SCENARIO` 变成真实 Evidence。
3. 解 5 条入口歧义：为 `attack_emitter` 明确运行时子类；为 `condition_gate` 引入场景级依赖分析。
4. 把 `FAILURE_KNOWLEDGE` 从"历史引用"升级为"可重跑复现"（关联 M04/M06 的重跑报告）。
5. 修 1.63 矩阵 P2（按 run/批次绑定评估报告），让 Planner 可以安全使用默认矩阵。
