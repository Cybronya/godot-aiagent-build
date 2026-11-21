# Phase 1.55 — Repository Integrity & Engineering Hygiene Audit

> **审计性质**：只读。本阶段未修改任何源码、测试、Feature 配置、协议或既有文档；
> 未执行 `git add` / `commit` / `push` / `reset` / `checkout` / `clean`；
> 未删除、移动、重命名任何仓库文件。
>
> **证据等级**（全文标注）：
> `FACT` = 有命令输出、代码行或测试结果直接证明；
> `INFERENCE` = 由现有实现推断，未经独立实验；
> `UNKNOWN` = 当前无法确认。

---

## 1. 审计基准与工作区状态

| 项目 | 实测值 | 等级 |
| --- | --- | --- |
| 本地 HEAD | `dd3a0e4d5d0f6f47e3a9c729e3ce89190f019bd8` | FACT |
| 分支 | `master`（跟踪 `origin/master`） | FACT |
| 与远端差距 | `0 ahead / 0 behind`（`git rev-list --left-right --count origin/master...HEAD` → `0 0`） | FACT |
| 任务给定基准 SHA | `dd3a0e4d…`，**与本地 HEAD 一致** | FACT |
| 工作区 | **干净**：`git status --short` 0 条；暂存区为空（`git diff --cached --stat` 无输出） | FACT |
| 最近提交 | 12 条，见 §3 | FACT |

结论：本次审计在**已提交状态**上进行，不存在“把工作区修改误认为已提交实现”的风险。
审计过程中唯一的文件写入是**本报告自身**（`.ai/context/PHASE_1_55_AUDIT.md`，此前不存在）。

---

## 2. 审计方法

- 静态核对：`Features/` 目录、`feature.yaml`、`template.yaml`、协议 YAML、manifest JSON、`.ai/tools/**` 代码、`.gitignore`。
- 集合对账：磁盘 Feature 目录 / `feature_index.json` / 协议引用 / 测试覆盖，全部用脚本求差集，不用“总数相等”代替。
- 只读测试：使用既有入口 `python .ai/tools/run_tests.py <段>`，只跑会写 `.ai/tmp/`（已在 `.gitignore`）与 Godot `user://` 的分段；副作用评估见 §7.5。
- **未运行**的：`scene_composer`（31 文件，历史实测约 18 分钟）、`e2e`（1 文件，历史实测约 21 分钟）——为控制审计时长与并发风险跳过，明确标注为 `not_executed`，不折算成 PASS。

---

## 3. Phase 实现时间线（Phase 1.52 之后）

| 提交 | 日期 | 标题声明的 Phase | 实际改动（FACT，来自 `git show --stat`） | 完成状态判断 |
| --- | --- | --- | --- | --- |
| `f0c0c7c1` | 10-28 | Phase 1.52 | 6 个 Feature 接入行为证据协议（`cooldown` / `hit_flash` / `i_frames` / `patrol_movement` / `projectile` / `screen_shake`）；新增 `behavior_protocol.yaml`(471 行)、`probes/feature_behavior_probe.gd`(1255)、`probes/composite_behavior_probe.gd`(1182)、`behavior_manifest.json`(516)、`FEATURE_BEHAVIOR_COVERAGE.md`(319)、`test_behavior_protocol_consistency.py`(546)、`test_feature_behavior_evidence.py`(630) | **实现 + 测试齐备**（FACT：6 个 Feature 现均声明 behavior，见 §4） |
| `5102cf9f` | 10-29 | code-library 管道修复 | `catalog.yaml` 7087 行重写、`INDEX.md` 更新、多处片段单行修订 | **数据管道修复**（非 Feature） |
| `824005d3` | 10-29 | 采集库扩容 | 新增 20 个仓库：`catalog.yaml` +94k 行、`INDEX.md` +2118 行、`candidates.json` 更新、新增源码片段 | **数据扩容**（FACT：现 62 个 sources 目录） |
| `ad0ffcd3` | 10-30 | **Phase 1.53 + 1.54 合并提交** | 新增 `knockback` / `sfx_pool` / `state_machine` / `save_game` / `attack_emitter`；协议扩到 17 动作 /16 观测 /19 信号；新增 `composite_behavior_evidence.py`(849)、`composite_behavior_protocol.py`(671)、`feature_behavior_evidence.py`(898)、`behavior_protocol.py`(973)、`instance_evidence.py`(623)、`composite_behavior_probe.gd`(+122) | **实现齐备**；但 1.53 的 3 个 Feature 与 1.54 的 2 个 Feature **共用一次提交**，Phase 边界不可按提交切分（FACT） |
| `6ab9f9d2` | 10-30 | 采集库同步 | `INDEX.md` +1032 行、`catalog.yaml` +47k 行、gdUnit4 片段去重迁移 | **数据同步** |
| `0099222b` | 10-31 | sfx_pool 修复 | `run_tests.py` +107 行（超时提额与执行改造）、探针 2/4 行、`Features/sfx_pool/test_sfx_pool.gd` | **修复 + 测试** |
| `8be61e97` | 10-31 | sfx_pool 簿记解耦 | `sfx_pool.gd` 19 行、探针 17 行、测试 29 行 | **修复** |
| `dd3a0e4d` | 10-31 | 本地增量落地 | 18 份审计报告（1.36–1.51.2）、`.ai/tools/evaluation/`、`check_instance_evidence.py`、`test_e2e_ownership.py`、复合协议/场景契约、`AI_ENTRY.md` §13、`Scenes/SlimeContactArena.tscn`、多份 schema/测试修订（68 文件） | **文档 + 工具 + 基线修复**；本质是“补交历史增量”，不是新 Phase |

**Phase 1.53 的实际内容**（FACT，`.workbuddy/memory/2026-10-30.md` 与 `template.yaml` 注释、`behavior_protocol.yaml:462` 互证）：
三个 Feature = `state_machine` / `save_game` / `attack_emitter`；协议新增 `state.*`、`savegame.*`、`attackemitter.*` 与只读观测（`observe_savegame_last_slot`、`observe_statemachine_current_state_name`）。
它们**没有独立提交**，也没有独立的行为证据测试文件（见 §8 覆盖矩阵的空洞）。

