# Godot AI Agent Build - Agent Onboarding

# Godot AI Agent Build - Agent 上手指南

## 1. 项目身份（Project Identity）

项目名称：

```
godot-aiagent-build
```

项目类型：

```
Godot AI Agent Development Framework
```

---

## 项目定位

本项目不是一个普通的 Godot 游戏项目。

它是一个用于探索和构建：

> AI Agent 如何理解、扩展、验证 Godot 项目的开发框架。

项目目标：

让 AI Agent 具备类似专业 Godot 开发者的能力：

* 理解已有项目结构
* 分析现有架构
* 识别已有能力
* 复用已有 Feature
* 安全修改项目
* 自动执行 Validation
* 根据反馈持续优化

长期目标：

> 建立一个能够参与专业 Godot 游戏开发的架构感知型 AI Agent。

---

# 2. 核心理念（Core Philosophy）

本项目遵循：

```
AI 应该先理解，再修改。
```

Agent 不应该：

* 直接生成大量代码
* 随意修改核心逻辑
* 创建重复系统

正确流程：

```
理解项目
    |
    v
分析已有 Feature
    |
    v
制定修改方案
    |
    v
复用已有能力
    |
    v
执行修改
    |
    v
Validation
    |
    v
持续优化
```

---

# 3. 当前项目阶段（Current Stage）

当前开发方向：

```
Feature-based Agent Development
```

项目已经从：

```
AI 配置阶段
```

进入：

```
AI 理解并扩展 Godot 项目阶段
```

已经完成：

* AI Entry 系统
* Skill 组织体系
* Agent Workflow 基础
* Godot Feature 验证
* Feature 组合实验
* Asset 管理 Skill
* 自动 Validation 思路

当前重点：

```
Feature Knowledge System
```

目标：

让 Agent 理解：

* 当前项目有哪些 Feature
* Feature 之间的 Dependency
* Feature 是否可以组合
* 修改是否安全

---

# 4. 整体架构（Architecture Overview）

当前设计：

```
User Request

        |
        v

AI Agent

        |
        v

AI_ENTRY.md

        |
        v

Skill Registry

        |
        v

Skills

        |
        v

Feature Knowledge

        |
        v

Godot Project

        |
        v

Tests / Validation
```

---

# 5. 核心概念（Core Concepts）

## 5.1 Skill

Skill 是 Agent 的能力定义。

位置：

```
.ai/skills/
```

Skill 负责：

* 定义 Agent 能力
* 提供工作规则
* 描述执行流程
* 提供相关知识

例如：

```
godot-art-assets
```

注意：

Skill 不是游戏功能。

Skill 的作用：

告诉 Agent：

> 如何完成某类工作。

---

## 5.2 Feature

Feature 是游戏中的可复用功能模块。

例如：

```
Features/

- stun
- pickup
- moving_platform
- movement
```

Feature 应该：

* 有明确职责
* 保持低耦合
* 定义 Dependency
* 提供 Validation 方法

Agent 开发时：

优先：

```
Reuse Existing Feature
```

而不是：

```
Create Duplicate Feature
```

---

## 5.3 Test Scene

Test Scene 用于验证 Feature。

关系：

```
Feature

    |
    v

Test Scene

    |
    v

Validation Result
```

一个 Feature：

如果没有 Validation：

则认为是不完整能力。

---

# 6. 项目结构（Repository Structure）

```
.ai/

    Agent 配置

    Skills

    Tools

    Context


Features/

    可复用 Godot 功能模块


Scenes/

    Godot Scene


Tests/

    测试场景和实验


addons/

    Godot 扩展


AI_ENTRY.md

    Agent 入口


AGENT_ONBOARDING.md

    Agent 上手指南


README.md

    项目说明
```

---

# 7. Agent 工作规则（Agent Rules）

## Rule 1：不要立即修改代码

收到需求后：

必须先：

```
Analyze

↓

Understand

↓

Plan

↓

Modify
```

---

## Rule 2：优先复用已有能力

新增 Feature 前：

检查：

```
Existing Features

Existing Skills

Existing Components

Existing Tests
```

避免：

重复实现相同功能。

---

## Rule 3：保持 State Ownership

每个系统必须拥有清晰职责。

错误方式：

```
Player.gd

负责：

Movement

Damage

Stun

Pickup

Inventory
```

正确方式：

```
Player

    |
    + Movement Component

    + Stun Component

    + Pickup Component

    + Inventory Component
```

核心原则：

> 一个系统只负责自己的 State。

---

# 8. 当前已验证 Feature

## Stun Feature

作用：

提供可复用的中断 / 禁止行动机制。

验证方向：

* Feature Reuse
* State Ownership

---

## Pickup Feature

作用：

提供可复用交互系统。

验证方向：

* Interaction
* Feature Composition

---

## Moving Platform Feature

作用：

提供环境移动机制。

验证方向：

* Feature Composition
* System Interaction

---

# 9. 当前开发优先级（Development Priority）

## Phase 1：Feature Registry

目标：

让 Agent 可以查询已有能力。

例如：

用户：

```
增加 Dash 技能
```

Agent：

```
查询 Feature Registry

发现：

Movement System

Cooldown System

Animation System


组合解决方案
```

---

## Phase 2：Feature Dependency Graph

目标：

让 Agent 理解：

```
Feature 依赖关系

Feature 冲突关系

Feature 可组合关系
```

---

## Phase 3：Feature Composer Workflow

目标：

将：

```
User Request
```

转换为：

```
Feature Plan

+

Implementation Steps

+

Validation Steps
```

---

# 10. 修改项目之前

Agent 必须回答：

1. 当前需求解决什么问题？

2. 是否已有 Feature 可以复用？

3. 会影响哪些 System？

4. 如何进行 Validation？

5. 修改后架构是否仍然清晰？

---

# 11. 项目成功标准（Success Definition）

项目最终目标：

用户提出：

```
增加一个新的 Gameplay Mechanic
```

Agent 可以：

理解：

```
Existing Architecture
```

分析：

```
Feature Composition
```

执行：

```
Safe Modification
```

验证：

```
Automatic Validation
```

最终：

无需人工重新解释整个项目结构。

---

# 12. 给 Agent 的最终指导（Final Guidance）

你不是在维护一个普通 Godot 项目。

你正在参与构建：

```
AI-driven Godot Development Framework
```

开发重点不是：

```
快速写代码
```

而是：

```
建立让 Agent 能够理解、扩展、
并长期维护 Godot 项目的能力。
```
