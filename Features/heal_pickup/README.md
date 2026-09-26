# Feature: heal_pickup

治疗拾取物：目标组实体接触时恢复其 Health 并从场景移除自身。恢复规则完全复用 health Feature。

## 接口

- `@export heal_amount: int`：恢复量（默认 2）
- `@export target_group: String`：可拾取实体所在组名（默认 `players`）
- 接触即结算：恢复后 `queue_free()` 移除自身

## 消费规则

满足以下全部条件才消费（恢复 + 移除），否则拾取物保持在场：

1. 接触实体属于 `target_group`
2. 实体存在命名为 `Health` 的 Health 子组件（本项目实体统一约定，见 AD-002）
3. 目标未死亡且当前生命值未满（满血不消费，恢复上限由 `Health.heal()` 钳制保证）

## 复用方式

1. 实例化 `HealPickup.tscn`，在同节点下添加 CollisionShape2D 定义拾取范围
2. 配置 `heal_amount` / `target_group`
3. 场景/生成器按需摆放或定期刷新拾取物

## 边界

- 不实现动画、音效、悬浮表现；需要时扩展本组件或由场景叠加
- 不做库存/背包：直接结算到目标 Health
- 死亡目标不消费（避免「死后复活」类副作用），复活类需求应另建 Feature

## 结构

| 文件 | 职责 |
|---|---|
| `HealPickup.tscn` | 组件场景（Area2D 根 + 脚本 + 占位外观） |
| `heal_pickup.gd` | 接触判定 + 消费规则，单一职责 |
| `test_heal_pickup.gd` | 无头运行时验证（用法见文件头注释） |