---

## 4. Feature 完整性矩阵

枚举口径：磁盘 `Features/*/feature.yaml`（不是 CLI 输出）。

### 4.1 总量

| 指标 | 值 | 等级 |
| --- | --- | --- |
| Feature 目录 | **23** | FACT |
| `feature_index.json` 条目 | **23**，与磁盘集合一致 | FACT |
| 声明 `capabilities.required` 非空 | 23 / 23 | FACT |
| 声明 `behavior` 契约 | 23 / 23（合计 **60** 条契约） | FACT |
| 契约引用的协议动作/观测/信号在协议中缺失 | **0**（无未知引用） | FACT |
| 每个 Feature 有 `template.yaml` | 23 / 23 | FACT |
| 每个 Feature 有实现 `.gd`（非测试） | 23 / 23 | FACT |
| 每个 Feature 有 `test_*.gd` | 23 / 23 | FACT |
| Feature 间的四集合差异 | 磁盘 = 索引 = 协议引用 = 测试覆盖，**差集均为空** | FACT |

### 4.2 逐 Feature 明细

| Feature | template | `instance:` 声明 | behavior 契约 | 实现文件 | 测试 | capabilities | 协议引用 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| attack_emitter | ✔ | ✘ | 2 | 3 | ✔ | 1 | ✔ |
| chase_movement | ✔ | ✘ | 2 | 1 | ✔ | 1 | ✔ |
| collect_pickup | ✔ | ✔ | 1 | 1 | ✔ | 2 | ✔ |
| condition_gate | ✔ | ✘ | 3 | 1 | ✔ | 1 | ✔ |
| contact_damage | ✔ | ✘ | 3 | 1 | ✔ | 2 | ✔ |
| cooldown | ✔ | ✘ | 3 | 1 | ✔ | 1 | ✔ |
| heal_pickup | ✔ | ✔ | 1 | 1 | ✔ | 2 | ✔ |
| health | ✔ | ✘ | 5 | 1 | ✔ | 1 | ✔ |
| health_bar | ✔ | ✘ | 5 | 1 | ✔ | 1 | ✔ |
| hit_flash | ✔ | ✘ | 3 | 1 | ✔ | 1 | ✔ |
| i_frames | ✔ | ✘ | 3 | 1 | ✔ | 1 | ✔ |
| knockback | ✔ | ✘ | 3 | 1 | ✔ | 1 | ✔ |
| moving_platform | ✔ | ✔ | 2 | 1 | ✔ | 2 | ✔ |
| openable_door | ✔ | ✔ | 1 | 1 | ✔ | 2 | ✔ |
| patrol_movement | ✔ | ✘ | 3 | 1 | ✔ | 1 | ✔ |
| player_movement | ✔ | ✔ | 2 | 1 | ✔ | 2 | ✔ |
| projectile | ✔ | ✔ | 3 | 1 | ✔ | 2 | ✔ |
| save_game | ✔ | ✘ | 2 | 4 | ✔ | 1 | ✔ |
| screen_shake | ✔ | ✘ | 2 | 1 | ✔ | 1 | ✔ |
| sfx_pool | ✔ | ✘ | 2 | 1 | ✔ | 1 | ✔ |
| state_machine | ✔ | ✘ | 2 | 3 | ✔ | 1 | ✔ |
| stun | ✔ | ✘ | 5 | 1 | ✔ | 1 | ✔ |
| trigger_switch | ✔ | ✔ | 2 | 1 | ✔ | 2 | ✔ |

说明：
- `instance:`（L2 静态实例证据）只有 8 / 23 个 Feature 声明，属设计选择（无场景实体的 Feature 不声明），Validator 第 7 阶段对未声明项报 `NOT_DECLARED` 而非失败（FACT：`validator/check_instance_evidence.py`）。**不构成缺口**，但意味着 L2/L3 只覆盖三分之一。
- `attack_emitter` / `save_game` / `state_machine` 的实现文件数为 3–4，说明是多脚本 Feature（FACT）。

### 4.3 应当不相等、但需要说明的集合

| 集合对 | 关系 | 原因（FACT/INFERENCE） |
| --- | --- | --- |
| 协议 entry 的“前缀” vs Feature id | 不相等 | 协议命名用 `door.open`、`pickup.collect`、`savegame.*` 等领域前缀，与 `openable_door`、`collect_pickup`、`save_game` 不是同一命名空间。**这是命名约定差异，不是漏项**；用 `template.yaml#behavior` 的引用关系统计后，23/23 全覆盖、0 未知引用 |
| 复合场景覆盖 vs Feature 集合 | 3 场景覆盖 10 / 23 | L6 只对“多 Feature 链路”建模：`escape_room`(player_movement, trigger_switch, condition_gate, openable_door)、`slime_contact`(player_movement, chase_movement, contact_damage, health)、`survival_arena`(trigger_switch, openable_door)。其余 13 个 Feature 无 L6 场景（FACT） |

---

## 5. Evidence / Probe / Validator 闭环

### 5.1 实际数据流（FACT，按代码而非设计文档）

```text
Features/<id>/template.yaml#behavior (契约)
        ↓  (feature_behavior_evidence.py 枚举, 真实 Godot)
probes/feature_behavior_probe.gd  ──执行动作──▶ 运行时状态/信号
        ↓  观测 + 重放 2 次
PASS / MISMATCH / INSUFFICIENT / INVALID / NOT_DECLARED 报告
        ↓
测试 test_feature_behavior_evidence.py（断言 PASS/executed/replay/evidence 路径 + 机制级负向 Case 3/4/10）
```

复合链路另有一条：

