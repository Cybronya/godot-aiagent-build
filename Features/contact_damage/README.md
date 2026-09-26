# Feature: contact_damage

接触伤害组件：对与宿主重叠、属于目标组的实体按时间节拍造成伤害。伤害规则完全复用 health Feature。

## 接口

- `@export damage: int`：每次结算的伤害量（默认 1）
- `@export tick_interval: float`：结算间隔秒数（默认 0.5）
- `@export target_group: String`：目标所在组名（默认 `players`）
- 每次结算对全部重叠的组内实体调用 `Health.take_damage(damage)`

## 目标约定（组合契约）

1. 目标实体加入 `target_group` 指定的组
2. 目标实体的 Health 组件子节点命名为 `Health`（本项目实体统一约定，见 AD-002）

满足约定即自动生效；不满足则静默跳过（不报错、不受伤）。

## 复用方式

1. 实例化 `ContactDamage.tscn` 作为实体（Area2D 亦可作实体根）的子节点或根
2. 在同节点下添加 CollisionShape2D 定义接触范围
3. 配置 `damage` / `tick_interval` / `target_group`

## 边界

- 本组件不实现生命值逻辑：受击、死亡保护均由 Health 兜底（死亡目标不再受击）
- 不处理击退、无敌帧等表现；需要时应扩展本组件或新建组件，不改动 Health
- 适合环境伤害（尖刺）、近身敌人；一次性命中类交互请复用游戏侧触发器模式

## 结构

| 文件 | 职责 |
|---|---|
| `ContactDamage.tscn` | 组件场景（Area2D 根 + contact_damage.gd） |
| `contact_damage.gd` | 重叠检测 + 节拍结算，单一职责 |
| `test_contact_damage.gd` | 无头运行时验证（用法见文件头注释） |
