# Work State

当前工程状态。（更新于 Phase 1.25 Semantic Orchestration Traces & Event-Level Regression Coverage 之后，待 commit）

## Project Stage

Feature-based Agent Development —— Phase 1.25（waves 语义事件 + 事件级回归覆盖）已完成并
在本机实测通过；Phase 1.24（黄金基线覆盖补齐 + 审批安全 + 质量门禁）、Phase 1.23（黄金
Trace 基线与回归检测）、Phase 1.22（可回放诊断事件 + 只读回放器）、Phase 1.21（多阶段
Boss 编排 + 跨契约身份校验）、Phase 1.20（通用关卡编排 + BossChallenge 接入）、
Phase 1.19（蓝图 → 组合计划生成）、Phase 1.18（Scene Intent 集成与运行时交互编排）、
Phase 1.17（多实体场景组合与绑定完整性）、Phase 1.16（实体绑定端到端接入）、Phase 1.15
（跨层契约与统一校验）、Phase 1.14（通用关卡编排管线）、Phase 1.13（关卡编排生成）、
Phase 1.12（死亡与胜负闭环）、Phase 1.11（实体根运动 + 接触伤害）、Phase 1.10（行为验证）、
Phase 1.9（端到端生成）、Runtime Playtest & Self-Repair（Phase 1.6，AD-010）与 Gameplay
Loop Composer（Phase 1.5，AD-009）已完成。

## Phase 1.25：waves 语义事件与事件级回归（实测）

- **生产端**：LevelOrchestrator 新增 wave_started / wave_cleared / exit_unlocked
  （真实转换边界 + 幂等守卫）；schema v1 加性扩展（旧 trace/基线完全兼容，boss 基线
  零重录）。
- **回放端**：波次事件模式约束、索引/清空/解锁顺序规则、waves 胜利前置条件；
  R44–R57（14 项）锁定。
- **基线**：waves 重批 v2（7 事件链，真实捕获 + 显式批准）；holdout 保持 v1
  （不虚构不存在的状态——审计结论已记录）。
- 验证：e2e 171 项 PASS（四模式逐事件比较）；回放 58/58；比较器 64/64；
  Godot 八专项 exit 0；validate.py 0 error / 17 warning 不变。

## Phase 1.24：黄金基线覆盖补齐 + 审批安全 + 质量门禁（实测）

- **四条黄金基线**：boss 单/多阶段（Phase 1.23）+ waves + holdout（Phase 1.24，
  真实 Godot 沙箱捕获 + 显式批准 v1，批准记录含指纹与来源链路）。
- **审批安全**：review/apply 从候选文件内容重算指纹；篡改/替换 = 拒绝（exit 1）；
  apply 原子写入；U49–U56 锁定。
- **配套修复**：level_planner `--mode holdout` CLI；两个适配层 `export_trace_json`
  转发器；level 探针 trace 导出；holdout_trace_probe。
- **删除守卫**：根因与分段执行结论如实记录于 run_tests.py 文档头；
  低删除量策略（导入缓存刷新 ×2、探针自清理、%TEMP% 沙箱）已实施。
- 验证：e2e 独立 171 项 PASS（T5a–T5d 四模式逐事件比较）；trace_baselines 57；
  godot-only 36/36；各分段全过；validate.py 0 error / 17 warning 不变。

## Phase 1.23：黄金 Trace 基线与回归检测（实测）

- **黄金基线**：`.ai/tools/validator/baselines/{multi_stage_boss,single_stage_boss}.json`
  （baseline_schema_version 1；事件来自真实 Godot 沙箱捕获；批准记录完整）。
- **比较器** `validator/trace_baselines.py`（只读）：先 trace 校验 + 回放，后按序逐事件
  对齐比较；严格字段 7 个，动态字段仅 run_id/timestamp_ms（显式策略），data 默认 strict；
  PASS(0)/REGRESSION·INCOMPLETE·INVALID_TRACE(1)/BASELINE_MISSING·INVALID_BASELINE(2)。
- **批准流程** `e2e/approve_trace_baselines.py`：candidate → review → apply --i-approve；
  测试/比较器永不写基线（T13 断言）。
- **E2E T 段 T1–T14**：沙箱真实捕获 → 逐事件比较 → 差异注入（exit 1 + 字段路径）→
  动态字段 PASS → 基线缺失/损坏 exit 2 → 基线不可改写 → 无残留。
- 验证：`run_tests.py` **78/78 PASS（exit 0）**；e2e 独立 169 项 PASS；trace_baselines
  单测 49 项；回放单测 44 项；validate.py 0 error / 17 warning 不变。

## Phase 1.22：诊断事件 + 只读回放（实测）

`LevelOrchestrator` 在真实状态变更边界写入 `OrchestrationTrace`（schema v1，纯数据）；
序号 0 起严格 +1，`timestamp_ms` 相对启动且非递减；重复通知与非法转换可观测但不改状态；
`trace_enabled = false` 零事件。`validator/trace_replay.py` 只读回放（不驱动游戏），
重建最终状态 / 阶段链 / Boss 死亡确认，并拒绝违反契约的序列；真实 E2E trace 由探针从
Godot 运行导出（`Tests/e2e_multi_stage_boss_trace.json`）并经独立回放后清理。

| 量 | 实测值 |
| --- | --- |
| 事件类型 | orchestration_started / stage_started / stage_completed / stage_transitioned / boss_death_confirmed / level_victory / level_failed / duplicate_event_ignored / invalid_transition_rejected |
| 契约 | 序号 +1 无缺口；时间戳非递减；阶段字段 null 策略；事件纯数据（is_json_safe） |
| 幂等 | Boss 重复死亡 = duplicate_event_ignored(boss_death)；终结后只允许 duplicate_event_ignored |
| 回放器 | trace_replay.py CLI 0/1/2；R1–R43；拒绝未知版本/类型、序号缺口、阶段跳跃、终结冲突、Boss 未确认死亡即胜利 |
| 真实 E2E | P14–P18：真实 trace → victory + [clear_1@0, boss@1]；重复回放一致；去终结事件重建为 playing |
| 关闭开关 | trace_enabled = false → 零事件且游戏结果不变（T5） |

新增：`Orchestration/orchestration_trace.gd`、`Tests/test_orchestration_trace.gd`（T1–T8）、
`validator/trace_replay.py`、`validator/tests/test_orchestration_trace.py`（R1–R43）、
`.ai/context/orchestration_trace_schema.yaml`；多阶段探针新增 trace 导出与 E2E P14–P18。

## Phase 1.21：多阶段 Boss + 跨契约校验（实测）

