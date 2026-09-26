# Feature: moving_platform

移动平台：在起点与起点+travel 之间三角波往返移动，重叠载客区的玩家随平台位移（渡载）。

## 接口

- `@export travel: Vector2`：相对起点的单程位移（默认 (200, 0)，即水平往返）
- `@export period: float`：一个完整往返周期秒数（默认 4）
- `@export target_group: String`：可载运实体所在组（默认 `players`）

## 行为契约

- 位置由内部时间驱动（不依赖外部输入），场景重载后自动从起点重新开始
- 进入 `RideZone` 的组内实体被记录为乘客，平台每帧位移量直接应用到乘客位置
- 离开 `RideZone` 即下车；乘客被释放时自动清理
- **非实体渡载语义**：平台本体不带碰撞（玩家可直接走入/走出载客区被携带/释放）；
  需要实体推挤时由使用场景自行添加 CollisionShape2D（子节点）
- `sync_to_physics = true`：与物理同步移动

## 复用方式

1. 实例化 `MovingPlatform.tscn`，按需覆写 `travel` / `period`
2. 摆放在需要渡运的缺口/通道旁
3. 垂直电梯：`travel = Vector2(0, -160)`

## 边界

- 渡载为「位移搬运」语义，乘客保持其自身速度（玩家输入仍然生效）
- 本体非实体：不做推挤阻挡（需要时场景级添加碰撞，属使用场景的设计决策）
- 不做路径点序列/等待节奏（需要时扩展 travel 行为，不改载客逻辑）
- 不与 Health/收集系统交互

## 结构

| 文件 | 职责 |
|---|---|
| `MovingPlatform.tscn` | 组件场景（AnimatableBody2D + Visual + DeckShape + RideZone + 内部信号连接） |
| `moving_platform.gd` | 三角波往返 + 渡载，单一职责 |
| `test_moving_platform.gd` | 无头运行时验证（用法见文件头注释） |
