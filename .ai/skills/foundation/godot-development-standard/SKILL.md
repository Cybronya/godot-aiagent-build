# SKILL: godot-development-standard

# Skill Identity

## Skill ID

godot-development-standard

## Skill Name

Godot Development Standard

## Version

1.0

## Category

foundation

# Registry Metadata

与 skill_registry.yaml 保持一致。

## Load Policy

required

## Dependencies

required: []

## Ownership

- project_structure
- naming_rules
- folder_rules
- development_standard

# Description

负责 Godot 项目开发规范、文件结构、命名规则、Scene、Script 和 Resource 组织的一致性管理。

------------------------------------------------------------------------

# Purpose

Godot 项目开发规范管理 Skill。

负责指导 AI Agent 在 Godot 项目开发过程中遵守统一的工程规范，包括文件结构、命名规则、Scene 组织、Script 组织、资源管理以及代码规范。

该 Skill 是 Godot Agent 所有开发类 Skill 的基础规范能力。

存在原因：

AI 在自动开发过程中容易产生：

- 文件位置混乱
- 命名不统一
- 重复创建脚本
- Scene 结构不可维护
- 资源管理混乱
- 不符合长期项目扩展要求

因此需要一个独立 Skill，在所有开发任务开始前和完成后，对项目规范进行检查和维护。

# Responsibility

这个 Skill 是：

Godot Agent 的工程规范管理能力。

它负责约束 AI 在 Godot 项目中的开发行为，使生成的文件、代码、Scene 和资源符合统一标准。

该 Skill 类似项目技术负责人制定的开发规范。

## 负责

- 分析当前项目结构
- 建议合理目录组织
- 检查文件命名
- 检查 Scene 命名
- 检查 Node 命名
- 检查 Script 命名
- 检查 Resource 存放位置
- 维护项目一致性
- 提醒其他 Skill 遵守项目规范

## 不负责

- 不设计具体游戏玩法
- 不实现游戏系统
- 不编写核心功能代码
- 不决定游戏架构方案
- 不负责美术资源制作
- 不负责性能优化
- 不替代其他专业 Skill

# Trigger Conditions

以下情况触发：

## 项目初始化

例如：

- 创建新 Godot 项目
- 建立项目目录结构

## 文件创建前

例如：

- 创建新的 Script
- 创建新的 Scene
- 创建新的 Resource

## 项目修改前

例如：

- 添加新系统
- 重构已有功能

## 项目检查

例如：

- 检查项目是否符合规范
- 整理混乱项目结构

# Input Contract

需要输入：

## 项目信息

包括：

- Godot 版本
- 项目类型
- 当前目录结构

## 当前任务

例如：

- 添加玩家系统
- 制作 UI
- 创建敌人

## 当前文件状态

包括：

- Scene 列表
- Script 列表
- Resource 列表

如果信息不足：

必须询问：

- 当前项目结构
- 目标功能
- 现有规范文件

# Workflow

标准流程：

## 1. 理解任务

分析：

- 用户目标
- 当前修改范围
- 是否涉及项目结构变化

## 2. 检查 Context 与 Memory

检查：

- 当前开发状态
- 当前修改任务
- 已存在规范

读取 Memory：

- 项目长期规则
- 已确定技术方案
- 命名约定

## 3. 读取 References

按需加载 references 目录中的规范文件（见下方 References 章节）。

## 4. 执行 Skill 规则

- 分析项目规范：文件位置、命名方式、Scene 结构、Script 关系
- 提供规范建议：发现问题给出修改方案、风险说明、推荐结构
- 执行规范检查：验证新增文件符合规则、修改没有破坏结构

## 5. 验证结果

- 按 validation-mode.md 选择检查深度
- 按 compliance-report.md 格式输出检查结果

## 6. 更新状态

输出：

- 检查结果
- 修改记录
- 遗留问题

# Output Contract

输出必须包含：

## 修改内容

说明：

- 创建了什么
- 修改了什么
- 删除了什么

