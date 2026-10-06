# Intents Routing（Hand-authored）

任务意图 → Source 位置。

路径基准 `references/4.7/`，正文前缀统一为：

```text
../../../../godot-official-docs_sources/4.7/
```

类文件规则：`classes/class_<name 小写>.rst`。继承成员先看 `api/INDEX.md` 的继承链规则。

| Query | Target | Source Path（接在前缀后） |
|---|---|---|
| 玩家移动 / character controller | `CharacterBody2D/3D` | `classes/class_characterbody3d.rst`；教程 `tutorials/physics/` |
| 键盘 / 手柄输入（WASD） | `Input` / `InputMap` / `InputEvent` | `classes/class_input.rst`；教程 `tutorials/inputs/` |
| UI 按钮 / 界面 | `Button` → `BaseButton` | `classes/class_basebutton.rst`；教程 `tutorials/ui/` |
| 切换场景 / 场景管理 | `SceneTree` / `PackedScene` | `classes/class_scenetree.rst`；入门 `getting_started/step_by_step/` |
| 文件读写 / JSON | `FileAccess` / `JSON` | `classes/class_fileaccess.rst`、`classes/class_json.rst`；教程 `tutorials/io/` |
| 多人游戏 | `MultiplayerAPI` | `classes/class_multiplayerapi.rst`；教程 `tutorials/networking/` |
| Shader / 材质 | `Shader` / `ShaderMaterial` | `classes/class_shadermaterial.rst`；教程 `tutorials/shaders/` |
| 动画 | `AnimationPlayer` / `Tween` | `classes/class_animationplayer.rst`；教程 `tutorials/animation/` |
| 物理（刚体 / 碰撞 / 射线） | `RigidBody3D` / `Area3D` / `RayCast3D` | `classes/class_raycast3d.rst` 等；教程 `tutorials/physics/` |
| 2D / 3D 游戏 | — | 教程 `tutorials/2d/`、`tutorials/3d/` |
| 音频 | `AudioStreamPlayer` | `classes/class_audiostreamplayer.rst`；教程 `tutorials/audio/` |
| 导航寻路 | `NavigationAgent3D` | `classes/class_navigationagent3d.rst`；教程 `tutorials/navigation/` |
| 资源 / 自定义 Resource | `Resource` | `classes/class_resource.rst`；教程 `tutorials/io/` |
| 导出 / 平台发布 | — | 教程 `tutorials/export/`、`tutorials/platform/` |
| 编辑器扩展 | — | 教程 `tutorials/plugins/`；`engine_details/editor/` |
| 性能 | — | 教程 `tutorials/performance/`、`tutorials/best_practices/` |
| GDScript 语法 | `@GDScript` / `@GlobalScope` | `classes/class_@gdscript.rst`；教程 `tutorials/scripting/` |
| 版本升级 / 破坏性变更 | — | `tutorials/migrating/upgrading_to_godot_4.7.rst` |
| 第一次使用 Godot | — | `getting_started/introduction/`、`getting_started/first_2d_game/`、`getting_started/first_3d_game/` |

路由顺序：本表 → `keywords.md` → `topics.md`。全部未命中 = FAIL，按 SKILL.md Failure Handling 处理。
