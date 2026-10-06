# Keywords Routing（Hand-authored）

自然语言 → 官方 API。

路径基准 `references/4.7/`，正文前缀统一为：

```text
../../../../godot-official-docs_sources/4.7/classes/
```

继承成员注意：signal / method 可能定义在父类（如 `Button.pressed` 在 `BaseButton`），按 Target 列的链路上溯；规则详见 `api/INDEX.md`。

| Query | Keywords | Target（→ 继承链） | Source Path |
|---|---|---|---|
| 玩家移动 | player movement, character controller, 3D character | `CharacterBody3D` | `class_characterbody3d.rst` |
| 2D 角色 | top-down movement, 2D character | `CharacterBody2D` | `class_characterbody2d.rst` |
| 移动实现 | velocity, move_and_slide, is_on_floor | `CharacterBody2D/3D`（方法在本类） | 同上 |
| WASD / 键盘 | keyboard input, action, deadzone | `Input` / `InputMap` | `class_input.rst`、`class_inputmap.rst` |
| 鼠标 / 手柄事件 | InputEvent, mouse click, joypad | `InputEvent` | `class_inputevent.rst` |
| 按钮点击 | button click, UI button, pressed | `Button` → `BaseButton` | `class_basebutton.rst`（signal 定义） |
| UI 容器 / 控件 | Control, theme, label | `Control` | `class_control.rst` |
| 节点关系 | node, parent, child, tree | `Node` | `class_node.rst` |
| 3D 节点 / 变换 | Node3D, transform, position | `Node3D` | `class_node3d.rst` |
| 切换场景 | change scene, instantiate, load scene | `SceneTree` / `PackedScene` | `class_scenetree.rst`、`class_packedscene.rst` |
| 读 / 写文件 | FileAccess, save file, open file | `FileAccess` / `DirAccess` | `class_fileaccess.rst` |
| JSON | parse json, stringify | `JSON` | `class_json.rst` |
| 自定义资源 | Resource, custom resource | `Resource` | `class_resource.rst` |
| 物理体 | rigidbody, collision, collider | `RigidBody3D` / `CollisionShape3D` | `class_rigidbody3d.rst` |
| 触发器 / 重叠 | area, trigger, overlap | `Area2D/3D` | `class_area3d.rst` |
| 射线检测 | raycast, line of sight | `RayCast2D/3D` | `class_raycast3d.rst` |
| 动画 | animation, play animation | `AnimationPlayer` | `class_animationplayer.rst` |
| 补间 | tween, lerp | `Tween` | `class_tween.rst` |
| 音效 | play sound, audio | `AudioStreamPlayer` | `class_audiostreamplayer.rst` |
| 相机 | camera, view | `Camera2D/3D` | `class_camera3d.rst` |
| 着色器 | shader, material, shader_parameter | `Shader` / `ShaderMaterial` | `class_shadermaterial.rst` |
| 寻路 | pathfinding, navigate | `NavigationAgent2D/3D` | `class_navigationagent3d.rst` |
| 多人 | multiplayer, rpc, sync | `MultiplayerAPI` / `MultiplayerPeer` | `class_multiplayerapi.rst` |
| 计时 | timer, wait | `Timer` | `class_timer.rst` |
| 版本迁移 | upgrade, breaking change | — | `../tutorials/migrating/upgrading_to_godot_4.7.rst`（前缀同上但去掉 `classes/`） |

未命中 → 转 `topics.md`；仍未命中 = FAIL。
