# Phase 1.36 — End-to-End Capability Evaluation（评估报告）

> 状态：**任务集已冻结并执行完成（2026-10-20）**。5/5 任务最终 PASS，
> 首次通过率 3/5，框架自动修复 1/1，计划修订 2/2，回归缺陷 0，人工干预 0（冻结后）。
> 未提交、未推送；F5 / janitor / `.godot` 并发治理**未实施**。
> 基线：HEAD = `1c30f94`（master），19 个修改 + 1 个未跟踪文件，暂存区为空（详见 §1）。

本阶段交付的是**可重复的评估体系**（`.ai/tools/evaluation/`），不是新测试数量：
任务集、判定口径、指标分母、所有权清理规则都固化在代码与 YAML 中，
报告里的每个数字都能回溯到 `.ai/tmp/eval/<token>/report.json` 的逐步证据。

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| 任务集 | T1–T5（单 Feature / 多 Feature / 条件联动 / 关卡胜负 / 诊断自修） |
| 最终通过率 | **5/5 = 1.0** |
| 首次通过率 | **3/5 = 0.6**（T1、T4 需要一次计划修订） |
| 自动修复成功率 | **1/1 = 1.0**（T5：诊断 → 修复 → 运行时回归） |
| 计划修订成功率 | **2/2 = 1.0**（T1 蓝图形态、T4 波次参数） |
| 回归缺陷 | **0 / 5 项回归检查** |
| 人工干预（冻结后） | **0** |
| 单次全量评估耗时 | 115.0 s / 117.2 s（两次） |
| 黄金基线 | sha256 与 mtime **未变化** |
| 共享目录残留 | **0**（清理 24 项，拒绝 0 项） |
| 全量回归 | **85/85 PASS**（83 + 新增 2 个评估器自测） |

## 1. 评估环境与保护记录

| 项 | 值 |
| --- | --- |
| HEAD | `1c30f94`（master） |
| 起始工作区 | 19 修改 + 1 未跟踪（`.ai/tools/validator/tests/test_e2e_ownership.py`），暂存区 0 |
| Godot | `4.7.stable.official.5b4e0cb0f`（`../Godot_v4.7-stable_win64_console.exe`） |
| Python | 3.12 + PyYAML |
| 平台 | Windows（Git Bash），文件系统为 NTFS |

未执行 `reset` / `clean` / 检出式恢复；未修改既有 Feature、Validator 判定或黄金基线；
未删除任何未知文件；未提交、未推送。评估过程中唯一写入共享目录的是任务自己的产物，
全部按标记 + 运行前缺席证明清理（§6）。

## 2. 方案设计（为什么这样评估）

评估最容易自欺的两处是「用文件生成成功冒充任务完成」和「用宽松断言换全绿」。
本阶段的对策是固定的三段式：

```
需求（固定自然语言）
  → attempts（可证伪的第一次尝试 + 允许的计划修订，各自记录归因）
  → verify（真实 Godot 探针 + 受控负向 + 既有测试回归）
  → 阶段判定（plan / artifacts / loadable / behavior / negative / regression）
  → 指标（分子分母显式，未执行不进分母）
```

- **阶段而不是总分**：`loadable` 通过不代表 `behavior` 通过；`artifacts` 通过不代表
  `plan` 正确。任何必需阶段不是 PASS，任务就不是 PASS（`NOT_EXECUTED` 也不算通过）。
- **受控负向**：每个任务都有一个「去掉关键条件后必须失败」的模式
  （无接触不掉血 / 只拿一把钥匙不开门 / 变异关卡配置被拒绝 / dry-run 不写文件）。
- **归因分离**：`initial`（首次尝试）、`plan_revision`（人工改计划）、`framework`
  （框架自动修复）分开统计，避免把「我改了一下输入」记成「框架能自修」。
- **证伪尝试**：T1/T4 的第一次尝试被显式标记 `expect_failure`。它按预期跑完（含预期中的
  非零退出码）也**不算通过**，必须由下一次尝试交付 —— 这正是本阶段最重要的观测点。

## 3. 任务定义（冻结）

| ID | 需求 | 阶段要求 | 受控负向 |
| --- | --- | --- | --- |
| T1 | a collectible key that disappears when picked up | plan/artifacts/loadable/behavior/negative/regression | 玩家停在 400 px 外：不得发信号、不得消失 |
| T2 | an enemy that chases the target, damages on contact, has health, and can be stunned | 同上 | 不配置目标：90 帧内不得移动、不得掉血 |
| T3 | 两把钥匙都拿到后门才打开 | plan/loadable/behavior/negative/regression | 只拿第 1 把：条件不得满足、门不得开 |
| T4 | 两波敌人，清空所有波次后打开出口 | plan/artifacts/loadable/behavior/negative/regression | 变异关卡（实体场景不存在）必须被 `--check` 拒绝 |
| T5 | 运行时 Node not found 时做最小修复 | plan/artifacts/loadable/behavior/negative/regression | `--dry-run` 不得修改任何文件 |