`mode: boss` 新增可选 `stages`（Phase 1.20 单阶段配置不写该字段即完全兼容）。
阶段顺序只由数组决定；`clear_enemies` 清空后进入 `defeat_boss`，Boss 死亡后完成，
可选 `complete_level` 作为显式终结阶段。`LevelHost` 改为 deferred start，避免在宿主
`_ready` 组装期间生成子节点触发 Godot「Parent node is busy」。

| 量 | 实测值 |
| --- | --- |
| 阶段契约 | `stages` >= 2；id 唯一；至少一个 clear_enemies；恰好一个 defeat_boss 且最后；complete_level 只能最后且要求 exit=never / victory=boss_defeated |
| 清理阶段 | 引用真实实体/条目；不能引用 boss.entity；Boss 未激活前不得完成关卡 |
| 转换 | clear 的 `alive_count` 归零 → 激活 Boss 阶段（只一次）；defeat 阶段内 Boss 死亡 → 完成该阶段 |
| 提前死亡 | 清理阶段击杀 Boss 只记录一次，不跳阶段；进入 Boss 阶段时立即结算且不重复 |
| 幂等 | stage_started / stage_completed / boss_defeated / finished 各恰好一次；重复 died / 重复帧不重复 |
| 交叉校验 | `arena_scene` 根名 == plan.host.name；根级 instance 集合 == plan.instance_name 集合；Boss instance 与 plan 一致；stage 实体均在 plan；缺 plan → INCOMPLETE |
| Python/Godot 一致 | C11 共 11 例（合法 clear→boss / +complete；空/重复/未知类型/缺 Boss 引用/顺序非法/终结冲突/waves+holdout 携带 stages） |
| 真实 E2E | P1–P13：蓝图 → 两个实体场景 → bind_assets → 自动 plan → `--compose-plan` 三实例宿主 → `--stage clear:stage_grunt:2 --stage boss` → check_level --plan → Godot 清理→Boss→完成 / 玩家失败 |

新增：`e2e/multi_stage_boss_probe.py`（临时 GDScript，机读 `STAGE:` 行）、
`Tests/test_boss_orchestration.gd` B6（多阶段生命周期/非法配置）。
交叉校验实现仍只有一份：`level_planner.validate_level(level, plan=...)`；
`check_level.py --plan`、`validate.py --level --level-plan` 均调用它。

## Phase 1.20：Boss 编排接入（实测）

`BossChallenge` 不再维护第二套胜负状态机：`Levels/boss_challenge.json`（boss 模式）+
`LevelConfig` + `LevelOrchestrator` 驱动世界状态；适配层只保留 HUD/表现与 Boss 停摆。
`level_schema.yaml` version 2 追加 `mode: boss` / `boss` 块 / `boss_defeated`，
现有 waves / holdout / v1 语义未改。

| 量 | 实测值 |
| --- | --- |
| Boss 身份 | `boss.entity` 必须已在 entities 声明；`boss.instance` 是相对宿主根的显式实例路径（拒绝绝对路径 / `..`）；不按 role / 节点名猜 |
| 实例来源 | `spawn: existing`（适配层 `bind_boss(entity_id, node)`，需带 Health）或 `spawn: on_start`（编排器从配置场景生成） |
| Boss 存活 | 出口区进入被显式拒绝（即使门已开）；Boss 不计入 alive_count |
| Boss 死亡 | 只结算一次：按 exit.unlock_when 开门，按 victory.condition 完成；重复 died 不重复开门/完成 |
| 玩家死亡 | Failed + finished(false) 恰一次；终态重复事件无效 |
| 失败路径 | 未知 boss 实体 / existing 缺 instance / 非法 spawn / 非法胜利规则 → 配置层拒绝（字段路径）；宿主实例解析失败 → `fail_setup`（stage=bind） |
| 跨层一致性 | `test_cross_layer_contract.py` C10：合法 boss + 未知实体 / existing 缺实例 / 非法 spawn / 含 waves / v1 boss 共 7 例，Python 与 Godot 判定及字段路径一致 |
| 真实 E2E | e2e N1–N13：蓝图 → 生成 Boss 实体场景 → bind_assets → 自动 plan → `--compose-plan` 宿主 → `level_planner --mode boss` → Godot headless（身份 / 存活零胜利 / 一次完成 / 重复忽略 / 玩家失败 / 非法实例拒绝） |

新增：`Orchestration/level_host.gd`（通用宿主适配器：按配置给组合宿主接线，
`existing` 时按 `boss.instance` 绑定），`Tests/test_boss_orchestration.gd`（B1–B5），
`e2e/boss_level_probe.py`（临时 GDScript，机读 `BOSS:` 行，用后删除），
`gameplay_planner/level_planner.py --mode boss --boss E --plan PLAN`（从真实 plan 生成，
默认 arena_scene = `res://Scenes/<host>.tscn` 且必须已存在；失败不写盘）。

## Phase 1.19：蓝图 → 组合计划生成（实测）

composition plan 不再手写：Gameplay Blueprint + **真实生成产物** →
`scene_composer/plan_generator.py` → plan 文档 → 既有正式入口
`scene_composer --compose-plan` → 宿主 `.tscn` → 真实 Godot headless。
生成器只生成声明，组合仍由 `composite.compose_from_plan`（唯一实现）承担；
校验也复用同一实现（临时目录真实试组合）→ **不新增** 独立 plan Validator 层。

| 量 | 实测值 |
| --- | --- |
| 实体 → 场景 | override > 蓝图 `entities.<id>.scene`（declared）> `Scenes/<Pascal>.tscn`（convention），逐实例可追溯 |
| 实例名 | `Pascal(entity_id)`；同名冲突 → 拒绝（不静默消歧） |
| 目标关系 | 只接受 `--target` 或 `--relations <entity_graph.json> --relation <name>`；source 必顶 Feature 声明 `target_path`（feature_index interfaces） |
| 自动生成的计划 | `instances` 保留蓝图 entity id + 真实生成场景；无关系声明时计划**不含** `targets` |
| 正式入口 | `--compose-plan` dry-run PASS；宿主含 `target_path = NodePath("../E2eProbePlayer")`，2 个 ext_resource 实例 |
| 真实 Godot | status=PASS/errors=0；双实例命名唯一；enemy 子树仅 enemy 资源、player 子树仅 player 资源；target_path 解析一致且 90 物理帧内真实接近 ≥20px |
| 受控负向 | 缺场景映射 / 未知目标 / 未知关系名 / source 无 target_path 能力 / 同名歧义 / 未知实体 override → 均 exit 1 且**无产物** |

宿主级组件职责审计（任务 E）：出生点、出口门/出口区、宿主级触发器均在
**场景 + LevelConfig/编排层**（`LevelOrchestrator` 注入式契约、`LevelConfig` 的
spawn/exit/victory）；composition plan 只声明「实例 + 目标引用」。本阶段不扩宿主组件
schema（DEFERRED）—— 职责重叠会破坏 4 份契约的边界。

