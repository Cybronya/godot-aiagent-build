# Feature: condition_gate

条件聚合门：把 N 个布尔输入按 AND 聚合为单一输出。纯逻辑 Node，无场景/节点类型依赖。

## 接口

- `signal fulfilled(is_fulfilled: bool)`：仅在跨越阈值时广播（幂等）
- `set_condition(value: bool, id: String)`：上报条件状态；id 未声明时自动纳入。value 在前是刻意的：场景连接 binds 追加在信号参数后，`activated(bool)` 可直连（binds=["id"]）
- `is_fulfilled() -> bool`：查询聚合结果
- `reset()`：清空全部条件并广播 false（供场景级重置流程调用）
- `@export condition_count: int`：最少满足数量（默认 2）

## 聚合契约

`fulfilled = 全部已上报条件为 true 且 条件数 ≥ condition_count`

- 任何已上报条件为 false 都会使聚合回落（set_condition 是绝对值上报）
- 跨越阈值才广播；重复上报同值不产生多余信号
- 与 trigger_switch 的 `activated(bool)`、openable_door 的 `set_open(bool)` 同签名，信号直连零胶水

## 复用方式

1. 实例化 `ConditionGate.tscn`，配置 `condition_count`
2. 场景层将各开关的 `activated` 直连 `set_condition` 并用 binds 绑定条件 id（如 `binds=["switch_a"]`）
3. 将 `fulfilled` 连接到目标（如 `OpenableDoor.set_open`）



## 边界

- 保持型语义：达成后保持满足，直到 reset（与 Latching 开关一致）
- 需要「条件失效立即失效」的动态重评：扩展本组件，不另建
- 不解析条件来源、不管理输入时序（上报顺序无关结果）

## 结构

| 文件 | 职责 |
|---|---|
| `ConditionGate.tscn` | 组件场景（Node + 脚本） |
| `condition_gate.gd` | AND 聚合逻辑，单一职责 |
| `test_condition_gate.gd` | 无头运行时验证（用法见文件头注释） |
