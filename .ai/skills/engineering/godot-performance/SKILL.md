# Skill Identity

## Skill ID

godot-performance

## Skill Name

Godot Performance

## Version

1.0

## Category

engineering

# Registry Metadata

本章节是本 Skill 的 Canonical Metadata。
Registry 仅索引本 Skill，不重复维护这些字段。

## Load Policy

conditional

## Dependencies

### Required

[]

### Related

[]

## Ownership

负责本 Skill 所定义的 Godot Performance 能力边界，不负责其他 Skill 的专属实现。

# Description

负责性能分析、性能验证与优化相关工程流程。

# Purpose

为 Agent 提供明确、可发现、可验证的 Godot Performance 能力边界。

# Responsibility

## 负责

- 定义本领域的结构、规则与工作流程。
- 在任务涉及本领域时提供实施与验证依据。

## 不负责

- 不接管其他 Skill 的专属职责。
- 不修改 Framework、Registry 或其他 Skill 的 Canonical Metadata。

# Trigger Conditions

- 用户任务明确涉及 Godot Performance。
- 其他 Skill 的工作流明确需要本领域能力。
- 需要检查或验证本领域相关修改。

# Input Contract

- 当前任务目标。
- 相关项目 Context。
- 涉及本领域的现有文件、结构或约束。

# Workflow

1. 理解任务目标与当前 Context。
2. 检查相关项目结构与现有实现。
3. 按本 Skill 的责任边界制定或执行修改。
4. 验证修改结果是否符合本 Skill 的约束。
5. 输出结果与验证状态。

# Output Contract

- 清晰说明执行内容。
- 列出关键修改与验证结果。
- 不输出超出本 Skill 责任边界的决策。

# Validation

## Validation Method

检查相关文件、结构、规则和任务结果是否满足本 Skill 的责任边界。

## Success Criteria

- 修改符合本 Skill 的规则。
- 未破坏其他 Skill 的责任边界。
- 验证结果可复现。

## Status Update

报告成功、失败、未完成项及其原因。

# Failure Handling

定义：

- 识别本 Skill 执行中的错误、缺失输入或验证失败。
- 在不越权的前提下采取可逆回退或停止操作。
- 涉及职责边界、核心架构或破坏性变更时请求用户确认。


# References

- .ai/config/SKILL_TEMPLATE.md
- .ai/config/skill-schema.yaml

# Examples

当任务涉及 Godot Performance 时，先读取本 Skill，再根据 Workflow 执行与验证。