## 本次变更（Phase 1.20）

- `Orchestration/level_config.gd`：新增 boss 模式归一化字段（arena_scene / boss_entity /
  boss_instance_path / boss_spawn / boss_scene）与镜像校验；waves/holdout 拒绝 boss 块。
- `Orchestration/level_orchestrator.gd`：boss 模式（existing 绑定 / on_start 生成）、
  `boss_defeated` 信号、只结算一次、出口区在 Boss 存活时拒绝胜利、`_started` 守卫
  （配置应用前不推进超时/重开）、`fail_setup` bind 阶段诊断。
- `Orchestration/level_host.gd`（新增）：通用组合宿主适配器（配置 → 编排器接线）。
- `Scenes/boss_challenge.gd` + `Levels/boss_challenge.json`：BossChallenge 改用统一编排器。
- `gameplay_planner/level_planner.py`：`validate_level` boss 规则 + `build_boss_level`
  （真实 plan → boss 配置）+ CLI `--mode boss --boss --plan`。
- `level_schema.yaml`：boss 契约、合法值、规则、generator_scope 与示例。
- 测试：`Tests/test_boss_orchestration.gd`（B1–B5）、`test_level_planner.py` L9、
  `test_cross_layer_contract.py` C10、`e2e/boss_level_probe.py` 与 e2e N1–N13。

## 本次变更（Phase 1.19）

- 新增 `scene_composer/plan_generator.py`：Gameplay Blueprint + 实体场景映射 →
  composition plan（映射优先级 override>declared>convention / `Pascal(entity_id)` 实例名 /
  目标只来自 `--target` 或点名 `--relation` / source 必须有 `target_path` 能力 /
  复用 `compose_from_plan` 校验 / 原子写入）；CLI 退出码 0-1-2。
- 新增 `scene_composer/tests/test_plan_generator.py`：Q1–Q12（24 项），含 6 类负向与兼容。
- e2e `test_end_to_end_generation.py`：新增 M1–M6（计划生成 / 蓝图派生关系 / 无关系不造目标 /
  缺映射与未知目标负向）；L9/L10/L16/L17 改为消费**自动生成**的计划（不再手写 dual_plan）。
- `scene_composer_schema.yaml` / `CONTRACT_INDEX.yaml` / e2e README：计划生成产物与入口同步。

## Phase 1.18：Scene Intent 集成与运行时交互编排（实测）

- **composition_plan 正式入口**（契约 scene_composer_schema.yaml#composition_plan）：
  `scene_composer.py --compose-plan <plan.yaml>`（dry-run 只校验不落盘）；
  composite.py `compose_from_plan` 唯一实现；Scene Intent 保持单实体契约不变（并列文档方案）。
- **运行时交互契约**：实体身份 ≠ 宿主实例名 ≠ target 引用（NodePath）；目标由计划显式
  声明（写追击方实例的 `target_path = NodePath("../<实例>")`），构建期拒绝无效目标，
  运行时由 chase_movement 既有相对解析契约消费；真实 Godot L16–L17 验证。
- **统一 Validator 新增 binding 层**：`run_binding_layer` 复用 check_bindings；
  `validate.py --bindings-dir`；信息不足 = info 诊断（不进基线），未知实体 = BINDING_* error。
- 验证：`run_tests.py` **73/73 PASS（exit 0）**；e2e 独立 118 项 PASS；
  composite 单测 16 项；unified validator 29 项；validate.py 0 error / 17 warning 不变。

## Phase 1.17：多实体场景组合与绑定完整性（实测）

- **双实体显式绑定闭环**（e2e L1–L8）：player 与 enemy 走同一条
  discovery → `--resolve-entity-from` → bind_assets → scene_composer 链路；
  player_* 资源全部 `resolved_from=binding`；静态断言最终资源归属与双向无泄漏。
- **多实体组合最小实现** `scene_composer/composite.py`：Godot 原生 instancing
  （宿主只声明 ext_resource + instance 节点），输入场景字节不变，实例名唯一（冲突消歧），
  返回实体→实例映射；CLI `--scene ... --name Host [-o dir] [--json]`。
- **真实 Godot 运行证据**（e2e L11–L15）：宿主 `E2eProbeDualHost.tscn` 由 run_scene
  运行 `status=PASS, errors=0`；瞬态探针断言两实例存在、命名唯一、运行时子树资源归属
  互不覆盖（enemy=slime / player=player）；探针与生成物由 finally + Z1 清理。
- **check_binding_schema.py 增强**（S1–S9）：记录级 role/asset/entity 健康检查、
  `--gameplay` 实体存在性（未知实体 = ERROR）、`binding_scope_errors` 契约字段检查、
  无蓝图 = note（信息不足）。既有版本检查与旧格式完全兼容；业务规则权威仍是 bind_assets。
- 验证：`run_tests.py` **72/72 PASS（exit 0）**；e2e 独立 115 项 PASS；
  validate.py 0 error / 17 warning（与基线逐项相同）。

## Phase 1.16：实体绑定端到端接入（实测）

实体作用域绑定进入**真实生成链路**，实体身份全程可追溯：

```
feature_discovery（payload.role=enemy）
  + gameplay 蓝图实体清单（恰好一个 enemy 角色实体）
  → discovery_to_binding --resolve-entity-from   # 解析唯一实体 id，打上 {entity, role, asset}
  → bind_assets --gameplay --binding             # 作用域路由：目标实体 resolved_from=binding
  → scene_composer --bindings                    # 绑定文档的节点名/资源路径落盘进生成的 .tscn
  → 真实 Godot headless（G8/G9/G10a）            # 生成场景 + 行为探针 PASS
```

零匹配 → `no_entity_with_role`（exit 1）；多匹配 → `ambiguous_entity_role`（exit 1，
诊断含全部候选 id）——归属不可猜测。`--entity` 显式优先。

| 场景 | 证据（e2e C/D/I 段 + test_binding_scope S6） |
| --- | --- |
| 1 多实体不同资源 | C2a/C3/D6/D6b/I1/I1b：作用域只路由到 enemy；玩家实体 idle 仍为 index 推断；生成场景带显式绑定节点（E4）+ 真实 Godot 行为探针 PASS |
| 2 显式 vs 推断冲突 | D7：无绑定推断得 idle=X，实体作用域绑定指向 Y≠X → 最终应用 Y（resolved_from=binding） |
| 3 未知实体 | D8：exit 1 + `binding_scope_errors`（location/entity/reason），不伪造成功 |
| 4 单实体旧格式 | C3b：适配器缺省输出保持 `{role, asset}` |
| 5 多实体 role-level | I2：既有行为保留，跨实体歧义由 compatibility 门禁标记 INCOMPATIBLE |
| 6 发现信息不足 | C6/S6：零匹配 `no_entity_with_role`、多匹配 `ambiguous_entity_role`（exit 1，含候选 id） |

