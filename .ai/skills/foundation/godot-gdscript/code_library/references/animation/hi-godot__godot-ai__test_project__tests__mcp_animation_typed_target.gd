# Source:  https://github.com/hi-godot/godot-ai/blob/main/test_project/tests/mcp_animation_typed_target.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends Node3D

## Test fixture: typed properties no stock node exposes, so the animation
## coercion and interpolation regressions can target a real property.
## `cell` is the Vector3i destination for the int32-range test; `quat` is the
## Quaternion destination for the rotation-contract test.

@export var cell: Vector3i = Vector3i.ZERO
@export var quat: Quaternion = Quaternion.IDENTITY
