# Feature: trigger_switch

触发开关：目标组实体进入触发范围后改变自身状态并广播信号。只感知触发、维护自身状态，不知道谁在监听。

## 接口

- `signal activated(triggered: bool)`：状态变化广播（true=已触发；reset 广播 false）
- `is_triggered() -> bool`：查询当前状态
- `reset()`：恢复未触发状态（供场景级重置流程调用）
- `@export trigger_mode`：Latching（默认，触发后保持）/ Repeat（每次进入都触发）
- `@export target_group: String`：触发实体所在组（默认 `players`）

## 行为契约

- Latching：首次进入触发，离开不回退，重进不重复触发
- Repeat：每次进入范围都触发（需明确理由才使用）
- 组外实体进入不触发；状态只有组件自身与 `reset()` 能改变

## 复用方式

1. 实例化 `TriggerSwitch.tscn`（内置 radius 40 默认触发范围，可覆写形状）
2. 场景层将 `activated` 连接到任意接受 `(bool)` 的方法（如 `OpenableDoor.set_open`、`ConditionGate.set_condition`）
3. 多个连接 = 一个开关控制多个目标，无需任何胶水脚本

## 边界

- 不做按键交互、按住保持、计时窗口（需要时扩展或新建组件）
- 不直接驱动目标：关系由场景连接表达

## 结构

| 文件 | 职责 |
|---|---|
| `TriggerSwitch.tscn` | 组件场景（Area2D + 脚本 + 占位外观 + 默认触发范围） |
| `trigger_switch.gd` | 触发感知 + 状态维护，单一职责 |
| `test_trigger_switch.gd` | 无头运行时验证（用法见文件头注释） |