验证：`run_tests.py` → **71/71 PASS（exit 0）**；E2E 独立 → exit 0（100 项 PASS）；
`test_binding_scope.py` → exit 0（29 项）；`validate.py` → 0 error / 17 warning（基线不变）；
真实 Godot（v4.7.stable headless）：G8/G9/G10a + C1–C9 跨层探针全 PASS。

## Phase 1.15：跨层契约与统一校验（实测）

| 交付 | 实现 | 证据 |
| --- | --- | --- |
| I1 绑定 entity 作用域 | `bind_assets.parse_explicit_bindings`（权威实现）：`{entity, role, asset}` 作用域路由 / 未知实体 → `binding_scope_errors`（exit 1，可定位）/ 类型门禁（audio↔visual 错配拒绝且不回退）/ 多实体角色级绑定按既有规则处理 + note 标注 / 结构非法不静默跳过；`discovery_to_binding.py --entity`（可选） | `asset_registry/tests/test_binding_scope.py`（I1-A…I1-G，24 项 PASS）；既有绑定测试 53 项 PASS（无回归） |
| 统一 Validator | `validator/unified.py` 编排既有四层检查器；`validate.py --scene-blueprint/--gameplay-blueprint/--level/--runtime-scene/--runtime-result`（opt-in，缺省兼容）；结构化诊断 `{layer,code,severity,location,path,reason,hint}` + 稳定代码；Runtime Godot 缺失 → UNAVAILABLE/INCOMPLETE（非零） | `validator/tests/test_unified_validator.py`（C10，24 项 PASS）；`validate.py --runtime-scene` 真实 Godot PASS |
| 跨层一致性 | 共享正反例（15 例）同时经 Python `validate_level` 与 Godot `LevelConfig`（真实探针）逐例比较判定与字段路径；C7 缺省值两层一致；C9 绑定边界 | `validator/tests/test_cross_layer_contract.py`（C1–C9，33 项 PASS，15/15 一致） |

命令与退出码（Phase 1.15 时点）：

- `python .ai/tools/run_tests.py` → **71/71 PASS（exit 0）**（新增
  `asset_registry/tests/test_binding_scope.py`、`validator/tests/test_unified_validator.py`、
  `validator/tests/test_cross_layer_contract.py` 均由统一入口自动发现）。
- `python .ai/tools/validator/validate.py` → 0 error / 17 warning（与基线逐项相同）。
- `python .ai/tools/validator/validate.py --level Levels/timed_combat_arena.json --level
  Levels/survival_arena.json --gameplay-blueprint survival_game.yaml --scene-blueprint
  slime_enemy.yaml` → exit 0（scene/gameplay/level×2 全 PASS）。
- `python .ai/tools/validator/validate.py --runtime-scene res://Scenes/EnemyBasic.tscn`
  → exit 0（runtime 层真实 Godot PASS）。
- `python .ai/tools/e2e/tests/test_end_to_end_generation.py` → exit 0（含 I1 回归段）。
- 独立层检查：`check_level.py`（两个发布配置 PASS）、`check_scene_composition.py
  slime_enemy.yaml` PASS、`check_gameplay.py survival_game.yaml` PASS、
  `check_runtime.py --scene`（真实 Godot）PASS。

## Phase 1.14：通用关卡编排管线（实测）

关卡编排从 `TimedCombatArena` 专属实现整理为场景无关管线，**两个真实场景使用同一套实现**：

| 场景 | 模式 | 配置 | 编排职责 |
| --- | --- | --- | --- |
| `Scenes/TimedCombatArena.tscn` | `waves` | `Levels/timed_combat_arena.json`（v2） | 顺序波次、清波推进、出口解锁、进出口区胜利 |
| `Scenes/SurvivalArena.tscn` | `holdout` | `Levels/survival_arena.json`（v2） | 持续生成调度（interval/delay/max_alive）、生存计时、生存胜利 |

通用实现（不依赖任何场景节点路径，全部经注入）：

- `Orchestration/level_config.gd`（`LevelConfig`）：解析 + 校验 + 归一化；错误带配置文件路径 /
  字段路径 / 失败阶段（`config_load` / `config_validate`）。
- `Orchestration/level_orchestrator.gd`（`LevelOrchestrator`）：状态机、生成与登记
  （幂等死亡结算）、waves 顺序波次、holdout 持续生成、出口解锁、胜利判定、胜负一次、
  重开轮询、结构化诊断。
- 场景适配层只做节点引用与表现：`Scenes/timed_combat_arena.gd`（公开 API 原样保留）、
  `Scenes/survival_arena.gd`（保留拾取物 / 陷阱 / 奖励机关 / HUD / 结束冻结 / 遗留导出）。

| 量（真实 Godot，`Tests/test_generic_level_orchestration.gd` G1–G13） | 实测值 |
| --- | --- |
| G1 通用性 | 静态：通用组件无 `NodePath(` / 无场景名（剔除注释）；运行时：程序化合成宿主（非 `.tscn`）完整跑通 波次→开门→入区→Completed，`finish_events=[true]` |
| G2 行为一致 | 发布场景 + 发布配置：3 波（3/3/5）逐波推进、清除途中门关闭、全清后门开、入区 Completed、胜负一次、无效配置零生成 + Failed |
| G3 同一实现 | 两场景编排器同一脚本；survival=`holdout` / arena=`waves`；发布生存配置零错误 |
| G4 玩法不回归 | 0.3s 出敌（interval=0.2）、精英 delay 前不出现、delay 后 1 个、`max_alive=3` 峰值锁死、1.0s 生存胜利（事件一次）、玩家死亡 → Lost、开局拾取物 1 个、陷阱 3 个 |
| G5–G7 | 首波剩敌不启动第二波；第二波清除途中出口关闭；全清后出口开启且状态仍 Playing |
| G8 | 重复 `died` 通知不重复计数 / 不重复推进 |
| G9 | Completed 后再入区 / 玩家死亡：胜负事件仍 `[true]` |
| G10 | 8 类非法配置（waves 与 holdout 规则集）全部拒绝：Failed + 零生成 + `waves=0` + 字段可定位 |
| G11 | 手写 waves / v1 配置 / 缺 exit+victory 选填块 / 遗留导出生存通道均正常 |
| G12 | 手写 waves 混编（普通+精英）生成 2 敌、清空后开门 |
| G13 | 诊断定位：`stage=config_validate` + `config_path` + 字段 + `consumer_scene`；读取失败 `config_load`；实体场景缺失带实体 id 与路径 |

