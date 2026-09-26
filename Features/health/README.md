# Feature: health

通用生命值组件：当前生命值、伤害处理、死亡状态与死亡事件。

## 接口

- `take_damage(amount: int)`：受到伤害；0/负数与死亡后重复伤害被忽略
- `heal(amount: int)`：恢复生命值，上限钳制为 max_health；0/负数与死亡后恢复被忽略
- `get_current_health() -> int`：查询当前生命值
- `is_dead() -> bool`：查询死亡状态
- `signal health_changed(current: int, amount: int)`：生命值变化（含伤害量）
- `signal died`：生命值归零时触发，恰好一次
- `@export max_health: int`：初始生命值（默认 5，实例化时可覆写）

死亡后的具体表现（消失、重生、结算等）由订阅 `died` 的游戏逻辑决定，本组件不实现。

## 复用方式

1. 将 `Health.tscn` 实例化为任意实体的子节点（不依赖父节点类型）
2. 需要差异化配置时覆写 `max_health` 导出属性
3. 游戏逻辑通过连接 `died` / `health_changed` 响应事件

## 结构

| 文件 | 职责 |
|---|---|
| `Health.tscn` | 组件场景（Node 根 + health.gd） |
| `health.gd` | 生命值状态、伤害处理、死亡事件 |
| `test_health.gd` | 无头组件验证（用法见文件头注释） |
