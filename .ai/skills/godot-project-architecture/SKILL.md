# SKILL: godot-project-architecture

# Skill Identity
- Skill ID: godot-project-architecture
- Skill Name: Godot Project Architecture
- Version: 1.0
- Category: architecture

# Registry Metadata
与 .ai/registry/skill_registry.yaml 保持一致。

## Load Policy
conditional

## Dependencies
required:
- godot-development-standard

# Ownership
- project_architecture
- module_boundaries
- dependency_graph
- system_placement
- autoload_architecture
- feature_placement
- architecture_refactoring

# Purpose
负责 Godot 项目的架构设计、模块边界、系统归属、Feature 放置、依赖关系、Autoload 决策与架构重构。

核心问题是：

> 一个功能、系统、模块或数据应该属于哪里，以及它们之间应该如何依赖。

godot-development-standard 负责“项目应该遵守什么规范”；本 Skill 负责“项目应该如何组织和演化”。

# Responsibility

## 负责
- 分析现有项目架构
- 定义 Module / System 边界
- 判断新 Feature 所属模块
- 定义状态与数据 Owner
- 设计依赖方向
- 检查循环依赖
- 判断 Autoload 是否合理
- 设计跨模块通信边界
- 设计架构重构方案
- 输出长期可复用的 Architecture Decision

## 不负责
- 文件/Node/Script 命名规范
- 具体 GDScript 实现
- 具体 Scene Node 设计
- 角色、玩法、UI、音频等系统的具体实现
- 美术资源制作
- 性能优化
- 构建发布

# Architecture Model
项目架构至少区分：
- Project
- Module
- System
- Feature
- Scene
- Script
- Resource

Module 是架构概念，不等于目录；目录是物理组织方式。

# Core Principles

## 1. Ownership First
每个核心状态与业务能力必须有明确 Owner。

## 2. Single Responsibility
Module / System 应有清晰职责；多个独立变化原因出现时再考虑拆分。

## 3. High Cohesion / Low Coupling
相关逻辑尽量聚合，跨模块依赖保持最小。

## 4. Explicit Dependency Direction
默认允许 Feature -> System -> Foundation 一类稳定方向；禁止循环依赖。

## 5. Local Before Global
只服务一个领域的能力优先留在该领域，不因为“以后可能复用”提前全局化。

## 6. Stable Boundaries
跨模块通过明确 API、Signals/Events 或 Data/Resource Contract 通信，不直接修改内部状态。

## 7. Stable Data Ownership
一个核心运行时状态只有一个写入 Owner；其他模块通过接口访问。

## 8. Architecture Before Implementation
新增系统/大型 Feature 在编码前先确定 Owner、Module、Dependencies、Data Ownership、Autoload。

# Trigger Conditions
- 创建 Godot 项目
- 添加新 Module
- 添加新 System
- 添加大型 Feature
- 修改模块职责
- 修改系统依赖
- 添加/删除/修改 Autoload
- 跨模块共享状态
- 大规模文件迁移
- 架构重构
- 项目架构检查
- 发现循环依赖或职责漂移

# Input Contract

尽可能提供：
- Godot 版本
- 项目类型
- 当前目录结构
- 当前 Module / System
- Scene / Script / Resource 状态
- 当前任务
- 已确认的架构规则

优先读取：
1. godot-development-standard
2. 项目已有架构文档
3. 已确认 Memory
4. 当前代码与目录结构

信息不足时，不得凭空设计大型架构；应先基于现有结构分析并提出最小必要问题。

# Workflow

## 1. Understand Task
确定目标、修改范围以及是否改变模块关系。

## 2. Load Standards
读取 development-standard 与本 Skill 相关 references。

## 3. Analyze Existing Architecture
检查目录、模块、Scene/Script/Resource 归属、Autoload、依赖关系和共享服务。

## 4. Determine Ownership
明确：
- 谁拥有状态
- 谁拥有行为
- 谁创建/销毁
- 谁可以读取
- 谁可以修改

## 5. Determine Placement
优先选择：
1. 现有正确 Module
2. 现有 System
3. 新 Module
4. Shared/Foundation

只有确实跨领域且职责稳定的能力才进入 Shared/Foundation。

## 6. Analyze Dependencies
建立有向依赖图，检查反向依赖、循环、过宽职责和不必要共享依赖。

## 7. Evaluate Autoload
回答：
1. 是否必须跨 Scene 持续存在？
2. 是否必须唯一？
3. 是否是真正的项目级服务？
4. 是否可以由明确的上层 Owner 管理？

