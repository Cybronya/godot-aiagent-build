# hit_flash

受击闪白组件：宿主生命值下降时，把目标 CanvasItem 的 `modulate` 抬到
`flash_color` 并在 `flash_duration` 内线性衰减回基色，产生受击反馈。

## 来源（片段 → Feature）

抽象自代码库参考片段（教学示例，未直接拷贝）：

- 片段 1：`.ai/skills/foundation/godot-gdscript/code_library/references/movement/nezvers__Godot-GameTemplate__addons__top_down__scripts__shaders__color_flash.gdshader`
  （[nezvers/Godot-GameTemplate](https://github.com/nezvers/Godot-GameTemplate)，MIT，star 1670）——混色闪白思路
- 片段 2：`.ai/skills/foundation/godot-gdscript/code_library/references/ui/godotengine__godot-demo-projects__misc__hdr_output__output_max_linear_value__color_flash.gd`
  （[godotengine/godot-demo-projects](https://github.com/godotengine/godot-demo-projects)，MIT，star 9711）——flash 后按时间衰减回基色的模式

抽象取舍：两个上游一个要求每个精灵配 ShaderMaterial，一个绑定具体 MeshInstance3D
材质；合并改用 **CanvasItem.modulate 衰减**——任意 2D 节点即插即用、无材质配置、
headless 可确定性测试（上游用 `_process` + 实时 delta，本组件用 `_physics_process`）。

## 复用方式

1. 场景中将 `HitFlash.tscn` 实例化为实体（Node2D 等 CanvasItem）的子节点。
2. 自动模式（默认）：宿主子树里有 `Health` 组件（命名 "Health" 或设
   `health_path`）即可——受击（生命值下降）自动闪白，治疗不触发，死亡豁免。
3. 主动模式：任意代码调用：

```gdscript
flash_body.get_node("HitFlash").flash(0.2)   # 自定义时长
```

4. 衰减与停止自动完成，无需手动复位。

## 契约要点

- **独占目标 `modulate`**：闪白期间不要让其它逻辑写该属性；移除组件时
  若仍在闪白自动归还基色。
- **幂等广播**：`flashing(bool)` 只在状态跨越时发一次（进入 true / 归零 false）。
- **长盖短**：闪白中再次触发取较大时长（与 Stun 组件一致）。
- **死亡守卫**：受击判定经 `call_deferred` 落地，击杀一击不触发闪白
  （health_changed 在 `_is_dead` 置位前发出的时序陷阱，与 Stun 同解）。
- 一个目标只挂一个 HitFlash（多实例会争抢 modulate）。

## 测试

```bash
godot --headless --path . -s res://Features/hit_flash/test_hit_flash.gd
```

覆盖：受击触发与基色记录、衰减归零、长盖短重入、治疗不触发、死亡豁免、
主动 flash、无效时长、错误宿主拒绝、移除归还基色。