Schema 与校验：version 2（新增 `mode` / `holdout` / `spawns` / `survive_duration`）；
version 1 遗留配置继续有效（v1 + holdout 一律拒绝）。`level_planner.validate_level` 与
GDScript 运行时校验为同一规则集的两个镜像实现（producer/validator 共用前者）。

验证：`python .ai/tools/run_tests.py` → **69/69 PASS（exit 0）**；
`python .ai/tools/e2e/tests/test_end_to_end_generation.py` → exit 0；
`python .ai/tools/validator/validate.py` → 0 error / 17 warning（与基线逐项相同）；
`python .ai/tools/gameplay_planner/tests/test_level_planner.py` → PASS（L1–L8 + 生成器 + CLI）；
临时资源无残留（`Levels/E2eGeneric*` 由测试自身清理并断言）。

## 本次变更（Phase 1.14）

- 新增 `Orchestration/level_config.gd`、`Orchestration/level_orchestrator.gd`（通用编排管线）。
- 重写 `Scenes/timed_combat_arena.gd`（薄适配层，公开 API 与 Phase 1.13 一致）、
  `Scenes/survival_arena.gd`（holdout 适配层 + 场景专属逻辑保留）。
- `Scenes/SurvivalArena.tscn` 增加 `level_config_path`；新增 `Levels/survival_arena.json`；
  `Levels/timed_combat_arena.json` 升级 version 2 + 显式 `mode: waves`。
- `.ai/context/level_schema.yaml`：契约升级（v2 / mode / holdout / 版本兼容 / 生成器边界）。
- `.ai/context/CONTRACT_INDEX.yaml`：`level_orchestration` 条目更新（version 2、两种模式、
  runtime_impl / config_impl、known_limits、generic_test）。
- `gameplay_planner/level_planner.py`：版本兼容 + holdout 校验（`_validate_holdout` /
  `_validate_victory_holdout`）；`build_level` 产出 v2 waves 配置。
- 新增 `Tests/test_generic_level_orchestration.gd`（G1–G13）；
  `gameplay_planner/tests/test_level_planner.py` 增加 L7/L8；
  `Tests/test_survival_arena.gd` 阶段 F 显式走遗留导出通道（断言不变）。
- `.ai/tools/e2e/README.md`：Phase 1.14 证据归位说明（不新增探针，避免复制证据）。

## Phase 1.13：关卡编排生成（实测）

关卡编排层进入生成链路：Gameplay Blueprint → `gameplay_planner/level_planner.py` →
`Levels/<id>.json`（声明式：实体 / 数量 / 波次 / 出口规则 / 胜利条件）→
`Scenes/timed_combat_arena.gd` **运行时消费**。生成数量、波次顺序、出口门与胜利条件全部由配置驱动；
无效配置在运行时被拒绝并给出可定位诊断；手写 `waves` 通道保持兼容。

| 量 | 实测值（真实 Godot） |
| --- | --- |
| 发布配置（`TimedCombatArena.tscn` + `Levels/timed_combat_arena.json`） | 3 波 / 首波 3 敌人，既有 `test_timed_combat_arena.gd` 全 PASS |
| 生成配置（`level_planner` 为 `e2e_probe_enemy` 生成，2 波 2/3） | `spawned_wave1=2`、`index_after_wave1=1`、`alive_after_wave1=3`、`wave2_count=3` |
| 首波未清 → 次波不启动（L9） | 首波存活时 `index` 不推进、`spawned` 不增加 |
| 出口门 | `door_open_with_survivor=0` → 全清后 `door_open_after_all=1` |
| 胜利 | 玩家真实输入进出口区 → `state_after_exit=1`（Completed）、`finish_events=1` |
| 生成物身份 | `entity_scene_match=1`、`focus_hits=5`（全部生成敌人来自 `E2eProbeEnemy.tscn`） |
| 无效配置 | 拒绝：`spawned_wave1=0`、`state=2`（Failed）、诊断定位 `waves[0].entries[0].count` |
| 幂等（L15） | 重复 died 通知不重复计数、不重复推进波次（移除守卫后对应测试立即失败） |
| 直接胜利变体 | `victory=all_waves_cleared` → 清场即 Completed，且出口门不开 |

审计结论（现有系统如何生成敌人 / 管理波次 / 统计死亡 / 控制出口）：

- 敌人在**运行时实例化**（`_spawn_enemy` / `_spawn`），但生成数据此前硬编码在 `.tscn` 导出属性中
  —— 本轮把「配置」外化为关卡 JSON，代码保持既有生成路径。
- 计数与全清：`alive_count`（`died` 递减）+ `waves` + `wave_index`；SurvivalArena 实时统计
  （`_count_enemies()`），BossChallenge 用 tscn `[connection]`。
- 出口与胜利：最后必需波次清空 → 开门 → `ExitZone.body_entered`（需门已开）→ `_finish(true)`。
- 生成实体与手写实体在竞技场中的接口相同：入口场景根 CharacterBody2D + 子节点 `Health` 命名约定
  （Phase 1.11 / 1.12 已验证）。

为什么是 JSON：Godot 无 YAML 解析；项目已有 JSON 产物先例（`feature_index.json`、
`gameplay_blueprints/*.json`）。契约文档仍是 YAML（`.ai/context/level_schema.yaml`）。

## Phase 1.12：死亡与胜利闭环（实测）

生成的敌人被**真实攻击输入路径**（空格 → `AttackTrigger` → `Health.take_damage`）打死，
死亡语义完全由既有 `Health` 拥有（`died` 信号）；场景编排层接收后递减击杀计数并让实体
退出战斗；最后一个必需敌人清空时由**场景自身逻辑**打开出口，玩家真实输入走进出口区完成。

| 量（生成物 `Scenes/E2eProbeEnemy.tscn`，宿主 `TimedCombatArena.tscn`） | 实测值 |
| --- | --- |
| 真实攻击结算 | `damage=1`、`max_health=5`、hp `5 → 4 → 0`（5 次攻击） |
| 死亡事件 | `died_events=1`（重复攻击 / 再次 take_damage 仍为 1） |
| 击杀计数 | `2 → 1`，重复攻击后仍 1；`live_entities=1 == alive_count` |
| 退出战斗 | `removed=1`（`died → queue_free` 既有规则） |
| 不提前胜利 | `door_open_with_survivor=0`、`premature_victory=0` |
| 胜利条件 | 最后一个敌人死后出口门由场景逻辑打开；玩家进出口区 → Completed、`finish_events=1` |

关键机制与产物：

- 审计结论：死亡由 `Features/health` 拥有（`died` 信号）；清理/计数/胜负全在场景编排胶水
  （TimedCombatArena / SurvivalArena / BossChallenge 的 tscn `[connection]`），**无**全局死亡或
  敌人管理器；奖励只有击杀计数与 `Systems/reward` 注册表契约，没有货币/掉落。
