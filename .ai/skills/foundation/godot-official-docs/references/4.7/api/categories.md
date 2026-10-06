# API Categories — 按领域分类的类导航（Hand-authored）

先选领域，再从类名直达 Source。所有路径以 `references/4.7/` 为基准目录，
格式：`../../../../godot-official-docs_sources/4.7/classes/class_<name 小写>.rst`。

继承成员不在本类文档中时，按 `api/INDEX.md` 的继承链规则上溯父类。

## Input

`Input` · `InputMap` · `InputEvent` · `InputEventKey` · `InputEventMouseButton` · `InputEventMouseMotion` · `InputEventJoypadButton`

## Physics

`CharacterBody2D` · `CharacterBody3D` · `RigidBody2D` · `RigidBody3D` · `Area2D` · `Area3D` · `PhysicsBody2D` · `PhysicsBody3D` · `CollisionObject2D` · `CollisionObject3D` · `CollisionShape2D` · `CollisionShape3D` · `RayCast2D` · `RayCast3D`

## UI

`Control` · `BaseButton` · `Button` · `Label` · `Panel` · `LineEdit` · `TextEdit` · `Container` · `BoxContainer` · `VBoxContainer` · `HBoxContainer` · `Theme`

## Scene & Node

`Node` · `Node2D` · `Node3D` · `CanvasItem` · `SceneTree` · `PackedScene` · `Viewport` · `Window` · `Timer`

## Resources & File I/O

`Resource` · `RefCounted` · `Object` · `FileAccess` · `DirAccess` · `JSON` · `ConfigFile` · `Image` · `ProjectSettings` · `Engine`

## Animation & Audio

`AnimationPlayer` · `AnimationTree` · `Tween` · `AudioStreamPlayer` · `AudioStreamPlayer2D` · `AudioStreamPlayer3D`

## Rendering & Shaders

`Camera2D` · `Camera3D` · `Light3D` · `Sprite2D` · `Shader` · `ShaderMaterial` · `Material` · `Mesh` · `Environment` · `WorldEnvironment`

## Navigation

`NavigationAgent2D` · `NavigationAgent3D` · `NavigationRegion2D` · `NavigationRegion3D`

## Networking / Multiplayer

`MultiplayerAPI` · `MultiplayerPeer` · `SceneMultiplayer`

> 分类为 Hand-authored；`tools/update_docs.py` 会验证以上每个类在 Source 中都存在。
