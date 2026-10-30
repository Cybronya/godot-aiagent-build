# attack_emitter

> 状态：**正式 Feature**（自 MizGodotTools attack_emitters 抽象重写，自测通过）。

## 职责

把「发起一次攻击」抽象成可组合的发射器单元：`do_attack()` 沿发射器树传播，
伤害结算走项目 `Health.take_damage` 协议；弹道线、命中特效、音效等视觉反馈
不属于本组件，由组合层订阅信号实现。

## 组成

| 脚本 | 说明 |
|---|---|
| `attack_emitter.gd`（AttackEmitter） | 基类：damage / source_of_attack / 排除列表沿链传播，do_attack 链式发起 |
| `raycast_attack_emitter.gd`（RaycastAttackEmitter） | 射线实现：需 RayCast2D 子节点，瞬时判定 + 结算 |
| `AttackEmitterFixture.tscn` | 行为夹具：发射器 + 射线 + take_damage 目标（40px 宽，位于 +X 110px） |

扇形（spray）、弧形（arc）等形态按相同协议继承 AttackEmitter 扩展
（参考片段库 `Miziziziz__MizGodotTools` 的 arc_emitter / spray_emitter 思路）。

## 接口速览

- `damage: int` / `source_of_attack: Node2D`：沿链传播的攻击参数
- `set_bodies_to_exclude([攻击者])`：排除列表（通常排除自己）
- `do_attack()`：发起攻击
- `attacked`（发起）/ `attack_performed(from, to, hit, point)`（弹道终点证据）/
  `attack_hit(target, point)`（伤害已结算）

## 与来源片段的差异（抽象要点）

1. **剥除类依赖**：原版依赖原工程的 `HitBox` / `DamageData` 全局类；
   改为鸭子类型——碰撞体实现 `take_damage(amount: int)` 即结算，
   与 health Feature 的公开接口直接对接。
2. **视觉解耦**：原版 preload 弹道特效/命中特效场景（原工程资源路径）；
   本组件只发 `attack_performed`（含起止点与命中标志），视觉归组合层。
3. **协议化排除**：RayCast2D 的 exception 注入收敛在 `set_bodies_to_exclude`，
   与基类传播链统一。

## 复用方式

```gdscript
var emitter := preload("res://Features/attack_emitter/raycast_attack_emitter.gd").new()
weapon.add_child(emitter)   # 并给 emitter 配 RayCast2D 子节点
emitter.damage = 3
emitter.set_bodies_to_exclude([owner_entity])
emitter.attack_hit.connect(_on_weapon_hit)
# 攻击输入时：
emitter.do_attack()
```

来源片段许可证：MIT（Miziziziz/MizGodotTools，对外发布需附署名）。