- 真实缺口 = 数据：`Scenes/TimedCombatArena.tscn` 的 `AttackTrigger` 未配 `target_group`，
  空格攻击解析不到目标；与 InterruptRange/SiegeGate/StunTraining 对齐加上
  `target_group = "enemies"`。
- 运行时闸门：新增 `.ai/tools/e2e/death_victory_probe.py`（N1/D1/D2/N2/V1/V2 断言 +
  `DEATH:` / `VICTORY:` 机读行 + `--expect survive` 受控负向），把生成场景放进**真实竞技场**。
- 永久回归：`Tests/test_timed_combat_arena.gd` M 段（真实攻击输入路径 → died → 计数/退出战斗）。
- 生成链路未改动：审计表明生成实体的死亡/管理接口已达到既有敌人同等水平
  （实体根可接收 `target_path`、子节点 `Health`、分组由编排层添加），缺口在游戏侧接线。

## Phase 1.11：生成实体的玩法闭环（实测）

修复后，Scene Composer 生成的敌人**实体根**真正在物理帧中移动，并在与玩家真实物理接触后
按现有 `ContactDamage + Health` 机制结算伤害（不修改生命值、不伪造信号）。

| 被测物（真实 Godot） | root_approach | child_max_drift | damage_total | HP |
| --- | --- | --- | --- | --- |
| 修复前旧生成物 `Scenes/SlimeEnemy.tscn`（现已重新生成） | 0.0 px | 120.0 px | 0 | 10 → 10 |
| 修复后生成物（e2e 场景 / 重新生成的 SlimeEnemy） | 120.0 px | 0.0 px | 3（节拍上限 5） | 10 → 7 |

关键机制：

- Feature Scene Template 声明 `attach.root_instance`（`chase_movement`）——实体根就是追击
  组件的入口场景实例，追击脚本驱动实体本身（不再作为子节点“自己跑”）。
- Feature Scene Template 声明 `attach.nodes`（`chase_movement` 的体积形状、`contact_damage`
  的接触形状）——Entity Blueprint 推导把作者 nodes + 成员模板节点写入 `nodes[]`；
  契约 known gap `entity_blueprint_nodes_dropped` 因此关闭。
- 静态闸门：`scene_validator` 在计划声明根实例时要求根必须是该实例、且该组件不得再作为
  子节点出现（旧结构会被拒）；`test_generator` 对根实例组件断言根节点类型。
- 运行时闸门：`.ai/tools/e2e/behavior_probe.py` v2（实体根位移 / 子节点不自移 / 无接触不受伤 /
  接触伤害节拍 / 目标释放后停止），配合变异体（去掉 ContactShape）做受控负向。

## Phase 1.10：玩法行为验证（实测；Phase 1.11 已扩展为实体根 + 接触伤害）

新增 `.ai/tools/e2e/behavior_probe.py`：对生成链路的产物在真实 Godot 中执行行为断言
（观察位置/距离变化，不是节点/信号存在性）。主行为 = 敌人追踪目标并实际移动，
目标使用项目真实玩家实体场景 `Features/player_movement/Player.tscn`。

实测（物理帧 60 Hz，speed=80）：距离 `400.0 -> 280.0`（approach=120.0 px）、
`baseline_drift=0.0`（未配置目标时静止）、`post_free_drift=0.0`（目标释放后停止）。
受控负向：只含 `health` 的生成场景 → 探针 `exit_code=1` +
`Precondition: ... 不存在 ChaseMovement 组件`。
独立复用：`Scenes/Enemy.tscn`（追击组件为根）与 `Scenes/SlimeEnemy.tscn`（为子节点）
两种结构均 PASS，说明探针不绑定单一生成形状。

断言阈值与诊断约定见 `.ai/tools/e2e/README.md`（断言表 + `BEHAVIOR:` 行机读字段）。

## Phase 1.9：端到端闭环现状（实测，非推测）

| 阶段 | 状态 | 证据 |
| --- | --- | --- |
| 自然语言 → Gameplay Blueprint | IMPLEMENTED_AND_TESTED | `gameplay_planner/planner.py`；e2e A1–A3 |
| Gameplay → 每实体 Entity Blueprint | IMPLEMENTED_AND_TESTED（本次新增） | `blueprint_generator.write_entity_blueprints` + `planner --emit-entities`；e2e A4–A8/G3 |
| Feature Discovery | IMPLEMENTED_AND_TESTED | `feature_registry/feature_discovery.py`；e2e B1–B5 |
| 显式候选选择 | IMPLEMENTED_AND_TESTED | `discovery_to_binding.py --select`；e2e C1–C5 |
| Resource Binding | IMPLEMENTED_AND_TESTED（作用域缺口） | `bind_assets.py --gameplay --binding`；e2e D1–D5、I1 |
| Scene Intent / 场景生成 | IMPLEMENTED_AND_TESTED | `scene_composer.py`（Gate + Capability Contract + Artifact Evidence）；e2e E1–E9 |
| 静态验证 | IMPLEMENTED_AND_TESTED | `check_scene_composition.py`、`check_gameplay.py`；e2e F1、G4/G7。`validate.py` 不调用后两者 |
| Godot 运行时 | IMPLEMENTED_AND_TESTED | `runtime/run_scene.py`；e2e G8/G9（真实 headless） |
| 玩法行为验证 | IMPLEMENTED_AND_TESTED（实体根追踪 + 接触伤害，Phase 1.11） | `e2e/behavior_probe.py` 在真实 Godot 中对**生成场景**断言实体根位移、子节点不自移、接触前后玩家生命值变化与节拍上限；e2e G10a–G10h、G11、G12 |
| 死亡与胜负闭环 | IMPLEMENTED_AND_TESTED（Phase 1.12） | `e2e/death_victory_probe.py` 把生成场景放进真实 `TimedCombatArena.tscn`，经真实攻击输入击杀 → `died` 一次 → 计数减一 → 实体退出战斗 → 全清后场景自身开门 → 进出口区 Completed；e2e J1–J9 + `Tests/test_timed_combat_arena.gd` M 段 |
| 失败诊断与自修复 | IMPLEMENTED_AND_TESTED（既有） | `runtime/self_repair.py` + `test_self_repair.py` / `test_asset_self_repair.py`（本轮未改） |

## 本次变更（Phase 1.13）

- 新增 `.ai/context/level_schema.yaml`：关卡编排契约（字段含义 / 合法值 / 默认值 / 校验规则 +
  可运行示例）；JSON 为运行时表示、YAML 为契约档案，两者字段一致。
