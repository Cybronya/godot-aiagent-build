# projectile

直线抛射物：`launch(direction)` 后恒速飞行，命中带 Health 的实体造成伤害；
穿透数上限与生命期双重终止，终止时广播 `finished` 并自释放。

## 来源（片段 → Feature）

抽象自代码库参考片段（教学示例，未直接拷贝）：

- 片段 1：`.ai/skills/foundation/godot-gdscript/code_library/references/movement/nezvers__Godot-GameTemplate__addons__top_down__scripts__weapon_system__projectile__HitLimit.gd`
  （[nezvers/Godot-GameTemplate](https://github.com/nezvers/Godot-GameTemplate)，MIT，star 1670）——穿透计数与终止生命周期
- 片段 2：同仓库 `weapon_system__projectile__LerpProjectileTrajectory.gd`——抛射物生命周期钩子（插值/落地/退场）
- 片段 3：`.ai/skills/foundation/godot-gdscript/code_library/references/movement/gdquest-demos__godot-open-rpg__src__combat__actions__battler_action_projectile.gd`
  （[gdquest-demos/godot-open-rpg](https://github.com/gdquest-demos/godot-open-rpg)，MIT，star 3028）——发射动作生成抛射物并传入方向

抽象取舍：去掉上游的 DataChannelTransmitter / ProjectileMover /
ShapeCastTransmitter 框架链与 Lerp 弹道特效，用本项目 Area2D.body_entered +
「Health 子节点」约定直连（与 contact_damage 同一套命中约定）；伤害统一走
`Health.take_damage`——无敌门（i_frames）与死亡守卫自动生效，无需本组件知情。

## 复用方式

```gdscript
var p: Projectile = Projectile_SCENE.instantiate()
p.damage = 2
p.max_hits = 1        # <1 无限穿透
add_child(p)
p.launch(target_dir)  # 或设 launch_on_ready=true 用 rotation 定向
```

- 挂在发射者身上：敌人射击、玩家武器、陷阱都同一组件。
- `hit(target)` / `finished` 供特效与音效挂钩；`get_progress` 不适用——
  直线弹道没有进度概念，用 `lifetime` 控制射程。

## 契约要点

- **命中即穿约定**：无 Health 的物体直接穿过（墙体由物理层/碰撞掩码屏蔽）。
- **终止语义**：`max_hits>=1` 时命中计数达到上限即终止；`<1` 无限穿透只受
  `lifetime` 约束；`finished` 恰好一次，随后 `queue_free`。
- 伤害走 `Health.take_damage`：目标开无敌门（i_frames）时本次命中被静默拒绝，
  但**仍计入穿透数**（接触即消耗）——组合时注意。

## 测试

```bash
godot --headless --path . -s res://Features/projectile/test_projectile.gd
```

覆盖：发射前休眠、恒速位移、命中伤害与 hit 信号、穿透耗尽终止、无限穿透、
无 Health 物体穿过、生命期到期、零向量方向忽略。
