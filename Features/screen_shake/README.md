# screen_shake

屏幕震动组件：作为 Camera2D 的直接子节点，调用 `add_trauma(amount)` 叠加震动强度，
组件自动完成衰减与停止，并将随机偏移写入宿主相机的 `offset`。

## 来源（片段 → Feature）

抽象自代码库参考片段（教学示例，未直接拷贝）：

- 片段：`.ai/skills/foundation/godot-gdscript/code_library/references/animation/nezvers__Godot-GameTemplate__addons__great_games_library__resources__CameraShakeResource__CameraShakeResource.gd`
- 上游：[nezvers/Godot-GameTemplate](https://github.com/nezvers/Godot-GameTemplate)（MIT，star 1670）

抽象时去掉的内容：GameTemplate 自定义 Resource 框架依赖
（`ReferenceNodeResource` / `TweenValueResource` / `BoolResource` / Tween 方法采样），
改为本项目组件挂载约定（父节点即宿主）与 trauma 衰减模型。

## 复用方式

1. 场景中将 `ScreenShake.tscn` 实例化为 `Camera2D` 的**直接子节点**
   （父节点不是 Camera2D 时组件告警并拒绝触发）。
2. 触发方在合适的时机调用：

```gdscript
shake.add_trauma(0.3)   # 轻微受击
shake.add_trauma(1.0)   # 爆炸满屏
```

3. 强度每秒按 `decay` 线性衰减，偏移 = 噪声 × `max_offset` × trauma²，
   归零后 `offset` 自动清零并广播 `shaking(false)`。无需手动停止。

## 契约要点

- **独占 `Camera2D.offset`**：不要让其它逻辑同时写宿主相机的 offset；
  移除组件时偏移自动归还为零。
- **幂等广播**：`shaking(bool)` 只在状态跨越时发一次（进入 true / 归零 false）。
- **可复现**：`noise_seed` 固定时，同输入序列产生同偏移序列（利于测试与录像）。
- 一台相机只挂一个 ScreenShake（多实例会争抢 offset）。

## 测试

```bash
godot --headless --path . -s res://Features/screen_shake/test_screen_shake.gd
```

覆盖：触发与幂等广播、噪声偏移生效、衰减归零、无效输入、错误宿主拒绝、
移除归还 offset、种子可复现。
