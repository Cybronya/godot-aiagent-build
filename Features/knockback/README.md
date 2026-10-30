# knockback — 击退组件

挂在 CharacterBody2D 实体下的受击反馈组件：`apply(direction, force)` 施加一段
线性衰减的**位置位移脉冲**，敌人被打退、玩家被爆炸推开。

## 教学来源

- [Miziziziz/MizGodotTools — damage_data.gd](https://github.com/Miziziziz/MizGodotTools)（MIT）：
  把 `damage_direction` / `knockback_modifier` 打包进伤害载荷的思路。
  收藏于 `code_library/references/combat/`（蒸馏片段）。

## 抽象取舍

| 参考实现 | 本组件 |
|---|---|
| 击退混在伤害载荷里，由移动系统消费 | 独立组件：`apply()` 即生效，衰减自动完成 |
| 通常写 velocity，与移动脚本互相覆盖 | **位置位移式**，不碰 velocity，与 chase/patrol 天然无冲突 |
| — | 线性衰减 `decay`，总位移确定（F²/(2D)），行为证据可精确断言 |

## 用法

```gdscript
# 实例化为 CharacterBody2D 直接子节点，受击时：
$Knockback.apply((enemy.global_position - global_position).normalized(), 240.0)
```

信号 `knockback_changed(is_active)` 幂等广播状态跨越（true 一次 / 归零 false 一次），
可供音效/粒子/屏幕震动联动。

## 语义三角（与移动类组件的关系）

- **chase/patrol**：写 `velocity`，负责持续移动——不受击退影响
- **stun**：暂停宿主物理，负责"不能动"
- **knockback**：位移增量，负责"被动挪动"——三者可同时挂载，职责正交

## 验证

```bash
godot --headless --path . -s res://Features/knockback/test_knockback.gd
```