## 修改文件

列出：

- 文件路径
- 文件用途

## 检查结果

包括：

- 是否符合规范
- 是否存在问题

## 遗留问题

说明：

- 未解决问题
- 后续建议

# Validation

## Validation Method

按 validation-mode.md 执行：

- Quick Check：命名、文件位置、基础规范
- Full Review：项目结构、模块关系、Scene 组织、Script 组织、Resource 管理

## Success Criteria

- 新增文件符合 naming-rules.md 与 folder-structure.md
- 修改没有破坏现有结构
- 无未确认的结构性变更

## Status Update

按 compliance-report.md 输出：

- PASS
- WARNING
- FAIL

# References

目录：references/

按需加载：

## rule-source.md / rule-priority.md

规范来源与优先级。规范冲突或需要判断「项目已有规范 vs Skill 默认规范」时必读。

## folder-structure.md

创建目录、调整项目结构时加载。

## naming-rules.md

创建或重命名任何文件时加载。

## scene-rules.md

创建或修改 Scene 时加载。

## script-rules.md

创建或修改 Script 时加载。

## resource-rules.md

涉及 Resource 数据文件时加载。

## validation-mode.md

执行规范检查前，选择检查深度时加载。

## compliance-report.md

输出检查报告时加载。

## refactor-policy.md

涉及移动、重命名、删除已有文件或目录时必读。

# Examples

目录：examples/

- good-project-example.md：符合规范的项目结构示例
- bad-project-example.md：违反规范的反例

# Templates

目录：templates/

- folder-structure-template.md：目录结构模板
- scene-template.md：Scene 结构模板
- script-template.md：GDScript 代码模板（对齐 Godot 4.7 官方风格指南）

# Collaboration

## Dependencies

required: []

## Related Skills

以下 Skill 尚未注册，注册后建立正式关系：

- godot-project-architecture：项目整体架构设计
- godot-scene-system：Scene 结构规范
- godot-gdscript：Script 代码规范
- godot-debug-testing：修改后的验证

## Communication Rules

同级 Skill 默认互不修改职责。

Skill 之间通过：

- dependencies
- ownership

建立关系。

# Tool Usage

可能调用：

- 文件扫描工具
- 文件读取工具
- 文件修改工具
- 项目结构分析工具

如果未来接入 MCP：

可以调用：

- Godot 项目结构查询
- Scene 树查询
- Node 信息查询

# Memory Interaction

## Read

允许读取：

- 项目长期命名规则
- 项目目录规则
- 已确定技术方案

## Write

需要更新 Memory：

- 项目长期命名规则
- 项目目录规则
- 已确认开发规范

只更新 Context：

- 当前检查结果
- 当前临时修改

不保存：

- 一次性文件调整
- 临时测试结果

# Failure Handling

## 信息不足

处理：

要求用户提供：

- 项目结构
- 当前规范
- 修改目标

## 文件错误

处理：

- 检查路径
- 检查引用
- 提供修复方案

## 设计冲突

处理：

- 按 rule-priority.md 判断优先级
- 保留已有规范
- 提醒冲突原因
- 请求用户确认

## 发现违规结构

处理：

- 按 refactor-policy.md 执行
- 不直接大规模修改
- 提供迁移方案
- 等待确认

# Permission Model

允许修改：

- 文件夹结构
- 文件名称
- 规范文档
- 项目配置文件

禁止修改：

- 核心游戏逻辑代码
- 玩家数据
- 游戏资源内容
- 未确认的重要文件

需要确认：

- 修改核心架构
- 删除重要文件
- 修改 Registry

# Skill Completion Report

完成后输出：

``` text
Skill:

任务:

修改内容:

验证结果:

状态:

后续建议:
```

# Notes

本文件遵循 SKILL_TEMPLATE v2.1 与 skill-schema.yaml 的结构契约。

版本号保持 1.0，与 skill_registry.yaml 注册信息一致；如需升级版本号，必须同步更新 Registry.
