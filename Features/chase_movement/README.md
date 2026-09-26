# Feature: chase_movement

朝目标节点持续移动的 2D 追击组件（CharacterBody2D 根脚本），与 player_movement（读输入）互为镜像：本组件不读任何输入。

## 接口

- `@export speed: float`：移动速度（默认 80）
- `@export target_path: NodePath`：目标节点路径（相对本节点，通常指向玩家实体）
- 每物理帧朝目标当前位置移动；目标缺失、未配置或已被释放时保持静止，不报错

## 复用方式

1. 实例化 `ChaseMovement.tscn` 作为实体根（要求 CharacterBody2D），或直接使用 `chase_movement.gd` 作为根脚本
2. 场景内自行添加 Visual / CollisionShape2D 与其他组件（如 `Features/health/Health.tscn`）
3. 通过 `target_path` 配置追击目标；目标死亡移除后追击自动停止

## 边界

- 移动逻辑不依赖目标类型（任何 Node2D 均可作为目标）
- 自身验证使用本地构建的探针目标，不依赖任何游戏侧实体场景

## 结构

| 文件 | 职责 |
|---|---|
| `ChaseMovement.tscn` | 组件场景（CharacterBody2D 根 + chase_movement.gd） |
| `chase_movement.gd` | 朝目标移动，单一职责 |
| `test_chase_movement.gd` | 无头运行时验证（用法见文件头注释） |
