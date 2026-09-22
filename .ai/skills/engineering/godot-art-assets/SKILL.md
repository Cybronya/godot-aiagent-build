# Skill Identity

## Skill ID

godot-art-assets

## Skill Name

Godot Art Assets

## Version

4.0

## Category

engineering

# Registry Metadata

## Load Policy

optional

## Dependencies

### Required

- None

### Related

- None

## Ownership

负责 Godot 项目艺术资源的目录规范、命名规范、metadata、扫描、review、检查和安全整理流程。

# Description

本 Skill 用于帮助 Agent 管理 Godot 项目的艺术资源（Art Assets），建立稳定、可预测、可验证的资源组织与审核流程。

# Purpose

解决新增、修改、删除、重复和待确认艺术资源的发现、分类、命名、metadata 与安全整理问题，同时避免在不确定时进行不可逆的自动判断。

# Responsibility

## 负责

- 标准艺术资源目录设计与检查
- 文件命名与路径规则
- 资源扫描与 manifest 状态比较
- metadata 与稳定资源 ID 规则
- review / pending 流程
- 动画帧连续性和重复资源检查
- 涉及 Godot 引用时的安全变更流程

## 不负责

- 图像分类、OCR、角色识别、场景识别或其他视觉语义判断
- 在语义不确定时替用户做最终分类决定
- 未检查 Godot 引用就批量移动、删除或重命名已有资源
- 替代其他 Skill 的架构、代码、场景或系统职责

# Trigger Conditions

当用户要求初始化、扫描、检查、整理、分类、审核、同步或维护 Godot 艺术资源时加载。

典型任务包括：

- 初始化艺术资源目录
- 扫描所有艺术资源
- 检查资源规范
- 查找新增、修改、删除或重复资源
- 生成待确认资源列表
- 更新资源 manifest
- 检查角色动画帧
- 检查资源命名问题

# Input Contract

输入应包含：

- 当前 Godot 项目路径
- 目标资源范围（如 assets/ 或指定子目录）
- 用户要求执行的操作
- 已有 manifest / review 数据（如存在）
- 涉及移动、重命名、删除时的变更范围

# Workflow

1. 读取本 Skill。
2. 检查项目与标准资源目录。
3. 读取 references、manifest 和已有 review 状态。
4. 执行 scan / check，收集路径、文件名、扩展名、大小、时间、hash、尺寸和路径/文件名 hints。
5. 比较 manifest，识别 new / changed / deleted / unchanged。
6. 对语义明确且规则稳定的资源执行安全组织；不确定资源进入 pending。
7. 涉及已有 Godot 引用时，先检查场景、资源、脚本路径引用，再执行移动、重命名或删除。
8. 变更后再次 scan / check。
9. 更新 manifest、review 状态和任务完成状态。

## Scanner Boundary

Scanner 不是视觉系统。它只根据路径、文件名、扩展名、文件尺寸和 hash 生成事实与 hints，不判断图像内容。

# Output Contract

完成任务后输出：

- 扫描或检查范围
- 发现的 new / changed / deleted / unchanged
- pending / review 项
- 执行的资源变更
- manifest / review 状态
- 最终验证结果

# Validation

## Validation Method

根据项目实际资源目录执行 scan / check，并在资源变更后重新扫描；涉及 Godot 引用时检查 .tscn、.tres、脚本路径和相关导入/引用。

## Success Criteria

- 标准目录存在或已明确记录例外
- 命名和路径符合规则
- 新增与变化资源已发现
- 不确定资源进入 pending
- manifest 状态一致
- 移动、重命名、删除经过引用安全检查
- 最终 scan / check 通过或明确报告剩余问题

## Status Update

- PASS：规则检查通过且没有未处理问题
- WARNING：存在需要人工确认的 pending / review 项，但流程本身有效
- FAIL：发现违反资源规则、manifest 不一致或存在未验证的高风险变更

# References

相关规范可放置于本 Skill 的 references/ 目录，包括：

- folder_structure.md
- naming.md
- metadata.md
- workflow.md
- godot_safety.md
- classification.md
- animation.md
- organization.md

# Examples

可在 examples/ 中放置资源扫描、review 和 manifest 示例。

# Templates

可在 templates/ 中放置资源 metadata、review 或 manifest 模板。

# Collaboration

## Dependencies

Canonical dependency data is defined in Registry Metadata → Dependencies。本章节不重复维护 dependency 数据。

## Related Skills

当前没有自动 Related 依赖。需要协作时根据任务边界调用对应 Skill，不把协作关系自动升级为依赖。

## Communication Rules

- 资源管理 Skill 只负责艺术资源领域。
- 资源语义不确定时必须进入 pending / review。
- 涉及架构、代码、场景或系统修改时，将对应职责交给相应 Skill。
- 不以“整理资源”为理由扩大变更范围。

# Tool Usage

如项目存在对应工具，可使用：

```bash
python .ai/tools/godot-art-assets/scan_assets.py init
python .ai/tools/godot-art-assets/scan_assets.py scan
python .ai/tools/godot-art-assets/scan_assets.py review
python .ai/tools/godot-art-assets/scan_assets.py apply
python .ai/tools/godot-art-assets/scan_assets.py sync
python .ai/tools/godot-art-assets/scan_assets.py check
python .ai/tools/godot-art-assets/scan_assets.py organize
```

工具调用必须遵守本 Skill 的权限与安全边界。

# Memory Interaction

## Read

允许读取：

- 长期项目资源组织规则
- 已确认的资源分类规则
- 长期有效的 Godot 资源安全约束

## Write

只保存长期有效的资源组织规则和人工确认结果，不保存临时扫描状态。

# Failure Handling

- 工具缺失或执行失败：停止依赖该工具的自动变更，并报告失败原因。
- 资源语义不确定：保持原位置或进入 pending，不强行分类。
- 检测到潜在 Godot 引用风险：停止移动、重命名或删除，先请求确认或执行引用检查。
- manifest 与实际资源不一致：先报告差异，再按用户要求执行同步。
- 批量操作出现部分失败：保留已知状态，停止继续扩大变更范围，并输出可恢复的状态。

# Permission Model

允许：

- 创建缺失的标准资源目录
- 扫描资源
- 生成 hints、review 和报告
- 对规则明确且低风险的新资源进行组织

需要确认：

- 删除未知资源
- 覆盖已确认语义
- 大规模移动已有 Godot 资源
- 重命名已有引用资源
- 修改核心项目资源组织规则

# Skill Completion Report

完成后输出：

```text
Skill:

任务:

修改内容:

验证结果:

状态:

后续建议:
```

# Notes

稳定资源 ID 不应依赖路径。例如：

```text
characters/enemies/goblin/goblin_attack_00.png
→ character_goblin
```

推荐命名使用 lowercase_snake_case；动画帧可采用 `[object]_[action]_[direction]_[frame].png`，帧号固定宽度并从 `00` 开始。

标准资源类型可包括：

```text
character
environment
tileset
background
prop
item
vfx
ui
portrait
font
```

Manifest 推荐将 Scanner 管理的 auto facts 与人工确认的 human semantic fields 分开。