```text
.ai/context/composite_scenes/<id>.yaml ─▶ composite_behavior_evidence.py ─▶ composite_behavior_probe.gd
        ↓                                   （逐字白名单场景，运行真实 .tscn）
测试 test_composite_behavior_evidence.py（14 个 Case，含断开连接 / 门假开 / 观测不可用 / 前置不满足 等负向）
```

### 5.2 闭环判定

| 环节 | 状态 | 证据 |
| --- | --- | --- |
| Feature → 契约声明 | ✅ 闭环 | 23/23 声明，60 条契约，0 未知引用（§4.1） |
| 契约 → 探针执行 | ✅ 闭环 | `feature_behavior_evidence.py` 逐契约启动真实 Godot，记录 `executed` / `first_observed_frame` / 重放一致性 |
| 探针 → Evidence 结构 | ✅ 闭环（有契约约束） | 状态枚举与 `instance_evidence` 共享（`STATUS_PASS/MISMATCH/INSUFFICIENT/INVALID`），`--require-behavior` 把 `INSUFFICIENT` 升级为失败 |
| Evidence → **Validator** | ❌ **未闭环** | FACT：`grep -rn behavior .ai/tools/validator/*.py` 仅命中无关字符串；Validator 的 7 个框架阶段（Project / Skill Registry / Feature Metadata / Feature Index / Asset / Binding Schema / Instance Evidence）+ 可选 Layer Checks **均不运行行为证据**。行为证据只能由测试或人工 CLI 触发 |
| Evidence → **Evaluation** | ❌ **未闭环** | FACT：`tasks.yaml` 的 `behavior` 阶段调用的是**评测自带探针**（`.ai/tools/evaluation/probes/*.gd` → 暂存为 `Tests/eval136_*_probe.gd`），不是 `feature_behavior_evidence.py` 的产物；两者互不引用 |
| Evidence → 持久化/可比对 | ⚠️ 部分 | 报告只在运行期生成（测试内断言），没有版本化的 evidence 快照；`INSUFFICIENT` 的历史趋势不可追溯（FACT：仓库内无 evidence 产物目录） |
| 自报成功风险 | ⚠️ 存在边界 | `state.set_property` 夹具不计入真实动作（文档与代码一致），但**探针内部观测由 GDScript 自行打印**，Python 侧只解析输出；若探针被篡改，Python 侧只能靠 `test_behavior_protocol_consistency.py` 的探针能力/清单一致性拦住（FACT：该测试校验 manifest 与探针实现映射） |

### 5.3 负向强度（L5）

| 对象 | 缺陷注入 | 证据 |
| --- | --- | --- |
| `health` | **10 处注入**（含删除死亡守卫、无敌门相关） | `tests/test_health_behavior.py`（`injection(` 计数 10） |
| `health_bar` / `condition_gate` / `contact_damage` / `chase_movement` / `stun` / `time_driven` | 机制级负向（期望 MISMATCH / INSUFFICIENT / 退出码），但**无逐 Feature 的缺陷注入** | 各自测试文件内 `injection(` 计数 0；`test_feature_behavior_evidence.py` Case 3/4/10 覆盖机制 |
| `attack_emitter` / `save_game` / `state_machine` / `knockback` / `sfx_pool` 等新 Feature | **无专属行为测试、无注入** | §8 覆盖矩阵 |

结论（INFERENCE，基于上述事实）：`FEATURE_BEHAVIOR_COVERAGE.md` 定义的 `VERIFIED`（要求 L5）在当前 23 Feature 上**不成立**；该文档本身也只写到 12 Feature / 32 行为（见 §10）。

---

## 6. Evaluation 体系

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| 稳定数据模型 | ✅ | `tasks.yaml` 有 `schema.id/version`、冻结规则注释、`required_phases`；`tasks.phase136.yaml` 为 v1 冻结副本（FACT） |
| 可重复入口 | ✅ | `python .ai/tools/evaluation/runner.py --task all/--task T1`；`--list` 实测输出 5 任务（FACT，本次运行） |
| Golden Trace | ✅ 存在并被测试 | `.ai/tools/validator/baselines/{waves,single_stage_boss,multi_stage_boss,holdout}.json`（schema v1）+ `trace_baselines.py`(45k) + `trace_replay.py`(36k) + `approve_trace_baselines.py`(27k)；`test_trace_baselines.py` 72 个 `ok()` 断言（FACT） |
| Holdout | ✅ 有独立工件 | `Tests/test_holdout_trace.gd`(14k) + `.ai/tools/e2e/holdout_trace_probe.py` + `baselines/holdout.json`（FACT） |
| Baseline 记录 | ⚠️ 版本口径过期 | 4 个 baseline 的 `approved_behavior_version` **全部是** `phase-1.22-orchestration-trace-contract-v1`；当前协议已到 Phase 1.54（17/16/19）。该字段是人工字符串，不与协议版本联动 ⇒ 行为变更不会自动使基线失效（FACT + INFERENCE） |
| 质量指标 | ✅ | `scoring.py`：`compute_metrics`（首次通过、计划修订、框架修复、回归缺陷）、`fold_statuses`、`phase_status`、`attempt_passed`（FACT） |
| 区分正确性/成功率/证据完整性 | ⚠️ 部分 | 任务级 PASS 与阶段（plan/artifacts/loadable/behavior/negative/regression）分离；但**没有“证据完整性”维度**——Evidence 体系不在评估输入内（§5.2） |
| 回归识别 | ✅ | 每个任务含 `regression` 阶段（跑 `run_tests.py Features/<id>`）；runner 在运行前后快照 4 个 baseline 的 sha256（`baseline_snapshot()`） |
| 防篡改 | ⚠️ 部分 | runner 用 `artifact_marker` + 所有权清理 + `preflight` 拒绝已存在路径；但评估任务本身可被修改（`tasks.yaml` 无签名/哈希锁定，`git` 是唯一审计） |
| 是否消费运行时 Evidence | ❌ | 见 §5.2：消费的是评测专用探针 |

`--list` 实测（FACT）：

