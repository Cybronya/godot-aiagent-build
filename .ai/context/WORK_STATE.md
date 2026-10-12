# Work State

当前工程状态。（更新于 Runtime Playtest & Self-Repair / AD-010 之后，待 commit）

## Project Stage

Feature-based Agent Development —— Runtime Playtest & Self-Repair（Phase 1.6，AD-010）已完成，
Gameplay Loop Composer（Phase 1.5，AD-009）已完成。

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

## Test Status（最近一次全量验证，AD-009 时点）

- Framework Validator：PASS（0 errors / 0 warnings，20 Skills / 6 categories）
- Python 层：test_feature_pipeline / test_composition / test_scene_composer / test_gameplay_planner 全 PASS
- CLI 端到端：planner → survival_game.yaml → scene_composer(Enemy.tscn) → check_gameplay PASS
- Godot 全量回归：30/30 PASS（含 SurvivalArena 生存循环集成测试）
- Runtime 层：test_runtime_playtest.py PASS、test_self_repair.py PASS（修复测试在临时项目副本上运行）

> 注意：本文件记录「最后一次验证时的快照」。如需最新逐项状态，以 git log 与 Tests/ 为准。
