# Godot AI Agent Build - Agent 上手指南

> 本文件是**背景与理念**文档（为什么这样设计）；机器入口协议见 `AI_ENTRY.md`（去哪加载什么）。
> 项目进度类信息**不在本文件维护**——见 `.ai/context/WORK_STATE.md` 与 `.ai/memory/HISTORY.md`。

## 1. 项目定位

本项目不是普通的 Godot 游戏，而是一个实验框架：

> 探索 AI Agent 如何理解、扩展、验证 Godot 项目。

核心目标：让 Agent 具备类似专业 Godot 开发者的能力——理解已有架构、复用已有 Feature、安全修改、自动验证，而无需人工每次重新解释项目结构。

核心理念：**先理解，再修改。**

## 2. 核心概念

### Skill（Agent 能力）

- 位置：`.ai/skills/**/SKILL.md`，经 `.ai/config/skill-registry.yaml` 发现
- 定义 Agent 如何完成某类工作（工作规则、执行流程、相关知识）
- **Skill 不是游戏功能**

### Feature（游戏可复用模块）

- 位置：`Features/<name>/`（脚本 + 场景 + `README.md` + 测试）
- 必须有明确职责、低耦合、可验证
- 开发时**优先复用已有 Feature**，而不是创建重复实现

### Test Scene（验证）

- 位置：`Features/*/test_*.gd`（组件级）与 `Tests/`（场景级集成）
- 一个 Feature 如果没有 Validation，视为不完整能力
- 统一测试入口：`python .ai/tools/run_tests.py`（全部测试一键运行）

### addons/godot_mcp（第三方工具通道）

- Godot 编辑器 MCP 插件，是 Agent 与引擎交互的工具通道（**第三方依赖**）
- 按第三方组件对待：不在本项目 Feature/Skill 体系内演化，不修改其内部实现
- 实验中涉及它的只有"使用"与"版本升级"（见 git 历史的 addon 升级提交）

## 3. 当前能力快照

- 可复用 Feature（12 个）：player_movement、health、health_bar、contact_damage、heal_pickup、collect_pickup、condition_gate、trigger_switch、openable_door、chase_movement、moving_platform、stun
- 实验进展：MCP Round 5 → 8 已完成（新 Feature 边界 → 跨场景复用 → 组合与 Do Not Reuse → 多机制汇聚/状态所有权）
- 详细清单与最新验证结果：`.ai/context/WORK_STATE.md`；实验档案：`.ai/memory/HISTORY.md`

> 注：Feature 列表会增长，以 `Features/` 目录实际内容为准；本节仅作快速概览。

## 4. 工作规则

### Rule 1：不要立即修改代码

```
Analyze → Understand → Plan → Modify → Validate
```

### Rule 2：优先复用已有能力

新增 Feature 前，先检查 Existing Features / Skills / Components / Tests，避免重复实现。

### Rule 3：保持 State Ownership

一个系统只负责自己的 State。冲突语义（如长盖短、幂等、死亡守卫）内置于拥有该状态的 Feature，由其公开接口表达；Scene Glue 只做事件连接与路由，不做状态仲裁。

错误方式：`Player.gd` 同时负责 Movement / Damage / Stun / Pickup / Inventory。

正确方式：

```
Player
    ├── Movement Component
    ├── Stun Component
    ├── Pickup Component
    └── Inventory Component
```

## 5. 修改项目之前，必须回答

1. 当前需求解决什么问题？
2. 是否已有 Feature 可以复用？
3. 会影响哪些 System？
4. 如何进行 Validation？
5. 修改后架构是否仍然清晰？

## 6. 成功标准

用户提出一个新的 Gameplay Mechanic 需求时，Agent 可以：理解已有架构 → 分析 Feature 组合 → 安全修改 → 自动验证——全程无需人工重新解释项目结构。

## 7. 最终指导

你不是在维护一个普通 Godot 项目，而是在参与构建 AI-driven Godot Development Framework。开发重点不是快速写代码，而是建立让 Agent 能够理解、扩展并长期维护 Godot 项目的能力。