- 新增 `.ai/tools/gameplay_planner/level_planner.py`：Gameplay Blueprint → 关卡配置；
  `validate_level` 为唯一校验实现（producer 与 validator 共用）；CLI 支持 `--emit` / `--check`。
- 新增 `.ai/tools/validator/check_level.py`：独立校验 CLI（与 check_gameplay / check_scene_composition 同构）。
- 新增 `Levels/timed_combat_arena.json`：随仓库发布的真实关卡配置。
- `Scenes/timed_combat_arena.gd`：改为 `level_config_path` 驱动（加载 + 运行时校验 + entries 生成 +
  出口 / 胜利规则 + 按实例幂等的 `died` 结算 + 可定位诊断）；配置无效拒绝开始；手写 `waves` 兼容。
- `Scenes/TimedCombatArena.tscn`：移除硬编码 `waves` 与敌人场景引用，改指向配置文件。
- 新增 `Tests/test_level_orchestration.gd`（发布配置消费 + L7–L15 + 直接胜利变体 + 无效配置拒绝
  + 手写 waves 兼容）；新增 `gameplay_planner/tests/test_level_planner.py`（L1–L6 + 生成器 + CLI）。
- 新增 `.ai/tools/e2e/level_orchestration_probe.py`（生成配置的运行时消费）；
  `e2e/tests/test_end_to_end_generation.py` 新增 K 段（K1–K12）。
- `CONTRACT_INDEX.yaml` / `e2e/README.md`：契约与探针文档同步。

## 本次变更（Phase 1.12）

- `Scenes/TimedCombatArena.tscn`：`AttackTrigger.target_group = "enemies"`（真实攻击路径接线，
  纯数据修正；此前空格攻击解析不到目标）。
- 新增 `.ai/tools/e2e/death_victory_probe.py`：生成实体的死亡/胜利闭环探针
  （真实竞技场宿主 + 真实攻击输入；`--expect die|survive`；临时脚本 `Tests/e2e_death_victory_probe.gd`
  非 `test_` 前缀并在 finally 删除）。
- `Tests/test_timed_combat_arena.gd`：新增 M 段（真实攻击输入路径驱动死亡与计数）+
  `_press_attack` / `_on_enemy_died` 辅助（死亡后不触碰已释放节点，改用信号镜像）。
- e2e：新增 J1–J9（正向、手写等价性、不死变异体双向负向、缺少运动能力的实体、清理断言），
  Z1 扩展至新探针脚本与变异体场景；README 补探针断言表。

## 本次变更（Phase 1.11）

- `Features/chase_movement/template.yaml`：`attach.root_instance: true` + `attach.nodes`
  （默认体积形状 28×28）；`Features/contact_damage/template.yaml`：`attach.nodes`
  （接触形状 36×36）。Feature 使用说明同步（feature.yaml composition.usage）。
- `template_loader.derive_scene_blueprint`：Entity Blueprint 推导 root.scene（根实例）与
  nodes[]（作者 nodes + 成员模板节点，作者优先；冲突/歧义报错）。
- `scene_builder`：入口场景 == root.scene 的组件不再实例化为子节点。
- `scene_validator`：计划声明根实例时改判根实例（静态解析被引用场景根类型；缺根实例 /
  重复子节点为失败）；`test_generator`：根实例组件断言根节点类型。
- 新增 `scene_composer/tests/test_entity_root_instance.py`（5 组契约回归）。
- e2e：新增 G6b–G6d（结构语义）、G10f–G10h（实体根位移 / 子节点不自移 / 接触伤害）、
  G12（去接触形状变异体的受控负向）；探针 v2 支持 `--expect damage|none`。
- 产物重新生成：`Scenes/SlimeEnemy.tscn`、`Tests/test_slime_enemy.gd`（同一 blueprint）；
  `Tests/test_slime_asset_binding.gd` 改为断言实体根即追击组件 + 碰撞形状。

## 本次变更（Phase 1.9 + 1.10）

- 新增 `.ai/tools/e2e/behavior_probe.py`（Phase 1.10）：生成场景的真实玩法行为探针
  （可独立运行；渲染临时 GDScript → 真实 Godot → 断言距离变化 → 清理）。
- 新增 `planner --emit-entities`：Gameplay Blueprint → 每实体 Entity Blueprint（复用声明的实体不产出）。
- 修 `scene_composer` / `test_generator` 跨盘符 `os.path.relpath` 崩溃（生成成功却 exit 1）。
- 修 `feature_discovery` 词匹配路径缺反混淆（敌方需求不再拖入 `player_movement`）。
- 新增 `.ai/tools/e2e/`（跨工具集成套件，自动被 run_tests.py 发现）+ README。

## 待解决（阻塞项）

- ~~显式绑定无 entity 作用域~~（Phase 1.15 已关闭：`{entity, role, asset}` 作用域 +
  可定位错误 + 类型门禁 + I1-A…G 回归测试）。
- ~~`validate.py` 未串联 Scene/Gameplay/Runtime 三个 check~~（Phase 1.15 已关闭：
  `unified.py` 编排 + Layer Checks flags + 稳定诊断代码；Runtime 缺失如实 INCOMPLETE）。
- Asset Manifest 17 条既有 missing-path 警告。
- ~~e2e 生成链路尚未改用适配层 `--entity`~~（Phase 1.16 已关闭：主链路经
  `--resolve-entity-from` 打上实体作用域并实际消费；旧格式路径保留为兼容通道）。
- 统一诊断错误代码依赖检查器失败文本前缀（未识别文本回退层默认代码；检查器文案
  改动需同步前缀表）。
- Runtime 层探针耗时，为显式 opt-in；缺省 Validator 只做快速静态检查（按层区分覆盖）。
- 实体身份解析以 role 为粒度：同角色多实体时必须由调用方 `--entity` 显式消歧
  （发现阶段 query 为自然语言，不感知实体 id——契约设计如此）。
- ~~多实体「合并场景」的运行时绑定验证不在当前链路覆盖内~~（Phase 1.17 已关闭：
  `composite.py` 原生 instancing 组合 + L11–L14 真实 Godot 运行时资源归属断言）。
  仍开放的部分：合并场景的**物理/逻辑交互**（碰撞、目标指派）不在 composite 职责内，
  由关卡编排层或后续阶段承担。
- 宿主组合器不解析实体场景内部结构（不做 Scene Intent 第二套管线）；实例冲突只按
  根名消歧，无节点级去重语义。
- 宿主级组件（出生点 / 出口区 / 宿主触发器）仍在场景 + LevelConfig/编排层；
  composition plan 不承载它们（Phase 1.19 已审计，扩展 DEFERRED）。
- 计划生成器的目标关系只支持**点名消费**（`--relation`）；relation → target 无语义映射表，
  且 source 必须确有输出 `target_path` 的 Feature（否则拒绝）。
