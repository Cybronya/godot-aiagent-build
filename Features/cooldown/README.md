# cooldown

通用冷却组件：`start()` 开始/重启一段倒计时，期间 `is_ready()` 为 false，
到期自动广播 `cooldown_finished` 并回到就绪。攻击间隔、技能 CD、机关触发
间隔等「用一次 → 等一段」的节流场景都适用。

## 来源（片段 → Feature）

抽象自代码库参考片段（教学示例，未直接拷贝）：

- 片段 1：`.ai/skills/foundation/godot-gdscript/code_library/references/ai/bitbrain__beehave__addons__beehave__nodes__decorators__cooldown.gd`
  （[bitbrain/beehave](https://github.com/bitbrain/beehave)，MIT，star 3312）——冷却门控思路（结束时间戳，行为树装饰器形态）
- 片段 2：`.ai/skills/foundation/godot-gdscript/code_library/references/movement/nezvers__Godot-GameTemplate__addons__top_down__scripts__damage__DamageCooldown.gd`
  （[nezvers/Godot-GameTemplate](https://github.com/nezvers/Godot-GameTemplate)，MIT，star 1670）——`cooldown_started/finished` 信号对

抽象取舍：脱离 beehave 的行为树 blackboard 与 GameTemplate 的 ResourceNode
框架（assert + 资源注入），Tween 延迟改为 `_physics_process` 倒计时——
独立挂载、无框架依赖、headless 下可确定性测试。

## 复用方式

```gdscript
# 场景中实例化 Cooldown.tscn 后：
if attack_cd.is_ready():
    _fire_projectile()
    attack_cd.start(0.8)          # 攻击 CD 0.8s
```

- 节流点判断 `is_ready()`，行动后 `start()`，到期自动回就绪，无需手动复位。
- `auto_start=true` 可挂载即进入冷却（关卡开场整备期等场景）。
- `get_remaining()` / `get_progress()` 供 UI 画冷却圈。

## 契约要点

- **重启语义**：冷却中再次 `start()` 重置剩余时长并再次广播 `cooldown_started`
  （与 Stun 的「长盖短」刻意不同——攻击 CD 的自然语义是重打重计）。
- **哨兵约定**：`start(-1)` / 不传参 = 用 `duration` 导出值；显式传 `0` 视为
  无效直接拒绝。
- 只拥有自己的计时状态，不触碰宿主属性；到期 `finished` 恰好广播一次。
- `_physics_process` 驱动，无头环境可确定性测试。

## 测试

```bash
godot --headless --path . -s res://Features/cooldown/test_cooldown.gd
```

覆盖：初始就绪、启动与信号、重启语义、到期广播、无效时长拒绝、哨兵语义、
duration=0 导出值拒绝、auto_start、进度查询。