```
T1 单 Feature 生成与验证（collect_pickup）           phases=plan,artifacts,loadable,behavior,negative,regression
T2 多 Feature 组合（chase_movement + contact_damage + health + stun） 同上
T3 条件与开关（放置若干钥匙 → 开门 → 过门）           phases=plan,loadable,behavior,negative,regression
T4 小型关卡与胜负条件（两波清剿 → 出口解锁）          phases=plan,artifacts,loadable,behavior,negative,regression
T5 运行时故障与修复（Node not found → 修复 → 重启回归） 同上
```

**未执行完整评估**（成本：每任务真实 Godot 多轮；本次审计未运行 `--task all`），因此“当前 5 任务是否仍全绿”属 `UNKNOWN`，只有 `PHASE_1_36/1.37` 的历史结论（5/5）可引，但那是更早 HEAD。

---

## 7. 测试体系与质量门禁

### 7.1 发现

| 类别 | 数量 | 说明（FACT） |
| --- | --- | --- |
| Python 测试文件（被 `run_tests.py` 发现） | **61** | 发现规则：`.ai/tools/**/tests/test_*.py` |
| Python 测试文件（磁盘在 `.ai/tmp` 之外） | 65 | 多出的 4 个是 `run_tests_evidence_<token>/test_probe_*.py`（被中断的测试留下的生成物，已 `.gitignore`） |
| Python 断言数（`ok(` 调用） | **2,318** | 静态计数，非运行结果 |
| Godot 测试脚本（被发现的） | **49** | 规则：`Features/*/test_*.gd`(23) + `Tests/test_*.gd`(26) |
| Godot 测试脚本（磁盘全部） | 207 | 差额 158 个全部位于 `.ai/skills/.../code_library/sources/`（第三方采集库，**未被发现**，符合设计） |
| 无法被发现的“项目自身”测试 | 0 | 23 + 26 = 49，与发现数一致（FACT） |

> 口径提醒：Godot 侧每个脚本是“一个 SceneTree 测试程序”，内部用 `_verify_*()` 分项断言并只打印一行 PASS/FAIL；**文件数≠用例数**。Python 侧同理（自定义 `run()` + `ok()`，不是 pytest）。

### 7.2 本次实际执行（当前 HEAD，串行）

| 段 | 命令 | 发现 | 结果 | 耗时 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| feature_registry | `run_tests.py feature_registry` | 4 | 4 PASS | 18 s | 0 |
| validator | `run_tests.py validator` | 10 | 10 PASS | 46 s | 0 |
| runtime | `run_tests.py runtime` | 5 | 5 PASS | 53 s | 0 |
| asset_registry | `run_tests.py asset_registry` | 11 | 11 PASS | 24 s | 0 |
| evaluation | `run_tests.py evaluation` | 2 | 2 PASS | 12 s | 0 |
| gameplay_planner | `run_tests.py gameplay_planner` | 2 | 2 PASS | 14 s | 0 |
| Godot | `run_tests.py --godot-only` | 49 | 49 PASS | 166 s | 0 |
| scene_composer | — | 31 | **not_executed**（历史实测 ~1105 s，见 PHASE_1_51_2 §8.1） | — | — |
| e2e | — | 1 | **not_executed**（历史实测 ~1261 s，同上） | — | — |

合计本次执行 83 个测试文件、0 失败、0 skip、0 INCOMPLETE。**不得**把它表述为“全量通过”：`scene_composer`(31) + `e2e`(1) = 32 个文件未在本阶段执行。

### 7.3 运行器审计（`.ai/tools/run_tests.py`）