选择理由：五项分别覆盖任务书要求的五个维度，且**全部复用仓库既有 Feature 与探针体系**
（`chase_movement` / `contact_damage` / `health` / `stun` / `collect_pickup` /
`condition_gate` / `openable_door`、`level_orchestration_probe.py`、
`runtime/self_repair.py`），没有为评估新增游戏资产或放宽任何既有校验。

输入冻结在 `fixtures/`（4 个 Blueprint/场景 + 1 个手工 `.tscn`），
行为断言冻结在 `probes/`（3 个运行时探针 + 1 个加载探针）。

## 4. 执行结果（两次正式运行）

两次运行（token `5112-08e78d96`、`7656-e9c85412`）在相同环境下结果逐项一致：

| 任务 | 尝试链 | 首次通过 | 最终 | 耗时（两次） |
| --- | --- | --- | --- | --- |
| T1 | `entity_blueprint`(证伪) → `scene_blueprint_revision` | ✗ | **PASS** | 15.6 / 16.0 s |
| T2 | `compose_four_features` | ✓ | **PASS** | 24.6 / 24.1 s |
| T3 | `author_wiring` | ✓ | **PASS** | 14.6 / 15.2 s |
| T4 | `waves_flag`(证伪) → `explicit_waves` | ✗ | **PASS** | 22.4 / 22.6 s |
| T5 | `framework_repair` | ✓ | **PASS** | 37.3 / 38.7 s |

阶段矩阵（两次一致）：

```
id   plan  artifacts  loadable  behavior  negative  regression
T1   PASS  PASS       PASS      PASS      PASS      PASS
T2   PASS  PASS       PASS      PASS      PASS      PASS
T3   PASS  NOT_EXEC   PASS      PASS      PASS      PASS   ← artifacts 未设独立校验（见 §9）
T4   PASS  PASS       PASS      PASS      PASS      PASS
T5   PASS  PASS       PASS      PASS      PASS      PASS
```

关键行为证据（摘自 `report.json` 的探针输出）：

```
T1 PICKUP positive: hits=1 alive=false          → 收集一次并自我移除
T1 PICKUP negative: hits=0 alive=true           → 未接触不触发（负向成立）
T2 approach=120.0 (90 frames)                   → 实体根真实追击
T2 contact_damage=3 ceiling=4 tick=0.50         → 按既有时序结算、未每帧结算
T2 stun lock_drift=0.000 resumed=56.0           → 眩晕期间锁定、结束后恢复
T3 first key: fulfilled=false open=false hits=0 → AND 语义（不提前开门）
T3 second key: fulfilled=true open=true hits=1 collision_disabled=true
T4 probe: waves=2.0 door_open_after_all=1.0 finish_events=1.0 state_after_exit=1
T5 Result: FAIL (dry run) / PASS (repair attempt 1)；脚本 Helth → Health，单行改动
```

## 5. 指标与分母

| 指标 | 值 | 分子/分母 | 分母含义 |
| --- | --- | --- | --- |
| 最终通过率 | **1.0** | 5/5 | 已尝试任务数（排除 `NOT_EXECUTED`/`UNAVAILABLE`） |
| 首次通过率 | **0.6** | 3/5 | 第一次尝试逐步骤通过 **且** 任务 PASS |
| 自动修复成功率 | **1.0** | 1/1 | `kind=framework` 的修复尝试 |
| 计划修订成功率 | **1.0** | 2/2 | `kind=plan_revision` 的尝试 |
| 回归缺陷 | **0 / 5** | 0/5 | 回归阶段失败次数 / 实际执行的回归检查数 |
| 人工干预 | **0** | — | 冻结后未修改任务集或探针 |
| 单任务耗时 | 15–39 s | — | 含暂存、生成、Godot 运行、回归子集 |
| 资源/模型成本 | `UNAVAILABLE` | — | 仓库无模型调用与费用计量入口 |

## 6. 失败原因分类与能力边界

评估期间实际观测到的失败（含 bring-up 阶段，均已归因）：