局部 Owner 能解决时优先不用 Autoload。

## 8. Produce Architecture Decision
实现前明确 Feature、Owner、Module、Responsibilities、Dependencies、Data Ownership、Autoload、File Placement、Risks。

## 9. Execute
仅在架构决策明确且权限允许时修改项目。

## 10. Validate
按 validation-mode 选择 Quick Check 或 Full Review。

## 11. Preserve Decision
稳定的架构决定进入项目文档或 Memory，避免后续重复设计。

# Output Contract
必须包含：
- Architecture Decision
- Module Changes
- Dependency Changes
- Autoload Changes
- File Placement
- Validation Result
- Remaining Issues

# Validation

## Quick Check
适用于单模块 Feature、小型依赖修改、局部架构调整。

检查：
- Owner
- Placement
- Dependencies
- Autoload
- Standard compliance

## Full Review
适用于新 Module、新 System、跨模块 Feature、Autoload 修改、大型重构。

检查：
- Project Structure
- Module Boundaries
- Dependency Graph
- Data Ownership
- Scene / Script / Resource ownership
- Autoload
- Cross-module communication
- Existing architecture decisions
- Refactor safety

## Success Criteria
PASS 必须满足：
- 功能有明确 Owner
- 模块职责清晰
- 依赖方向明确
- 无未经确认的循环依赖
- 没有不必要的全局状态
- 不破坏已有架构决策
- 文件位置符合 Development Standard

# References
- architecture-principles.md
- project-structure.md
- module-boundaries.md
- dependency-rules.md
- autoload-rules.md
- feature-placement.md
- refactor-policy.md
- validation-mode.md

# Examples
- good-architecture-example.md
- bad-architecture-example.md
- feature-placement-example.md

# Templates
- project-architecture-template.md
- module-template.md

# Collaboration

## Required
- godot-development-standard

## Related
- godot-scene-system
- godot-gdscript
- godot-character-system
- godot-gameplay-system
- godot-ui-system
- godot-data-resource
- godot-debug-testing
- godot-performance
- godot-build-release

本 Skill 决定“功能应该属于哪里”；专业 Skill 决定“具体怎么实现”。

# Tool Usage
可使用文件扫描、读取、修改、Scene 分析、Script 分析、Resource 分析、依赖关系分析。
未来 Godot MCP 可查询 Scene Tree、Node、Autoload、Project Settings、Script references。

# Memory Interaction

## Read
- 已确认 Module 边界
- 长期架构决策
- Autoload 决策
- 依赖方向
- 数据所有权

## Write
稳定决策可保存：
- Module ownership
- System boundaries
- Dependency rules
- Autoload decisions
- Feature placement

不保存临时方案、测试结果和未确认猜测。

# Failure Handling
- 信息不足：先分析现有结构，无法安全判断 Owner 时请求必要信息。
- 架构冲突：遵守 rule-priority.md，不静默覆盖高优先级决定。
- 循环依赖：标记 WARNING/FAIL，提出删除依赖、移动职责、提取稳定接口等方案。
- 高风险重构：先给迁移方案，必要时请求确认。

# Permission Model

允许：
- 分析架构
- 输出架构方案
- 创建新 Module 目录
- 添加架构文档
- 在授权范围内调整依赖

需要确认：
- 删除核心 Module
- 修改核心 Autoload
- 大规模迁移
- 改变已确认的核心架构

禁止：
- 为方便实现绕过模块边界
- 未确认删除核心逻辑
- 用 Autoload 掩盖所有权不清
- 修改其他 Skill 的职责定义

# Architecture Decision Record

推荐格式：

```yaml
architecture_decision:
  feature: inventory
  owner: player
  module: Gameplay/Inventory
  responsibilities:
    - manage inventory state
    - expose inventory queries
  dependencies:
    - Character
    - Data
  data_owner: inventory
  autoload: false
  communication:
    - direct_api
  reason:
    - player-owned gameplay state
    - no project-wide lifetime requirement
```

Architecture Decision 是长期架构记忆的主要载体。

# Skill Completion Report

```text
Skill:

任务:

Architecture Decision:

Module Changes:

Dependency Changes:

Autoload Changes:

File Placement:

验证结果:

状态:

后续建议:
```

# Notes
本 Skill 只解决项目架构问题，不替代具体系统实现 Skill。
版本号保持 1.0；升级时必须同步 Registry。