| 项目 | 现状 | 等级 |
| --- | --- | --- |
| 发现逻辑 | Python：`.ai/tools/**/tests/test_*.py`；Godot：`Features/*/`+`Tests/` 一层 | FACT |
| 过滤语义 | `filter_tests()` 是**子串匹配**（路径小写包含 needle），不是目录作用域 | FACT |
| 过滤重叠 | `validator` 段 10 个里 **3 个来自 scene_composer/**（`test_capability_contract_validator.py`、`test_artifact_evidence_validator.py`、`test_scene_validator_intent_input.py`）；`runtime` 段 5 个里 2 个来自 scene_composer；`e2e` 段 2 个里 1 个是 `validator/tests/test_e2e_ownership.py`。交集：validator×scene_composer=3、runtime×scene_composer=2、validator×e2e=1 | FACT |
| 段计数可信度 | 8 个短名段相加 = 67，去重后 = **61**（等于全量发现）。即“段内 completed=N/N”是**该过滤器的结果**，不能相加当全量 | FACT |
| 超时控制 | 每测试默认 Python 300 s、Godot 120 s；`e2e` 1800 s、`test_feature_behavior_evidence` 900 s 覆盖 | FACT |
| 进程树终止 | `terminate_tree()`：Windows `taskkill /F /T`，POSIX `killpg(SIGKILL)`；`run_captured()` 用 `Popen(start_new_session=True)` + 合并流，超时后杀树再收尾 | FACT |
| 诊断编码 | `keep_diagnostics_printable()` 只放宽 stdout/stderr 的 `errors="backslashreplace"`，不改子进程解码与判定 | FACT |
| 临时产物隔离 | 前端夹具走 `testsupport/run_workspace.py`：`user://.test_runs/runs/<token>/`（Godot `user://` = `%APPDATA%/Godot/app_userdata/...`），`ownership.jsonl` 账本 + fail-closed 清理；`test_run_workspace.py` 的 W19 断言六个 GDScript 测试都使用 token 作用域根 | FACT |
| 残留 | 仓库根残留 `run_tests_evidence_dbhqxui0/`（被中止的 evidence 测试留下，`.gitignore:42` 已忽略） | FACT |

### 7.4 门禁拓扑

```text
validate.py（静态，7 阶段 + 可选 layer checks）      ← 可作 pre-commit 门禁
run_tests.py（Python 61 + Godot 49）                ← 事实上的唯一回归门
feature_behavior_evidence.py / composite_...        ← 由测试调用，不是独立门禁
evaluation/runner.py                               ← 手动触发，不进任何门禁
```

**FACT**：没有任何脚本把 `validate.py`、`run_tests.py`、`evaluation/runner.py` 串成单一入口；仓库内也没有 CI 配置（`ls .github` 不存在）。因此“全绿”依赖执行者自觉选择正确命令。

---

## 8. Feature 测试覆盖矩阵

列含义：`Impl`=实现入口；`UT`=Feature 自有 `test_*.gd`；`L4`=行为证据（协议契约被执行）；`L5`=该 Feature 的缺陷注入；`L6`=复合场景；`Eval`=评测任务引用。

| Feature | Impl | UT | L4 契约 | L5 注入 | L6 场景 | Eval |
| --- | --- | --- | --- | --- | --- | --- |
| attack_emitter | ✔ | ✔ | 2（动态枚举） | ✘ | ✘ | ✘ |
| chase_movement | ✔ | ✔ | 2 | ✘（机制级） | `slime_contact` | T2 |
| collect_pickup | ✔ | ✔ | 1 | ✘ | ✘ | T1 |
| condition_gate | ✔ | ✔ | 3 | ✘ | `escape_room` | T3 |
| contact_damage | ✔ | ✔ | 3 | ✘ | `slime_contact` | T2 |
| cooldown | ✔ | ✔ | 3 | ✘ | ✘ | ✘ |
| heal_pickup | ✔ | ✔ | 1 | ✘ | ✘ | ✘ |
| health | ✔ | ✔ | 5 | **✔ 10 处** | `slime_contact` | T2 |
| health_bar | ✔ | ✔ | 5 | ✘（机制级） | ✘ | ✘ |
| hit_flash | ✔ | ✔ | 3 | ✘ | ✘ | ✘ |
| i_frames | ✔ | ✔ | 3 | ✘ | ✘ | ✘ |
| knockback | ✔ | ✔ | 3 | ✘ | ✘ | ✘ |
| moving_platform | ✔ | ✔ | 2 | ✘ | ✘ | ✘ |
| openable_door | ✔ | ✔ | 1 | ✘ | `escape_room` / `survival_arena` | T3 |
| patrol_movement | ✔ | ✔ | 3 | ✘ | ✘ | ✘ |
| player_movement | ✔ | ✔ | 2 | ✘ | `escape_room` / `slime_contact` | T2 |
| projectile | ✔ | ✔ | 3 | ✘ | ✘ | ✘ |
| save_game | ✔ | ✔ | 2（动态枚举） | ✘ | ✘ | ✘ |
| screen_shake | ✔ | ✔ | 2 | ✘ | ✘ | ✘ |
| sfx_pool | ✔ | ✔ | 2（动态枚举） | ✘ | ✘ | ✘ |
| state_machine | ✔ | ✔ | 2（动态枚举） | ✘ | ✘ | ✘ |
| stun | ✔ | ✔ | 5 | ✘（机制级） | ✘ | T2 |
| trigger_switch | ✔ | ✔ | 2 | ✘ | `escape_room` / `survival_arena` | T3 |

**空洞（FACT）**：
1. **无 L5**：22 / 23 个 Feature 没有针对自身的缺陷注入；`FEATURE_BEHAVIOR_COVERAGE.md` 的 `VERIFIED` 判据在当前规模下不可满足。
2. **无专属行为测试**：`attack_emitter` / `save_game` / `state_machine`（Phase 1.53 三件套）只有“动态枚举”覆盖，没有自己的场景级/负向测试文件；`knockback` / `sfx_pool` 同理只出现在协议一致性测试与通用证据测试里。
3. **无 L6**：13 / 23 个 Feature 不在任何复合场景中。
4. **无 Eval**：18 / 23 个 Feature 不被任何评估任务引用。

---

## 9. 第三方代码知识库（code_library）治理统计

| 指标 | 实测 | 方法 / 等级 |
| --- | --- | --- |
| 目录 | `.ai/skills/foundation/godot-gdscript/code_library/` | FACT |
| 文件总数 | **12,491** | `rglob` + `is_file` |
| 逻辑体积 | **69.0 MB**（`du -sh` 报 102 MB，差异来自目录块开销） | 逐文件 `st_size` 求和 |
| `.gd` 文件 | **11,991** | FACT |
| `sources/` | 6,526 文件 / 34.5 MB / **62 个仓库目录** | FACT |
| `references/` | 5,962 文件 / 29.5 MB（蒸馏片段） | FACT |
| `catalog.yaml` | v1，`generated_at: 2026-10-29`，`total_entries: 6381`，`unique_fragments: 5962` | FACT |
| `INDEX.md` | 6,100 行 | FACT |
| `candidates.json` | 100 条候选 | FACT |
| Git 跟踪 | **12,523 个文件 / 68.9 MB** | `git ls-files` + 逐文件大小 |
| 重复源码 | 405 组内容完全相同的 `.gd`，涉及 816 个文件（约 6.8%） | sha256 全量比对 |
| catalog 去重口径 | 6381 − 5962 = 419 条以 `duplicate_of` 标记 | FACT |
| 来源可追溯 | 每个 snippet 含 `repo` / `repo_path` / `commit_sha` / `source_url` / `license` / `sha256` | FACT |
| sources 目录与 catalog 仓库匹配 | 62 / 62 全部能匹配 | 启发式脚本，0 例外 |
| 失效索引 | 未发现：`sources/` 全部有对应仓库条目 | FACT |
| 检索是否真的被用 | `SKILL.md:120-135,158,172` 明确要求“先读 INDEX.md，再查 catalog.yaml”；但没有可执行断言证明 agent 真的调用 | **UNKNOWN**（只有文档约束） |
| 与项目代码混杂 | 目录隔离（`.ai/skills/.../sources/`），且 `sources/.gdignore` 阻止 Godot 扫描 | FACT |
| `references/` 是否被 Godot 扫描 | **是**（该目录无 `.gdignore`，`find` 只在 `sources/` 找到 `.gdignore`） | FACT（无忽略文件）+ INFERENCE（会进入 Godot 资源扫描，拖慢编辑器/无头启动） |
| 临时抓取残留 | `.ai/tmp/code_check` **30.2 MB**（`.ai/tmp/` 已忽略） | FACT |

**治理方案（建议，不在本阶段执行）**：
1. `sources/`（34.5 MB 原始仓库）**移出 Git 跟踪**，只保留 `catalog.yaml` + `references/` + `INDEX.md`；用一个 `sources.manifest.json`（repo / commit_sha / license）保证可重放下载，下载脚本按 manifest 复原。
2. `references/` 放 `.gdignore`，避免 Godot 把 5,962 个片段当项目脚本索引。
3. 对 405 组重复片段做一次“保留一份 + 其余改指 `duplicate_of`”的迁移（catalog 已有该字段，只差文件层去重）。
4. `candidates.json` 与 `_meta.json` 保留（体积极小、可追溯性强）。

---

## 10. 文档与代码一致性

| 文档 | 文档记录 | 实际代码状态 | 差异 | 影响 |
| --- | --- | --- | --- | --- |
| `.ai/context/WORK_STATE.md` | “更新于 Phase 1.38 之后”；HEAD `1c30f94`；Phase 1.26–1.37 为未提交增量 | HEAD `dd3a0e4d`；Phase 已到 1.54；全部已提交 | HEAD 落后 6+ 个提交，Phase 落后 16 个 | 下一个 agent 会从错误前提开工（评估/依赖判断都失真） |
| `.ai/context/CURRENT_TASK.md` | Phase 1.38 完成；“全量 87/87 PASS” | 110 个测试文件（61 Py + 49 GD） | 测试规模差 23 个文件 | 同上 |
| `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md` | 12 个 Feature / 32 条行为；“基线 HEAD `1c30f94`” | 23 个 Feature / 60 条行为 | 少 11 个 Feature / 28 条行为 | 用它判断覆盖会漏掉一半 Feature |
| `.ai/context/ROADMAP.md` | 只有 P0/P1 条目，无 Phase 1.5x | 实际已到 1.54 | 规划层未跟进 | 无法从 ROADMAP 判断当前阶段 |
| `.ai/tools/validator/baselines/*.json` | `approved_behavior_version: phase-1.22-…` | 协议 `protocol_version: 2`（17/16/19，Phase 1.54） | 版本口径停在 1.22 | 行为变更不会使基线失效（治理风险） |
| `AI_ENTRY.md` | §13 新增临时目录卫生规则（本会话前一次提交） | 与代码无冲突 | 无 | — |
| `PHASE_1_51_2_AUDIT.md` | 记录 110 个测试、`8be61e97` | 当前 `dd3a0e4d`（后续只有本阶段补交与文档） | 已过期一天 | 可作为历史证据，不可当现状 |

**未记录的实现**（文档缺失，FACT）：`state_machine` / `save_game` / `attack_emitter` 三个 Feature 没有任何审计报告或覆盖矩阵条目；`.ai/tools/evaluation/` 的详细用法只在 README 中，未进 `CONTRACT_INDEX.yaml`（`CONTRACT_INDEX.yaml` 有 166 行变更但未覆盖 evaluation）。

---

## 11. 子系统成熟度评级

评级口径：M0 未实现 / M1 基础结构 / M2 核心可执行 / M3 自动化测试 / M4 完整验证闭环 / M5 稳定基线+回归保护。

| # | 子系统 | 职责 | 主要入口 | 关键数据 | 完成能力 | 测试证据 | 风险 | 评级 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Agent Framework | 入口协议 / Skill 发现 | `AI_ENTRY.md`、`.ai/config/agent.yaml`、`skill-registry.yaml` | `skill-registry.yaml` | 文档驱动，无运行时代码 | Validator 阶段 1–2（`validate.py:620-630`） | 完全依赖 agent 自觉读文档 | **M2** |
| 2 | Skill 系统 | 能力定义与协作 | `.ai/skills/**/SKILL.md` | SKILL 元数据 | 20+ Skill 有 SKILL.md 与依赖/协作配置 | Validator 加载 Skill 记录（Registry/Schema 通过） | 无“Skill 是否解决任务”的评估 | **M2** |
| 3 | Feature Registry | 能力发现 | `feature_discovery.py`、`build_feature_index.py`、`feature_index.json` | `feature.yaml` | 23/23 一致；动态断言已落地 | `feature_registry` 4/4 PASS（本次实测） | 生成物靠人工/提交方重建（历史出现 8 分钟陈旧窗口） | **M4** |
| 4 | Scene Composer | 场景生成与组合 | `scene_composer.py`、`plan_generator.py`、`scene_builder.py`、`composite.py` | `composition_schema.yaml`、`scene_intent` | 生成 + 能力门禁 + 产物证据 + 实例证据 | `scene_composer` 31 文件（历史 31/31 PASS）；本次未跑 | 生成质量无端到端评分（只靠 Eval 5 任务） | **M3** |
| 5 | Evidence / Probe | 运行时行为证据 | `feature_behavior_evidence.py`、`composite_behavior_evidence.py`、`probes/*.gd` | `behavior_protocol.yaml`、`behavior_manifest.json` | 23 Feature / 60 契约 / 3 复合场景 | 协议一致性 PASS、证据测试 PASS（历史）、复合 14 Case | L5 仅 health；无 evidence 快照 | **M3** |
| 6 | Validator | 静态门禁 | `validate.py`（7 阶段 + layer checks） | `validator/README.md` | 覆盖结构/元数据/索引/资源/绑定/实例证据 | `validator` 10/10 PASS（本次） | **不消费行为证据** | **M3** |
| 7 | Evaluation | 端到端能力评估 | `evaluation/runner.py` | `tasks.yaml`（5 任务）、`scoring.py` | 任务执行 + 阶段指标 + baseline 快照 | `evaluation` 2/2 PASS（本次，仅 runner/scoring 自测） | 与 Evidence 不连通；未在本 HEAD 实跑全任务 | **M3** |
| 8 | Workflow / Execution | 运行与隔离 | `run_tests.py`、`testsupport/run_workspace.py` | `ownership.jsonl` | 进程树超时、token 作用域、fail-closed 清理 | `validator` 段含 W1–W23 契约 | 过滤子串重叠；无统一 CI 入口 | **M4** |
| 9 | Code Knowledge Library | 第三方代码检索 | `code_library/INDEX.md`、`catalog.yaml`、`SKILL.md` §检索 | catalog 6,381 条 | 62 仓库 / 5,962 唯一片段 / 来源可追溯 | 无自动化测试（只有数据一致性靠提交时脚本） | 69 MB 进 Git；405 组重复；references 未 `.gdignore` | **M2** |
| 10 | Testing Infrastructure | 回归门 | `run_tests.py` | 110 个测试文件 | 发现/分段/超时/隔离齐备 | 本次 83 文件全绿（+32 未执行） | 段过滤重叠、无 CI、耗时接近 1 小时 | **M4** |

---

## 12. 风险清单

| 级别 | 风险 | 依据 | 影响 |
| --- | --- | --- | --- |
| **High** | Evidence 与 Validator / Evaluation 均未连通 | FACT（§5.2、§6） | “行为已验证”与“门禁通过”是两件事；有人可能只看 Validator exit 0 就认为行为无误 |
| **High** | 状态文档落后 16 个 Phase | FACT（§10） | 新 agent 以 Phase 1.38 / 87 测试为前提规划，直接产出错误计划 |
| **High** | L5 缺陷注入只覆盖 1 / 23 Feature | FACT（§8） | 行为证据“只能证明 PASS，不能证明会拒绝错误实现”，回归保护偏弱 |
| **High** | 测试段过滤是子串匹配，段计数会重叠 | FACT（§7.3：8 段相加 67 ≠ 61） | 用“分段相加”统计覆盖率会虚高；历史报告里的段数字不能复算 |
| **Medium** | code_library 12,523 文件 / 68.9 MB 进 Git | FACT（§9） | 克隆/备份成本、Git 历史膨胀；`references/` 还会被 Godot 扫描 |
| **Medium** | baseline `approved_behavior_version` 停在 1.22 | FACT（§6） | 行为契约变更后，黄金基线不会自动失效，可能“旧基线守新行为” |
| **Medium** | 无统一门禁入口 / 无 CI | FACT（§7.4） | 回归是否执行完全依赖人工；`scene_composer`(18 min) 与 `e2e`(21 min) 最容易被跳过 |
| **Medium** | Phase 1.53 三件套无专属测试 | FACT（§8） | 新增 Feature 只有“动态枚举”兜底，缺场景级与负向证据 |
| **Low** | 仓库根残留 `run_tests_evidence_*/` 与 `.ai/tmp/code_check`(30 MB) | FACT（§7.3、§9） | 磁盘与目录噪音（已 gitignore，不影响提交） |
| **Low** | 单次全量回归约 45–50 分钟且高负载下波动大 | FACT（历史 e2e 527→1261 s） | 容易诱发“跳过测试”或“卡死” |

---

## 13. Phase 1.56+ 开发建议

> 原则：先补“可信基线”，再谈新 Feature。下列工作按优先级排序，**不建议**在本阶段之后立刻开发新玩法。

### P0-1 让 Evidence 进入门禁（架构调整：小）

- **必要性**：当前 Validator / Evaluation 都不消费行为证据，闭环缺最后一跳（§5.2）。
- **涉及**：`.ai/tools/validator/validate.py`（新增 opt-in 阶段 `--behavior-evidence`）、`.ai/tools/scene_composer/feature_behavior_evidence.py`。
- **前置**：无（CLI 已存在且 `--require-behavior` 可作失败口径）。
- **验收**：`validate.py --behavior-evidence` 在 23 Feature 上 exit 0；注入一个已知缺陷（隔离副本）时 exit 1。
- **测试**：新增 `validator/tests/test_behavior_stage.py`，包含“基线 PASS / 注入 FAIL / 缺 Godot 时 INCOMPLETE 而非 PASS”。
- **风险**：真实 Godot 启动使 Validator 从秒级变为分钟级 ⇒ 必须 opt-in，并明确不进入默认快速路径。

### P0-2 状态文档自动同步（无架构调整）

- **必要性**：文档落后 16 个 Phase 是最高性价比的风险（§10、§12）。
- **涉及**：`.ai/context/WORK_STATE.md`、`CURRENT_TASK.md`、`FEATURE_BEHAVIOR_COVERAGE.md`、`.ai/context/ROADMAP.md`。
- **验收**：文档中的 HEAD / Feature 数 / 测试数由脚本生成（或 CI 校验一致），不允许手写数字。
- **测试**：新增 `validator/tests/test_state_docs.py`：读取 `feature_index.json` 与测试发现结果，断言文档里的数字与实测一致（不一致即 FAIL）。
- **风险**：文档里很多是叙述性判断，只能自动校验“数字类事实”，叙述部分仍需人工。

### P0-3 修正测试段过滤语义（无架构调整，改动极小）

- **必要性**：段重叠导致计数虚高（§7.3），影响一切“覆盖率”结论。
- **涉及**：`.ai/tools/run_tests.py` `filter_tests()`。
- **做法**：把“子串包含”改为“相对路径以 `<needle>/` 开头”或显式目录前缀匹配；或增加 `--segment <name>` 走白名单。
- **验收**：8 个段相加 == 61（去重后仍 61），并输出每段与总集的差集。
- **测试**：`validator/tests/test_run_tests_evidence.py` 增加“段互斥”断言。
- **风险**：若其它脚本依赖旧子串行为，需要同步调整（目前只看到 `run_tests.py` 自身与文档引用）。

### P1-4 给 Phase 1.53 三件套补专属行为测试（架构调整：无）

- **必要性**：`state_machine` / `save_game` / `attack_emitter` 无专属测试与负向证据（§8）。
- **涉及**：`.ai/tools/scene_composer/tests/` 新增 `test_state_machine_behavior.py`、`test_save_game_behavior.py`、`test_attack_emitter_behavior.py`；必要时补 `composite_scenes/`。
- **验收**：每个 Feature 至少 1 条缺陷注入被拒绝（`MISMATCH`/`INVALID`），并逐字节恢复。
- **前置**：P0-3（否则新测试可能被错误段纳入）。

### P1-5 code_library 治理（架构调整：目录与构建流程）

- **必要性**：68.9 MB / 12,523 文件进 Git（§9）。
- **涉及**：`.gitignore`、`.ai/skills/foundation/godot-gdscript/code_library/sources/`、下载/重建脚本、`references/.gdignore`。
- **验收**：Git 跟踪体积降到 `< 10 MB`；`catalog.yaml` + `references/` + `INDEX.md` 保持完整；用 manifest 能完整复原 `sources/`；重复片段迁移完成。
- **测试**：新增 `code_library/tests/test_catalog_integrity.py`：catalog 条目 ↔ references 文件 ↔ manifest 三方对账。
- **风险**：一次性删除 34 MB 跟踪文件会产生大 diff；建议单独提交并在提交信息里写明可复原机制。

### P1-6 基线版本口径（架构调整：小）

- **必要性**：`approved_behavior_version` 停在 1.22（§6）。
- **涉及**：`.ai/tools/validator/trace_baselines.py`、`baselines/*.json`。
- **做法**：把 approved 版本改为引用 `behavior_protocol.yaml#protocol_version` + 协议内容哈希；协议变更即要求重新批准。
- **验收**：改动任一协议条目 → 基线校验报“需重新批准”；未改动 → 校验通过。
- **风险**：需要一次性重新批准 4 条基线（可用 `approve_trace_baselines.py`）。

### P2-7 统一回归入口 / CI

- **必要性**：无 CI、无统一门禁（§7.4）。
- **做法**：`run_all.py`（分阶段 + 单段超时上限 + 结构化 JSON），CI 至少跑 fast 段（validator/feature_registry/runtime/asset_registry/evaluation/gameplay_planner + Godot）。
- **验收**：一条命令产出 `{segments, counts, exit}` 且段互不重叠；慢段显式标注 `skipped_by_policy`。

**不建议**：重写 Scene Composer / Feature Registry / Evidence 框架。它们当前分层清晰且有测试保护；问题集中在“最后一跳未接通”和“文档/治理滞后”。

---

## 14. 证据文件与执行命令

| 证据 | 路径 |
| --- | --- |
| 分段日志（本次） | `.ai/tmp/p155/{feature_registry,validator,runtime,asset_registry,evaluation,gameplay_planner,godot}.log` |
| 历史全量分段（对照） | `.ai/tmp/p1512/head8be61e97_*.log`、`.ai/tmp/p1512/head8be61e97_scene_composer.log` |
| 协议 / manifest | `.ai/context/behavior_protocol.yaml`、`.ai/tools/scene_composer/probes/behavior_manifest.json` |
| 复合协议 / 场景 | `.ai/context/composite_behavior_protocol.yaml`、`.ai/context/composite_scenes/*.yaml` |
| 基线 | `.ai/tools/validator/baselines/*.json` |
| 评测任务 | `.ai/tools/evaluation/tasks.yaml`（v1：`tasks.phase136.yaml`） |
| 覆盖矩阵（过期） | `.ai/context/FEATURE_BEHAVIOR_COVERAGE.md` |
| code_library | `.ai/skills/foundation/godot-gdscript/code_library/{catalog.yaml,INDEX.md,candidates.json,sources/,references/}` |

关键命令（均为只读）：

```bash
git rev-parse HEAD; git branch --show-current; git status --short
python .ai/tools/run_tests.py feature_registry      # 4/4 PASS, 18s
python .ai/tools/run_tests.py validator             # 10/10 PASS, 46s
python .ai/tools/run_tests.py runtime               # 5/5 PASS, 53s
python .ai/tools/run_tests.py asset_registry        # 11/11 PASS, 24s
python .ai/tools/run_tests.py evaluation            # 2/2 PASS, 12s
python .ai/tools/run_tests.py gameplay_planner      # 2/2 PASS, 14s
python .ai/tools/run_tests.py --godot-only          # 49/49 PASS, 166s
python .ai/tools/evaluation/runner.py --list        # 5 个冻结任务
python .ai/tools/scene_composer/behavior_protocol.py --check-manifest
```

集合对账 / 统计（只读，本阶段实际执行过的口径）：

```bash
# Feature 集合：磁盘 vs 索引 vs 协议引用 vs 测试
python - <<'PY'  # 见 §4 数据来源：枚举 Features/*/feature.yaml、feature_index.json、template.yaml#behavior、Tests/Features 测试
PY
# 段过滤重叠
python -c "import sys,pathlib;sys.path.insert(0,'.ai/tools');import run_tests as rt;..."  # 见 §7.3
```

---

## 15. 工作区保护确认

| 项目 | 结果 |
| --- | --- |
| 是否修改源码 | **否**（`git status --short` 在本阶段开始时 0 条，结束时仅新增本报告） |
| 是否修改测试 | 否 |
| 是否修改既有文档 | 否（只新建 `PHASE_1_55_AUDIT.md`） |
| 是否执行 git 暂存/提交/推送 | 否 |
| 测试是否产生临时文件 | **是**：`.ai/tmp/p155/`（日志）、Godot `user://.test_runs`（token 作用域）、`.ai/tmp/` 内既有工作区；均在 `.gitignore` 覆盖范围内，未进入 Git |
| 是否有残留进程 | 审计结束后检查 `Godot_*` / `run_tests` 进程为 0 |
| 是否删除/移动/重命名文件 | 否 |
