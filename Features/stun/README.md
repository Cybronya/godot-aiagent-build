# stun（眩晕/硬直组件）

## 职责

使宿主 `CharacterBody2D` 的物理行为暂停一段时长后自动恢复。属于「宿主受击/被控后的表现层」组件，与死亡表现（`Scenes/player_death.gd` 先例）同源：状态判定复用 health Feature，表现由本组件决定（AD-002 哲学的受击面延伸）。

## 公开接口

```gdscript
signal stunned(is_stunned: bool)   # 状态跨越时广播；重复同值不广播（幂等）

func stun(duration: float) -> bool  # 主动触发；duration<=0 或宿主已死亡返回 false
func is_stunned() -> bool
```

导出参数：

- `stun_on_hit: bool = false` — 订阅宿主 Health，生命值下降（受击）自动眩晕
- `stun_duration: float = 0.4` — 受击自触发的眩晕时长；`stun()` 调用由调用方给时长
- `health_path: NodePath` — 显式指定 Health 组件；缺省按 `../Health` 命名约定解析

## 组合契约

- 宿主：`CharacterBody2D`（挂为宿主子节点）
- 生命状态：宿主子节点 `Health`（命名约定，AD-004 契约一致），或经 `health_path` 指定
- 组合方式与 contact_damage / health_bar 完全一致：实例化 Stun.tscn 为实体子节点 + 覆写导出参数

## 暂停范围（边界）

- 暂停：宿主根节点 `set_physics_process(false)` + 速度集成停摆 + 速度清零（与 player_death 死亡表现同源）
- 不影响：宿主子组件各自的 `_physics_process`（ContactDamage 等独立驱动）；组合层可自行取舍
- 重入：时长内再次触发取剩余与新时长的较大值（长盖短，不提前解除）
- 死亡保护：宿主死亡后不触发、不生效；恢复时不启用物理（不越权复活，死亡表现由死亡订阅方负责）
- 生命周期：组件在眩晕未结束时移除（宿主仍存活）→ 恢复宿主物理，不留永久停摆；宿主 queue_free 时随树销毁，无 timer/callback 残留
- 治疗豁免：`health_changed` 数值上升不触发受击眩晕

## 拥有的状态 / 不拥有的状态

- 拥有：眩晕剩余时长、宿主与 Health 引用、上次生命值快照（受击判定）
- 不拥有：生命值数值（Health）、伤害数值（触发方决定）、宿主移动参数、任何场景流程状态（波次/胜负/倒计时）

## 触发模式（两种消费者形态）

1. **被动自触发**：`stun_on_hit=true` —— 敌人被玩家命中后打断追击（硬直）
2. **主动 API**：场景逻辑调用 `stun(duration)` —— 麻痹陷阱、技能、机关等外部效果

## 验证

```bash
godot --headless --path . -s res://Features/stun/test_stun.gd
```

覆盖：主动眩晕/恢复/幂等刷新与长盖短重入、无效输入、无宿主容错、受击自触发、治疗豁免、物理停摆与恢复、死亡保护、多实例独立。
