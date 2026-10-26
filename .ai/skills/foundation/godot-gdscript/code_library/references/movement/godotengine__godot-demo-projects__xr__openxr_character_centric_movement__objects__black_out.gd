# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/xr/openxr_character_centric_movement/objects/black_out.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends Node3D

@export_range(0, 1, 0.1) var fade := 0.0:
	set(value):
		fade = value
		if is_inside_tree():
			_update_fade()

var material: ShaderMaterial


func _update_fade() -> void:
	if fade == 0.0:
		$MeshInstance3D.visible = false
	else:
		if material:
			material.set_shader_parameter(&"albedo", Color(0.0, 0.0, 0.0, fade))
		$MeshInstance3D.visible = true


func _ready() -> void:
	material = $MeshInstance3D.material_override
	_update_fade()
