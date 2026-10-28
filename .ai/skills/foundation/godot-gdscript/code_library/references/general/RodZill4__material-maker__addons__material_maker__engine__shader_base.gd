# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/engine/shader_base.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends RefCounted
class_name MMShaderBase


func _init():
	pass

func set_shader(shader : String) -> bool:
	return false

func get_parameters() -> Dictionary:
	return {}

func set_parameter(name : String, value) -> void:
	pass
