# i_frames

受击无敌帧组件：宿主受到伤害后自动在 Health 上开启一段无敌窗口——窗口内
所有 `take_damage` 被 Health 门静默拒绝，到期自动恢复可受击。经典
「受击 → 1 秒无敌闪烁」机制的机制层（视觉表现交给 hit_flash）。

## 来源（片段 → Feature）

抽象自代码库参考片段（教学示例，未直接拷贝）：

- 片段 1：`.ai/skills/foundation/godot-gdscript/code_library/references/movement/nezvers__Godot-GameTemplate__addons__top_down__scripts__damage__DamageCooldown.gd`
  （[nezvers/Godot-GameTemplate](https://github.com/nezvers/Godot-GameTemplate)，MIT，star 1670）——`can_receive_damage` 受击门控思路
- 片段 2：同仓库 `...actor__VisualInvulnerability.gd`——无敌状态的反应式表现切换

抽象取舍：上游把门控状态放在自己的 DamageResource 里（ResourceNode 框架）；
本项目的伤害唯一入口是 `Health.take_damage`，所以门做进 Health（加性扩展，
默认关闭零行为变化），计时**直接复用 Cooldown Feature**（IFrames.tscn 内置
Cooldown 子节点，组合而非重造），视觉不掺和（hit_flash 已覆盖）。

## 复用方式

1. 实体场景：`Health.tscn` + `IFrames.tscn` 同挂实体（Node2D 等）下即生效
   ——受击自动开窗（默认 0.3s），窗口内 `contact_damage` 的攻击被门拒绝。
2. 主动无敌（技能/翻滚）：`iframes.grant(0.5)`；保护中重复 grant 被拒绝
   （固定窗口，不刷新）。
3. UI：`is_protected()` / `protected(bool)` 供 HUD 显示保护状态。

## 契约要点

- **职责切分**：门状态归 Health、计时归 Cooldown、本组件只做胶水与受击快照
  判定；移除组件时若在保护中会归还门状态（避免永久无敌）。
- **固定窗口**：窗口内再次受击/grant 不刷新时长（与 Stun 长盖短、Cooldown
  重启刻意不同——无敌帧应是确定保护期）。
- **死亡时序**：受击判定经 `call_deferred` 落地，击杀一击不再开新窗
  （health_changed 在 `_is_dead` 置位前发出，与 Stun/hit_flash 同解）。
- 一个 Health 只挂一个 IFrames（多实例会争抢门写权）。

## 对 Health 的加性扩展（本次一并落地）

- 新增 `set_invulnerable(bool)` / `is_invulnerable()`；`take_damage` 在门开时
  静默拒绝（heal 不受影响）。
- **默认关闭，行为与历史完全一致**——health/stun/hit_flash/contact_damage/
  heal_pickup 全部回归测试通过。

## 测试

```bash
godot --headless --path . -s res://Features/i_frames/test_i_frames.gd
```

覆盖：Health 门默认关闭兼容、受击自动开窗与免伤、固定窗口不刷新、到期恢复、
治疗不触发、主动 grant 与保护中拒绝、死亡豁免、无 Health 宿主、移除归还门状态。
