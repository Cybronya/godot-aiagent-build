# Rule Priority

版本：1.0

## Purpose

定义 Godot Agent 在面对多个规范来源时的优先级。

## Priority Order

规则优先级：

1. 用户明确指定规则
2. 项目已有规范文件
3. 项目历史决定（Memory）
4. Skill References中的规范
5. Skill默认规范

## Behavior

当高优先级规则与低优先级规则冲突时：

- 保留高优先级规则
- 不自动覆盖已有项目决定
- 向用户说明冲突原因

## Example

如果Skill默认要求：

Scripts/

但项目已有：

game_logic/

则保持项目现有结构，除非用户要求修改。
