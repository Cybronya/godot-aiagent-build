# API INDEX — Class Reference 导航（Hand-authored）

所有 Source 路径以 `references/4.7/` 为基准：
`../../../../godot-official-docs_sources/4.7/classes/class_<name 小写>.rst`

## Frequently Used Classes

| Class | Category | Inherits |
|---|---|---|
| `Object` | Core | — |
| `RefCounted` | Core | Object |
| `Node` | Scene | Object |
| `Node2D` | Scene | CanvasItem < Node |
| `Node3D` | Scene | Node |
| `CanvasItem` | Scene | Node |
| `SceneTree` | Scene | MainLoop |
| `PackedScene` | Resources | Resource |
| `Resource` | Resources | RefCounted |
| `Input` | Input | Object |
| `InputMap` | Input | Object |
| `InputEvent` | Input | Resource |
| `CharacterBody2D` | Physics | PhysicsBody2D |
| `CharacterBody3D` | Physics | PhysicsBody3D |
| `RigidBody2D` / `RigidBody3D` | Physics | PhysicsBody2D / 3D |
| `Area2D` / `Area3D` | Physics | CollisionObject2D / 3D |
| `RayCast2D` / `RayCast3D` | Physics | Node2D / Node3D |
| `Control` | UI | CanvasItem |
| `BaseButton` | UI | Control |
| `Button` | UI | BaseButton |
| `Label` | UI | Control |
| `FileAccess` | File I/O | RefCounted |
| `DirAccess` | File I/O | RefCounted |
| `JSON` | File I/O | RefCounted |
| `Timer` | Scene | Node |
| `AnimationPlayer` | Animation | AnimationMixer |
| `Tween` | Animation | RefCounted |
| `Camera2D` / `Camera3D` | Rendering | Node2D / Node3D |
| `MultiplayerAPI` | Networking | RefCounted |
| `Shader` / `ShaderMaterial` | Rendering | Resource |

Source path 模板（把 `<name>` 换成上表小写类名即可）：

```text
../../../../godot-official-docs_sources/4.7/classes/class_<name>.rst
```

## Inheritance Navigation — 继承链规则（重要）

如果某个 API 成员（method / property / signal / enum）在目标类文档里找不到，
它很可能是继承来的。按以下顺序处理：

1. 查 `classes.md` 中该类的 Inherits 链
2. 打开直接父类的 reference（如 `Button` → `BaseButton`）
3. 在父类文档中解析继承的成员；仍找不到则继续上溯

示例：`Button.pressed` signal 定义在 `BaseButton`：

```text
Button（class_button.rst，只有用法示例）
→ BaseButton（class_basebutton.rst，signal pressed 的定义）
```

典型继承链：

```text
CharacterBody3D → PhysicsBody3D → CollisionObject3D → Node3D → Node → Object
Button → BaseButton → Control → CanvasItem → Node
```

禁止因目标类文档没有该成员就回答「不存在」——先走继承链。

## 查找入口

- 按领域浏览类：`categories.md`
- 按类名精确查找（全量）：`classes.md`（Generated，1078 类）
- 主题 / 概念文档（非 API）：`../routing/topics.md`
