# Feature: health_bar

血条显示组件：绑定宿主 Health，按当前/最大生命值比例绘制双色血条。纯显示组件，不修改任何生命值状态。

## 接口

- `@export health_path: NodePath`：宿主 Health 组件路径（相对本节点）
- `@export bar_size: Vector2`：血条尺寸（默认 32x4）
- `@export back_color / fill_color: Color`：底色 / 前景色
- `get_ratio() -> float`：当前比例（0.0–1.0， Health 上限钳制 + 显示钳制双重保证）

## 刷新机制

订阅宿主 Health 的 `health_changed` / `died` 信号，信号到达即 `queue_redraw()`；
比例读取自 Health 公开接口（`get_current_health()` / `max_health`），血条自身不保存状态。

## 复用方式

1. 实例化 `HealthBar.tscn` 为任意实体子节点
2. 配置 `health_path` 指向该实体的 Health 组件（默认命名 `Health`，见 AD-002 约定）
3. 按需调整位置与外观导出参数

## 边界

- 不适合直接当玩家 HUD 主血条使用（HUD 场景需叠加布局/文本/全屏样式时，应组合本组件或扩展，不改 Health）
- 不绑定 Health 时不绘制填充（比例恒为 0），不报错

## 结构

| 文件 | 职责 |
|---|---|
| `HealthBar.tscn` | 组件场景（Node2D 根 + health_bar.gd） |
| `health_bar.gd` | 绑定 Health + 按比例绘制，单一职责 |
| `test_health_bar.gd` | 无头运行时验证（用法见文件头注释） |
