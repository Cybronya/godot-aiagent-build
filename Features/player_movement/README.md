# Feature: player_movement

方向键驱动的 2D 角色移动（CharacterBody2D），本项目第一个沉淀的可复用 Feature（见 `.ai/memory/DECISIONS.md` AD-001）。

## 复用方式

1. 将本目录整体复制，或直接实例化 `Player.tscn`
2. 项目需定义输入动作：`move_left`、`move_right`、`move_up`、`move_down`
3. 移动速度通过根节点导出属性 `speed` 调整
4. 输入动作名通过导出属性 `action_left/right/up/down` 自定义（默认 `move_*`），多个角色可复用同一逻辑（参见 `Scenes/Player2.tscn` 的 `p2_*` 用法）

## 结构

| 文件 | 职责 |
|---|---|
| `Player.tscn` | CharacterBody2D 根节点 + Visual（占位外观）+ Collision |
| `player_controller.gd` | 输入 → 速度 → 移动，单一职责 |
| `test_player_movement.gd` | 无头运行时验证（用法见文件头注释） |