| 编号 | 现象 | 分类 | 处置 |
| --- | --- | --- | --- |
| D1 | Entity Blueprint 交付单 Feature 场景时根类型推导为 `Node2D`，能力契约判 `Collision requires CollisionShape2D` | 生成器表达力 + 契约误判（组件实例自带的碰撞子树不可见，属已知 gap） | 计划修订为 Scene Blueprint（根即入口场景）；首次通过失败被如实记录 |
| D2 | 组件实例 + `root.scene` 但缺 `root.type` → 契约报 `Node requires node_exists` | 契约要求与 Blueprint 文档提示不一致 | 在蓝图里显式声明 `type`（与入口场景真实根类型一致） |
| D3 | `level_planner --waves 2 --wave eval_grunt:2` 产出 **1 波** | 参数语义与文案不符（`--waves` 被 `--wave` 静默覆盖） | 改用两次显式 `--wave`；缺陷记录待修 |
| D4 | Scene Composer 不表达信号连接，也不支持同一 Feature 的多个实例 | 组合工具能力缺口 | T3 由人工 glue 交付（`.tscn` 的 3 条 connection），并在报告中标注 |
| D5 | `scene_composer --tests` 在根实例蓝图上生成**空断言**测试 | 生成测试质量缺口 | 不把该测试当行为证据；行为证据只取探针 |
| D6 | `collect_pickup/feature.yaml` 写明 `collected` 直连 `set_condition` 需 `binds=[pickup_id]`，照做会以 3 参调用 2 参方法 | 文档与实现不一致 | 改为不加 binds；本条由探针的真实调用错误暴露 |
| D7 | 需求里出现 "player" 时 `compose_features` 把角色判成 player（把「以玩家为目标」误当「玩家组件」） | 词法匹配副作用 | 冻结需求措辞时规避；列入下一阶段 |
| D8 | 评估器自身：① T1 fixture 的 YAML 值未加引号导致解析失败；② 证伪尝试因「步骤符合预期」而提前结束尝试链 | 评估器缺陷 | 均已修复，并新增 5 条自测（A1 系列）锁定语义 |

**能力边界（当前框架能做到 / 做不到）**

- 能做到：单 Feature 场景（需显式根实例）、3–4 Feature 组合实体、按既有约定产生
  可运行行为（追击/接触伤害/眩晕/拾取/条件聚合/门状态）、关卡波次编排与真实胜负闭环、
  `node_path_literal` 类运行时缺陷的诊断与最小修复。
- 做不到（需人工或下一阶段）：用一份计划直接表达「根实例 + 组件导出参数 + 信号连接 +
  同一 Feature 多实例」；用 `--waves` 表达波次数量；从需求词直接得到正确的实体角色
  （关键词会劫持）；生成非空的行为测试；修复 `node_path_literal` 之外的运行时错误。

## 7. 评估器自身的验证

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 判定与指标纯函数 | `python .ai/tools/evaluation/tests/test_evaluation_scoring.py` | 28 项 PASS，exit 0 |
| 清理所有权 / 断言 / 报告结构 | `python .ai/tools/evaluation/tests/test_evaluation_runner.py` | 24 项 PASS，exit 0 |
| 全量回归（含上述 2 个） | `python .ai/tools/run_tests.py` | **85/85 PASS**，exit 0 |
| 评估器可重复性 | `runner.py --task all` ×2 | 逐任务判定与指标一致 |
| 文档同步后的复核 | `test_scene_intent_contract.py`、`test_run_tests_evidence.py`、`test_level_planner.py`（均解析 `CONTRACT_INDEX.yaml`） | 三个均 exit 0；YAML 可解析 |

自测锁定的语义（防止评估器以后悄悄变宽）：未知状态一律 `INCOMPLETE`；
`NOT_EXECUTED` 不算通过；尝试判定只看自己的步骤；标记不匹配的文件**拒绝删除**；
运行目录之外的目录**拒绝递归删除**；`expect_failure` 尝试不结束尝试链。

## 8. 黄金基线与工作区保护

四条历史黄金基线（评估前后两次采样，逐字节一致，未重录/未改写 `run_id`）：

| 基线 | sha256（前 16 位） | mtime |
| --- | --- | --- |
| `.ai/tools/validator/baselines/holdout.json` | `acf8bfbac8abf774` | 2026-10-18 23:55 |
| `.ai/tools/validator/baselines/multi_stage_boss.json` | `5736788cd9efd866` | 2026-10-17 22:19 |
| `.ai/tools/validator/baselines/single_stage_boss.json` | `d540cfe2226216e0` | 2026-10-17 22:19 |
| `.ai/tools/validator/baselines/waves.json` | `878691b1d174cbf0` | 2026-10-18 22:39 |

资源所有权证据（两次正式运行）：清理 24 项 / 拒绝 0 项 / 共享目录残留 0 项；
`Scenes`、`Levels`、`Tests` 中评估产物在运行后全部消失；
`.ai/tmp/eval/<token>/report.json` 保留为证据。

## 9. 未执行 / 未覆盖（如实记录）

