# Feature: collect_pickup

接触拾取组件：目标组实体接触后广播 `collected` 并从场景移除自身。一次性收集语义，不与 Health 交互。

## 接口

- `signal collected(value: bool, pickup_id: String)`：收集事件（value 恒为 true；签名与 ConditionGate.set_condition 完全一致，直接连接即可）
- `is_collected() -> bool`：查询收集状态
- `@export pickup_id: String`：本拾取物的条件 id（直连 set_condition 时作为数据约定传入）
- `@export target_group: String`：可拾取实体所在组（默认 `players`）

## 行为契约

- 组内实体接触 → 广播一次 → `queue_free()` 自移除；消失后天然不可重复收集
- 组外实体接触无效果
- `collected(value, pickup_id)` 与 `ConditionGate.set_condition(value, id)` 签名一致：场景层直接连接，`pickup_id` 导出值作为条件 id（数据约定，无需 binds）

## 复用方式

1. 实例化 `CollectPickup.tscn`（内置默认拾取范围，可覆写形状），配置 `pickup_id`
2. 场景层将 `collected` 直接连接到 `ConditionGate.set_condition`（pickup_id 导出值 = 条件 id），或接入任意 `(bool, String)` 消费者
3. N 把钥匙 = N 个实例；收集进度由 ConditionGate 聚合表达

## 边界

- 不与 Health 交互、无数值结算（那是 heal_pickup 的职责）
- 无库存/背包/掉落实体：收集即事件
- 不可重复收集、不可返还

## 结构

| 文件 | 职责 |
|---|---|
| `CollectPickup.tscn` | 组件场景（Area2D + 脚本 + 占位外观 + 默认拾取范围） |
| `collect_pickup.gd` | 接触收集 + 一次性语义，单一职责 |
| `test_collect_pickup.gd` | 无头运行时验证（用法见文件头注释） |
