# Feature: openable_door

状态门：接收激活信号切换「阻挡 ↔ 通行」，视觉同步反映当前状态。纯被动组件，不知道信号来源。

## 接口

- `set_open(value: bool)`：设置门状态（重复设置同值幂等无副作用）
- `is_open() -> bool`：查询当前状态
- `signal state_changed(is_open: bool)`
- `@export start_open: bool`：入树即开启
- `@export open_visual_color / closed_visual_color: Color`：双色可调

## 行为契约

- 开 = 碰撞停用 + 半透明绿；关 = 碰撞启用 + 实体棕
- 碰撞切换使用 `set_deferred`，信号回调（含物理回调）中调用安全
- 旋转场景实例即可得到任意方向的门（碰撞与视觉随实例变换）

## 复用方式

1. 实例化 `OpenableDoor.tscn`，按需旋转/缩放
2. 场景层将任意 `activated(bool)` 类信号连接到 `set_open`
3. 多个信号连到同一扇门 = 多来源共同控制（后写优先）

## 边界

- 无滑动/升降动画（表现层叠加或扩展）
- bool 二态；三态以上需重新设计契约，不硬塞
- 无 Health：不可被破坏（可破坏门应另组合 Health 的新变体场景）

## 结构

| 文件 | 职责 |
|---|---|
| `OpenableDoor.tscn` | 组件场景（StaticBody2D + 脚本 + Visual + Collision） |
| `openable_door.gd` | 状态切换 + 碰撞/视觉反映，单一职责 |
| `test_openable_door.gd` | 无头运行时验证（用法见文件头注释） |