| 项 | 状态 | 原因 / 条件 |
| --- | --- | --- |
| 模型调用与费用成本 | `UNAVAILABLE` | 仓库无 provider 计量入口；不伪造数字 |
| T3 `artifacts` 独立阶段 | `NOT_EXECUTED` | T3 的产物是手工 `.tscn`，其结构断言并入 `plan`；未再设独立产物校验 |
| 并行评估（两个 runner 同时跑） | `NOT_EXECUTED` | 共享目录固定路径互斥；与 Phase 1.33 §5.3 的并发限制同源 |
| 移动平台 / 可开启门 / 血条 等 Feature 的端到端任务 | `NOT_EXECUTED` | 本阶段只取 5 项代表任务，其余未评估（不计入通过率） |
| `node_path_literal` 之外的自动修复分类 | `NOT_EXECUTED` | 框架本阶段只有这一条确定性策略 |
| 黄金基线重录 | `SKIP` | 任务书明确禁止 |

## 10. 下一阶段最值得解决的三个问题

1. **计划表达力**：让 Blueprint 直接表达「根即入口场景 + 组件导出参数 + 信号连接 +
   同一 Feature 多实例」。当前 T1 需要一次计划修订、T3 完全靠人工 glue，
   这不是测试问题而是表示能力问题；解决后 T1/T3 的首次通过才可以真正提高。
2. **生成的测试必须非空**：`scene_composer --tests` 在根实例蓝图上产出零断言测试，
   使 `loadable` 阶段出现「PASS 但没有内容」的空洞。需要生成结构断言（根类型、
   关键子节点、必要信号连接），否则「测试覆盖关键失败路径」这一维度无法成立。
3. **工具契约一致性自动校验**：本阶段两次遇到「文案与实现不一致」
   （`--waves` 被 `--wave` 覆盖；`collect_pickup` 的 `binds` 说明与信号签名冲突）。
   这类低级不一致应由 Validator/契约测试在合并前拦住，而不是靠端到端评估反复发现。

## 11. 变更清单（未提交）

新增（全部未跟踪）：

- `.ai/tools/evaluation/README.md`（方案、指标口径、用法、限制）
- `.ai/tools/evaluation/tasks.yaml`（5 个冻结任务）
- `.ai/tools/evaluation/runner.py`（执行器 + 所有权清理 + 报告）
- `.ai/tools/evaluation/scoring.py`（判定与指标，口径唯一事实源）
- `.ai/tools/evaluation/probes/eval_pickup_probe.gd`
- `.ai/tools/evaluation/probes/eval_stun_enemy_probe.gd`
- `.ai/tools/evaluation/probes/eval_key_door_probe.gd`
- `.ai/tools/evaluation/probes/eval_scene_load_probe.gd`
- `.ai/tools/evaluation/fixtures/t1_entity_blueprint.yaml`
- `.ai/tools/evaluation/fixtures/t1_scene_blueprint.yaml`
- `.ai/tools/evaluation/fixtures/t2_scene_blueprint.yaml`
- `.ai/tools/evaluation/fixtures/t3_key_door.tscn`
- `.ai/tools/evaluation/fixtures/t4_gameplay_blueprint.yaml`
- `.ai/tools/evaluation/tests/test_evaluation_scoring.py`
- `.ai/tools/evaluation/tests/test_evaluation_runner.py`
- 本报告

修改（均在既有未提交文件内**追加/替换本阶段段落**，不涉及他人修改的代码）：

- `.ai/context/CONTRACT_INDEX.yaml`：新增 `evaluation:` 契约条目（任务/判定/所有权/证据）
- `.ai/context/CURRENT_TASK.md`：当前状态新增 Phase 1.36 段（1.34 段保留为「此前」）
- `.ai/context/WORK_STATE.md`：新增 Phase 1.36 段，更新「更新于」时间标记

其余 16 个既有未提交修改与 `test_e2e_ownership.py` 保持原样，未触碰；未执行任何
`git add` / `commit` / `push`（暂存区仍为 0）。

最终 `git status`：**19 修改 + 3 未跟踪条目**（`PHASE_1_36_AUDIT.md`、`.ai/tools/evaluation/`、
既有 `test_e2e_ownership.py`），暂存区 0。我的临时探针目录（`.ai/tmp/spike*`、
`.ai/tmp/eval_spike`、`.ai/tmp/before.json`）已删除。

证据位置（易失，`.gitignore` 已覆盖 `.ai/tmp/`）：

- `.ai/tmp/eval/5112-08e78d96/report.json`（正式运行 1）
- `.ai/tmp/eval/7656-e9c85412/report.json`（正式运行 2）
- `.ai/tmp/full_regression_136_final.log`（最终全量回归）
