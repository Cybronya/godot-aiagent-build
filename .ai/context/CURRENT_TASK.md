# 当前任务

## 目标

新增独立 Escape Room 场景，验证 Reusable Features 脱离 SurvivalArena 的再组合能力；流程为 Discovery → Reuse → Composition → Identify Missing Capability → Minimal Build → Verification → Finalization。

## 当前状态

已完成并通过验证：

- 复用（零改动）：player_movement（Player 实例 + players 组）、trigger_switch（两个 Latching 实例 = 两个独立机关）、openable_door（出口门，竖直通道用默认朝向）、tscn connection 接线模式、restart reload 重置语义
- 新 Feature `Features/condition_gate/`：N 条件 AND 聚合（此前只能 OR），纯逻辑 Node；契约 = `set_condition(value, id)`（value 在前，tscn connection binds 追加在信号参数后可直连）+ `fulfilled(bool)` 信号（幂等）+ `is_fulfilled()` + `reset()` + `@export condition_count`；聚合契约 = 全部已上报条件为 true 且数量 ≥ condition_count
- `Scenes/EscapeRoom.tscn`：封闭房间（右墙 128px 缺口）+ SwitchA/SwitchB + ConditionGate(condition_count=2) + ExitDoor + EscapeZone；关系连接 3 条 [connection]（2 条 binds 直连 set_condition，1 条 fulfilled → set_open），零胶水接线
- `Scenes/escape_room.gd`：仅一次性场景逻辑（逃脱成功反馈 + 结束状态重开轮询），机关关系不经过它

关键实现事实（供后续任务参考）：

- 竖直通道的门保持组件默认朝向即可挡住缺口；旋转 90° 会把 24px 碰撞转成横向，只挡缺口中段（物理测试抓到的真实地图缺陷）
- GDScript 调用不可绑定：tscn connection 的 binds 参数是「追加在信号参数之后」，要求目标方法参数顺序为 (信号参数..., 绑定参数...)，API 设计时按此排序
- 多实例测试用 Feature 场景全新实例化，不用 duplicate()（会复制信号连接产生隐式联动）
- 玩家通行验证必须 Input.action_press 真实驱动（PlayerController 每帧按输入覆盖 velocity）
- 测试包装函数与被测组件同名会遮蔽并可能无限递归（set_condition 案例）

验证结果：

- condition_gate 自身验证（AND 聚合/数量约束/回落语义/幂等/reset/多实例）：PASS
- Escape Room 集成验证（真实物理阻挡与穿出、AND 条件、状态保持、逃脱成功、重载复位、连接为场景数据）：PASS
- 全量回归：17/17 PASS；主场景与 EscapeRoom 场景启动均无脚本错误；Framework Validator PASS（0 errors / 0 warnings）

Framework 缺陷检查：未发现阻塞，未修改 Framework。

## 修改文件

- `Features/condition_gate/`（新增：脚本、场景、测试、README）
- `Features/trigger_switch/README.md`、`Features/openable_door/README.md`（补充既有 Feature 文档）
- `Scenes/EscapeRoom.tscn`、`Scenes/escape_room.gd`（新增）
- `Tests/test_escape_room.gd`（新增）
- `.ai/context/CURRENT_TASK.md`（本文件）

## 下一步

无阻塞事项。
