# 项目长期记忆（Godot_v4.7-stable/game）

## 架构事实（Phase 1.14 起）

- 关卡编排的**唯一通用实现**在 `Orchestration/`：`level_config.gd`（LevelConfig，
  解析+校验+归一化）与 `level_orchestrator.gd`（LevelOrchestrator，运行时）。
  场景脚本（`Scenes/*.gd`）只做适配层：解析自身节点引用、注入编排器、转发信号到 HUD。
  **禁止**在场景脚本里再写一套波次/生成/计数/出口/胜负逻辑，也禁止在 Orchestration/
  里写任何 NodePath 或场景名。
- 两种编排模式（schema `level_orchestration` v2）：`waves`（顺序波次，TimedCombatArena）
  与 `holdout`（持续生成+生存胜利，SurvivalArena）。v1 配置 = 遗留 waves，仍有效。
- 关卡配置校验有两个镜像实现（同规则集）：Python `gameplay_planner/level_planner.py::
  validate_level`（设计期，producer/validator 共用）与 GDScript `LevelConfig`（运行期）。
  改规则必须同改两处 + `.ai/context/level_schema.yaml`。
- 运行时错误诊断契约：`get_config_errors()` 消息形如
  `<配置文件>: <JSON字段路径>: <说明>`；`get_diagnostics()` 另给
  {stage, phase, config_path, mode, errors, consumer_scene}。
- 敌人管理接口（编排层依赖）：实体根 CharacterBody2D 可接收 `target_path`、子节点
  `Health` 命名约定、由编排层 `add_to_group("enemies")`。
- holdout 首生成时间规则：delay>0 → 到点即第一波、随后每 interval；delay=0 → 首个也在
  interval 后。

## 环境/工具注意

- 新增 `class_name` 脚本后必须跑一次 `godot --headless --path . --import` 注册全局类。
- 统一测试入口：`python .ai/tools/run_tests.py`（Godot `Tests/test_*.gd` +
  Python `.ai/tools/**/tests/test_*.py`，单测超时 Godot 120s / Python 300s）。
- Godot 二进制：`F:/Godot_v4.7-stable/Godot_v4.7-stable_win64_console.exe`。
- validate.py 既有基线：0 error / 17 warning（17 条均为 Asset Manifest 小写路径不符）。

## Code Library（.ai/skills/foundation/godot-gdscript，2026-10-27 起）

- 分类：`examples/` = Agent 自制示例；`code_library/` = GitHub 收集
  （sources/ 原始 + references/ 蒸馏 + catalog.yaml + INDEX.md；references 与
  sources 带 .gdignore，Godot 不导入）。
- 工具 `tools/github_collector.py`：search/fetch/catalog/check/reindex；
  GITHUB_TOKEN 可选提额；许可证白名单（MIT/BSD/CC0/Apache 等），GPL/未知跳过；
  tarball 走 codeload 不占 API 配额。
- 首批 12 仓库：godot-demo-projects、dialogic、dialogue_manager、phantom-camera、
  beehave、open-rpg、statecharts、steering-ai-framework、Metroidvania-System、
  两套 GameTemplate、Kenney City Builder。1810 条目 / 1454 parse OK / 0 FAIL。
- Agent 检索入口：先读 code_library/INDEX.md，再查 catalog.yaml；片段是学习参考，
  落地必须适配项目约定（class_name 冲突、Health 节点、enemies 组）。
