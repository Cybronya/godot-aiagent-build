# 当前任务

> 历史实验档案（Round 5 → 8 全部结论，含 Siege Gate 状态所有权、Round 7 Do Not Reuse、
> 测试证据与后续处置记录）已归档至 `.ai/memory/HISTORY.md`。

## 当前状态

Phase 1.6（Runtime Playtest & Self-Repair）已完成并沉淀（AD-010）：静态 Validator 之后新增 Runtime
Correctness 层（`.ai/tools/runtime/`：Runtime Runner → runtime_result → Runtime Diagnosis →
Repair Plan → Self Repair → 复验），Validator 增加第 5 阶段 `check_runtime.py`（只判定，不修复）；
自动修复刻意狭窄（仅 node_not_found + 唯一可定位字面量），且修复无效/引入新错误必须回滚；
运行契约与安全边界集中在 `.ai/config/runtime-playtest.yaml`；新增 runtime-playtest Skill
（category: quality，第 20 个 Skill）；AI_ENTRY.md 只增加「Runtime failure → runtime-playtest Skill」路由。
验证：test_runtime_playtest.py PASS（Test1 正常场景 / Test2 node_not_found / Test3 script_error /
Test4 TIMEOUT + 分类与解析事实 + Validator 第 5 阶段）、test_self_repair.py PASS（Test5 单次自修
FAIL→PASS + 多轮尝试 + 回滚 + 不可修复不动项目 + 安全边界）、Godot 全量回归 PASS、
Validator PASS（20 Skills / 6 categories，0 errors / 0 warnings）。

Round 9（Phase 1.5 Gameplay Loop Composer）已完成并沉淀（AD-009）。Feature 能力链已完成四级：

4. **Gameplay Loop Composer**（AD-009）：需求文本 → gameplay_planner（requirement_parser /
   blueprint_generator）→ Gameplay Blueprint（survival_game.yaml：entity/scene 复用/systems/
   loop）+ Entity Relationship Graph（entity_graph.json，Enemy-[attack]->Player）+ System Registry
   （Systems/*/system.yaml，跨实体流程契约）+ check_gameplay.py（实体场景/能力满足/循环闭合）
   + gameplay-planner Skill。

Round 8 已完成并沉淀（commit `ae6e4d9`）。Feature 能力链已完成三级：

1. **Metadata Pipeline**（AD-006）：12 个 feature.yaml → 索引生成器
   （build_feature_index.py → feature_index.json v2）→ Discovery Tool →
   Metadata Validator（已集成 validate.py 执行链）。
2. **Composition Planner**（AD-007）：feature.yaml relations 节 + Feature Graph
   （feature_graph.json，12 节点 27 边）+ compose_features.py（Discovery → 关系图 →
   评分 → Entity Blueprint）+ check_composition 组合检查 + feature-composition Skill。
3. **Scene Composer**（AD-008）：Feature Scene Template（12 个 template.yaml）+
   scene_composer 工具链（composer/builder/resolver/validator）+
   check_scene_composition.py + test_generator（生成 Tests/test_<id>.gd）+
   scene-composer Skill（18 Skills）。

验证：test_feature_pipeline PASS + test_composition.py PASS（21 项）+
test_scene_composer.py PASS（31 项：三用例场景生成/缺前置拒绝/全链校验）+
test_gameplay_planner.py PASS；端到端：planner "create enemy survival game" →
survival_game.yaml → scene_composer 重建 Scenes/Enemy.tscn（实例化根覆写，后续 SurvivalArena
循环 Godot 生存循环测试 PASS）→ check_gameplay PASS；Godot 全量回归 30/30 PASS；
Validator PASS（0 errors / 0 warnings，19 Skills / 12 Feature metadata）。
职责定位：Discovery/Composition 输出仅为 recommendation/blueprint，Reuse/Build
决策归 feature-development.md §3，实现归 feature-development.md + 相关 Skill。

## 下一阶段方向

路线图已记录于 `.ai/context/ROADMAP.md`（P0：Feature Registry / Game Design Skill / Scene Composer；
P1：Runtime Debug Agent / Asset Intelligence；P2：Feature Migration System / Multi-Agent Workflow）。
P0-1 Feature Registry（Metadata Pipeline + Composition Planner）与
P0-3 Scene Composer 与 P1 前置的 Gameplay Loop Composer 均已完成；下一任务候选：P0-2
Game Design Skill、提交成果（Phase 1.5 全链成果待 commit），
或直接串联「自然语言 → Gameplay Blueprint → 全部实体场景 → 验证」的多实体生成演示。

P1-4 Runtime Debug Agent 已由 Phase 1.6（AD-010）覆盖（运行期错误捕获 → 定位 → 修复 → 复验闭环）。

## AD 候选（挂起，观察中）

当多个触发路径作用于同一个状态域时，应优先由该状态的 Feature 定义冲突语义，而不是让 Scene Glue 仲裁。
与既有 AD（002/005）方向一致，暂不升格；待出现第一个需要在 Glue 层仲裁的真实案例再评估。
