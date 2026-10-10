# Work State

当前工程状态。（更新于 Gameplay Loop Composer / AD-009 之后，待 commit）

## Project Stage

Feature-based Agent Development —— Gameplay Loop Composer（Phase 1.5，AD-009）已完成。

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

## Framework

- 入口：AI_ENTRY.md → .ai/config/agent.yaml → skill-registry.yaml
- Validator：.ai/tools/validator/validate.py（仅按需执行）
- 决策记录：.ai/memory/DECISIONS.md（AD-001 ~ AD-003）

## Test Status（最近一次全量验证，AD-009 时点）

- Framework Validator：PASS（0 errors / 0 warnings，19 Skills）
- Python 层：test_feature_pipeline / test_composition / test_scene_composer / test_gameplay_planner 全 PASS
- CLI 端到端：planner → survival_game.yaml → scene_composer(Enemy.tscn) → check_gameplay PASS
- Godot 全量回归：30/30 PASS（含 SurvivalArena 生存循环集成测试）

> 注意：本文件记录「最后一次验证时的快照」。如需最新逐项状态，以 git log 与 Tests/ 为准。
