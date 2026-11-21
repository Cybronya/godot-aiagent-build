# Phase 1.59 — L5 Behavioral Mutation Testing 审计（实施前基线）

- 审计时间：2026-11-03
- 审计方式：只读检查（`git status` / 文件读取 / 模块导入 / 一次真实采集计时）。未修改任何仓库文件。
- 标签：**FACT** = 本次直接观测；**INFERENCE** = 由事实推断；**UNKNOWN** = 未能验证。

---

## 1. 仓库基线（FACT）

| 项 | 值 |
| --- | --- |
| 分支 | `master` |
| HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` |
| `git status --short` 行数 | 993 |
| 其中 `.ai/skills/**/code_library` | ≈ 950 条（他人并行产物，本阶段不触碰） |
| 已跟踪且有未提交修改（非 code_library） | `.ai/context/{CURRENT_TASK,FEATURE_BEHAVIOR_COVERAGE,WORK_STATE}.md`、`.ai/context/feature_{graph,index}.json`、`.ai/tools/evaluation/{README.md,runner.py}`、`.ai/tools/scene_composer/feature_behavior_evidence.py`、`.ai/tools/scene_composer/probes/feature_behavior_probe.gd`、`.ai/tools/validator/{README.md,validate.py}`、`Features/{attack_emitter,knockback,save_game,sfx_pool,state_machine}/feature.yaml`、`project.godot` |
| 未跟踪（本阶段之前已存在） | Phase 1.55–1.58 的审计/报告、Phase 1.56–1.58 新工具与测试、8 个未纳入正式支持集的 Feature 目录、E2E 孤儿场景/关卡 |

**风险判定**：工作区不干净属于常态，但 **没有** 任何迹象表明有正在运行、会写入仓库的任务
（未发现锁文件或活动进程；`.ai/tmp` 下最新产物是本次会话之前的 Phase 1.58 运行）。
判定为可以继续，条件是：本阶段所有写操作只发生在自己创建的 `.ai/tmp/p159/**` 与
本阶段新增的 `.ai/tools/evaluation/mutation/**` 内。

> 注意：`feature_behavior_evidence.py` 与 `probes/feature_behavior_probe.gd` 处于**已修改未提交**
> 状态。它们是本阶段的**只读依赖**（Harness 调用其 CLI，不修改它们）。若这两个文件在实施期间
> 被其他 Agent 改动，mutation 复跑结果可能变化——报告里记录其 SHA256 以便追溯。

## 2. 8 个未纳入支持集的 Feature（FACT）

`Features/{anima_behaviour, attribute_editor, audio_player_pool, blackboard, clean_copy,
flying_letter, pedestal_interaction, pickable_audio}` 为未跟踪目录。本阶段
**不把它们加入支持集**，也不对它们做 mutation。

正式支持集动态读取结果（FACT，本次运行）：**23 Feature / 60 Behavior**
（`feature_behavior_evidence.declared_features()` + `build_contracts()`，协议版本 2）。

---

## 3. 已有 L5 能力（FACT）

仓库已有**逐 Feature 的缺陷注入测试**，位置 `.ai/tools/scene_composer/tests/`：

| 文件 | 注入的缺陷（摘要） | 判定终点 |
| --- | --- | --- |
| `test_health_behavior.py` | 9 类（伤害钳制、heal 钳制、事件参数、死亡标记、死亡守卫等） | 采集器 `STATUS_MISMATCH` |
| `test_chase_movement_behavior.py` | 追击位移缺陷 | 同上 |
| `test_condition_gate_behavior.py` | 阈值判断 / 条件源断线 | 同上 |
| `test_contact_damage_behavior.py` | 伤害量 / 接触前置 | 同上 |
| `test_health_bar_behavior.py` | 比例计算 / 更新时机 | 同上 |
| `test_behavior_time_driven.py` | `moving_platform` 位移、`trigger_switch` 时间窗 | 同上 + CLI 退出码 |
| `test_composite_behavior_evidence.py` | 组合契约缺陷 | 同上 |

已有能力（可复用，**不重建**）：

1. `feature_behavior_evidence.BehaviorWorkspace`：把 `Features/` + 探针 + manifest + `project.godot`
   的 `[input]`/`[physics]` 段复制成隔离 Godot 项目，`--import` 后执行。
2. `verify_feature(feature, features_dir, ...)`：支持 `--features-dir`，因此**指向被改过的 Features 副本
   就能跑 mutant**，无需改仓库文件。
3. 注入方式为「精确锚点替换 + sha256 前后比对 + 逐字节恢复」，已有测试证明仓库文件不变。

已有能力的**缺口**（本阶段要补的，FACT）：

- 判定终点停在采集器自报 `STATUS_MISMATCH`；**没有**经过 Validator，也**没有**经过 Evaluation。
- 没有 Mutation Catalog（每条缺陷只有测试代码里的常量，不可机器读取/审计）。
- 没有「Mutation 是否真的生效」的独立检查：现有测试直接断言「某个契约失败了」，
  而"契约失败"既可能是注入生效，也可能是环境坏了。
- 没有 Mutation Verdict 状态模型（Killed / Survived / Invalid / Error / Timeout）。
- 没有 positive / negative control 的同场景对照记录。
- 没有覆盖统计（哪些 Feature 有有效 mutation、哪些被杀、哪些漏检）。

---

## 4. 真实接口（FACT，读取源码确认）

| 组件 | 接口 | 本阶段用法 |
| --- | --- | --- |
| 采集器 | `python .ai/tools/scene_composer/feature_behavior_evidence.py --feature F --features-dir DIR --evidence-out DIR --bundle-id ID [--replay N] [--timeout S]` | 对隔离副本执行；`--features-dir` 指向 mutant 副本 |
| 采集器 API | `verify_feature(feature, features_dir, project_root, godot, replay, timeout, workspace=None)`、`build_contracts()`、`declared_features()` | 只用于 catalog 校验（Feature/Behavior 是否存在），不重复实现执行 |
| Validator | `check_behavior_evidence.check_evidence(project_root, evidence_dir, features, max_age_hours, protocol_path, features_dir, artifact_roots)` | 由 Adapter 调用（`load_verified`） |
| Adapter | `evidence_adapter.load_verified(evidence_dir=..., features_dir=...)` | 报告里记录 Validator 结论 |
| Evaluation | `python .ai/tools/evaluation/evidence_eval.py --tasks-file F --evidence-dir D --no-collect [--json]` → exit 0/1/2/3 | 每个 mutation 一份生成的 tasks 文件，走既有链路 |

一个重要事实：`evidence_eval.py` 支持 `--tasks-file`，所以 **per-mutation 的评估期望可以写进
运行目录里的临时 tasks 文件**，不需要改 `evidence_tasks.yaml`（也就不会把 mutation 期望混进
常规评估集）。

`--evidence-out` 只决定 bundle 落盘目录；执行产物（`result.json` 等）仍写在采集器默认的
`.ai/tmp/behavior/<run_id>/`（Phase 1.58 已确认无 `--artifact-root` 参数），Validator 的
artifact 根校验因此天然通过。

真实耗时（FACT）：`--feature openable_door` 单次采集 **11.98s**（含 `--import` 与 2 次重放）。

---

## 5. 可选 mutation 目标（按可观测性筛选，FACT）

| Feature / Behavior | 可注入缺陷（真实锚点已确认存在） | 预期可观测差异 | 类型 |
| --- | --- | --- | --- |
| `health` / `damage` | 删除 `_current_health = max(_current_health - amount, 0)` | `health.current` 由 1 变 5 | 状态更新遗漏 |
| `health` / `post_death_guard` | `take_damage` 守卫去掉 `_is_dead or` | `health_changed` 次数 1 → 2 | 生命周期守卫缺失 |
| `collect_pickup` / `collect_on_contact` | 删除 `queue_free()` | `node.freed` false | 资源释放遗漏 |
| `trigger_switch` / `latch_once` | Latching 分支去掉 `if _triggered: return` | `activated` 次数 1 → 2 | 状态锁存失效 |
| `openable_door` / `open` | `_apply()` 里删除 `state_changed.emit(value)` | 信号次数 1 → 0（`is_open` 仍 true） | 事件发送遗漏 |
| `save_game` / `save_slot_persists_world_state` | 删除 `_record_last_slot(slot_path)` | `savegame.last_slot` 空 | 持久化记录遗漏 |

这 6 条覆盖 5 种类型（状态转换 2、资源生命周期 1、状态锁存 1、事件传播 1、持久化 1）。
选 5 条（每 Feature 一条）作为第一批，`health` 的 `post_death_guard` 作为同 Feature 的第二类
（若时间允许）。

**不选** `health` 的 9 类中「已知不被任何契约检出」的那一类（Phase 1.51 记录的覆盖缺口）——
它注定 `MUTANT_SURVIVED`，价值在于如实记录，可放在第二批。

---

## 6. 本阶段建议实施范围

1. `evaluation/mutation/` 新模块：`catalog.py`（manifest 加载/校验）、`operators.py`（锚点替换与
   diff）、`workspace.py`（隔离副本 + 仓库哈希看守）、`harness.py`（执行链 + verdict）、
   `mutation_eval.py`（CLI）。
2. `mutation_catalog.yaml`：6 条（先跑 5 条）。
3. Verdict：`MUTANT_KILLED / MUTANT_SURVIVED / INVALID_MUTANT / HARNESS_ERROR / TIMEOUT / NOT_RUN`。
4. 每条 mutation 三次真实执行：**negative control**（原始副本）、**positive control**（mutant 副本）、
   **recovery**（副本恢复后）。三者共用同一份 tasks 文件与同一探针参数。
5. 测试：`evaluation/mutation/tests/test_mutation_harness.py`（锚点/哈希/路径/清理/verdict 逻辑，
   真实文件系统）+ `test_mutation_integration.py`（真实 Godot 端到端，2 个 Feature）。
6. 覆盖统计：`FEATURE_BEHAVIOR_COVERAGE.md` 新增 L5 一节（逐 (Feature, Behavior) 标注
   `未测试 / 有效 mutation 未检出 / killed / invalid / harness error / 不适用`）。

## 7. 不应触碰（明确清单）

- `.ai/skills/**`（含 `code_library` 约 950 条）——只读，任何工具都不写入。
- `Features/**`：**只读**。mutation 只作用于本 Harness 复制出的副本。不修改 5 个已被他人改过的
  `feature.yaml`，不把 8 个未跟踪 Feature 加入支持集。
- `.ai/tmp/p157/**`、`.ai/tmp/p158/**`、`.ai/tmp/behavior/**` 既有产物：只读；本阶段写入
  `.ai/tmp/p159/**`。
- `validator/baselines/*.json`：不审批、不更新、不写入。
- `evidence_tasks.yaml`：不改（mutation 期望写进运行目录的临时 tasks 文件）。
- `project.godot`、`Scenes/E2e*.tscn`、`Levels/E2e*.json`、`Tests/test_e2e_probe_enemy.gd`：
  他人的未提交/历史产物，不修改、不删除。
- 任何 git 写操作：不执行。
