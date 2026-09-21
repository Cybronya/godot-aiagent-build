# Godot Naming Rules

## 文件与目录命名

Scene 文件：

- PascalCase
- 例如：`Player.tscn`、`MainGame.tscn`

Script 文件：

- snake_case
- 例如：`player_controller.gd`

资源文件（图片、音频等）：

- lowercase_snake_case
- 例如：`player_idle.png`
- 详细规则见 godot-art-assets Skill

目录命名：

- 顶层目录 PascalCase（本项目约定，见 folder-structure.md）
- 资源子目录 lowercase（由 godot-art-assets 工具创建，如 `assets/characters/`）

## 标识符命名

Class：

- PascalCase
- 例如：`PlayerController`

Variable：

- snake_case
- 例如：`move_speed`

Constant：

- UPPER_SNAKE_CASE
- 例如：`MAX_HEALTH`

Function：

- snake_case
- 例如：`take_damage()`

Signal：

- 过去式或名词短语，snake_case
- 例如：`health_changed`、`died`

## 禁用的文件名写法

以下写法**禁止出现在文件名中**（禁止的是文件名后缀，不是 GDScript 标识符——`final`/`new` 本身是脚本语言关键字，与文件命名无关）：

- `player_final.gd`（用 final 标记"最终版"）
- `player_final2.gd`（数字后缀的版本变体）
- `new_scene.tscn`（用 new 标记"新建"）
- `temp_fix.gd`（用 temp 标记临时文件）
- `backup_player.gd`（用 backup 标记备份副本）

版本管理交由 git 完成；临时实验文件不要提交，也不要用这些词命名长期文件。

## 示例对照

| ❌ 错误 | ✅ 正确 | 原因 |
|---------|---------|------|
| `player final2.gd` | `player_controller.gd` | 无版本后缀、snake_case |
| `NewScene.tscn` | `MainMenu.tscn` | 按职责命名 |
| `test.gd` | `enemy_spawner.gd` | 按功能命名 |
| `BACKUP_Player.png` | `player_idle.png` | 资源用小写 snake_case |