- ~~`BossChallenge` 未接入通用编排~~（Phase 1.20 已关闭：使用同一 LevelConfig + LevelOrchestrator）。
  仍开放：`BossChallenge` 只使用单阶段 boss；多阶段组合宿主由生成链路覆盖。
- holdout 模式无出口概念；顺序波次仅 waves 模式支持；并行刷怪、随机刷怪、动态难度、
  按时间调度仍不支持。
- 拾取物 / 陷阱 / 奖励机关由场景适配层管理，不纳入关卡编排配置。
- 生成器（`level_planner.py`）产出 waves / boss / 多阶段 boss 配置；holdout 配置仍为手工编写。
- 遗留上限语义差异：原 `SurvivalArena` 的 `max_enemies` 为组计数（含精英）；通用化后
  `holdout.max_alive` 为编排层登记总上限，仅手工注入未登记实体时计数口径不同。
- Scene Composer 仍只生成实体场景，不生成关卡场景本身（竞技场宿主仍是手写场景）。
- 奖励经济不存在（只有击杀计数 + 胜负结算），未发明货币/掉落机制。
- 死亡表现即「按既有规则移除」（`queue_free`），无死亡动画/终结状态机可验证。
- 其他手写场景（EnemyBasic.tscn / Boss / EliteEnemy 等）未重新生成；它们的
  追击根归属与新规则一致与否由静态闸门（声明根实例时）与探针分别把关。
- 多阶段 `on_start` Boss 没有宿主实例，故不参与 composition_plan 的实例交叉校验；
  这是显式策略，不是遗漏。
- 阶段类型目前只有 clear_enemies / defeat_boss / complete_level；没有血量阈值、
  限时阶段或通用状态机（按任务范围刻意保持最小）。

## Current Capabilities

### 可复用 Feature（Features/，12 个）

- player_movement、health、health_bar、contact_damage、heal_pickup
- collect_pickup、condition_gate、trigger_switch、openable_door
- chase_movement、moving_platform、stun

### 验证场景（Scenes/ + Tests/）

- 场景组合实验：survival_arena、escape_room、boss_challenge、timed_combat_arena、interrupt_range、stun_training、siege_gate 等
- 对应集成测试位于 Tests/（test_siege_gate.gd、test_timed_combat_arena.gd 等）

## Round 8 结论（详见 CURRENT_TASK.md）

多机制汇聚于同一实体：各 Feature 自有状态 + 公开行为接口，Scene Glue 只做事件连接与路由，不引入跨 Feature 仲裁器。

## Round 9 结论（Gameplay Loop Composer，详见 DECISIONS.md AD-009）

自然语言 → Gameplay Blueprint（entity/scene 复用 + systems + loop）→ Entity/Scene 生成 → check_gameplay → 循环测试：多实体玩法;i循环全链机读化。跨实体流程用 System Registry 描述（Systems/*/system.yaml），不实现 Manager。

## Round 10 / Phase 1.6 结论（Runtime Playtest & Self-Repair，详见 DECISIONS.md AD-010）

静态验证通过 ≠ 项目能跑。新增 Runtime Correctness 层：真实启动 Godot 运行 Scene，观测事实
（exit_code / duration / stdout / stderr / parsed events）→ 诊断（12 类 classification + likely_cause
+ related feature/scene + confidence）→ 修复计划（安全边界硬约束）→ 最小修复（单点字面量替换）→
静态验证 → 重跑；修复无效或引入新错误自动回滚，最多 max_repair_attempts 次。
Validator 增加第 5 阶段（check_runtime.py，只判定不修复），Validator 本身仍只做静态验证。

## Framework

- 入口：AI_ENTRY.md → .ai/config/agent.yaml → skill-registry.yaml
- Validator：.ai/tools/validator/validate.py（仅按需执行）；Runtime Validation（第 5 阶段）：
  .ai/tools/validator/check_runtime.py
- Runtime Playtest：.ai/tools/runtime/（run_scene / run_project / capture_output / runtime_result /
  diagnose_runtime / repair_plan / repair_engine / self_repair）；契约 .ai/config/runtime-playtest.yaml
- 决策记录：.ai/memory/DECISIONS.md（AD-001 ~ AD-010）

## Test Status（最近一次全量验证，Phase 1.24 时点）

- 统一入口 `python .ai/tools/run_tests.py`（最终验证，2026-10-18）：**79 项中 78 PASS
  （exit 1）**——唯一失败 `test_cross_layer_contract.py` 为**环境删除守卫终止**
  （SAFE_DELETE_BULK_CONFIRM_REQUIRED：同一命令内工作区删除达 50 次上限后终止进程，
  恰逢其自清理阶段；其 C1–C9 契约断言全部 PASS，独立运行 4 次均 66/66）。分段运行
  （每段独立命令 = 独立删除预算）**全部通过**：--godot-only 36/36、asset_registry
  11/11、e2e 1/1、feature_registry 4/4、gameplay_planner 2/2、runtime 4/4、
  scene_composer 17/17、validator 7/7。根因与分段命令清单见 run_tests.py 文档头。
- E2E 独立运行：`python .ai/tools/e2e/tests/test_end_to_end_generation.py` →
  exit 0，**171 项 PASS**（T5a–T5d：四种编排模式 trace 与各自批准基线逐事件比较全过；
  T8/T9 差异注入 REGRESSION + exit 1；T13 基线不可被运行改写；T14 无残留）。
- 黄金基线专项：`validator/tests/test_trace_baselines.py` → exit 0（**57 项**，
  含 Phase 1.24 的 U49–U56 审批安全：篡改/替换/无指纹/追加事件全部拒绝且基线不动）；
  回放器单测 `test_orchestration_trace.py` → exit 0（44 项）。
- Godot 专项（适配层转发器与 holdout CLI 改动后复跑，全部 exit 0）：
  test_orchestration_trace / test_boss_orchestration / test_boss_challenge /
  test_survival_arena / test_timed_combat_arena / test_generic_level_orchestration /
  test_elite_enemy。
- 其他套件独立运行（全部 exit 0）：composite（17）、binding_scope（29）、
  binding_schema_checks（14）、unified_validator（36）、cross_layer_contract（66）、
  level_planner（134，含 holdout CLI）、plan_generator（25）；`check_level.py`
  两个发布配置 PASS。
- Framework Validator：PASS（0 error / 17 warning；与基线逐项相同）。
- 真实 Godot：4.7.stable.official.5b4e0cb0f（headless）；T4 四场景沙箱捕获、
  P14–P18、G8/G9/G10a、L11/L16–L17 均以真实二进制执行。

> 注意：本文件记录「最后一次验证时的快照」。如需最新逐项状态，以 git log 与 Tests/ 为准。
