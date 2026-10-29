# Source:  https://github.com/HungryProton/scatter/blob/main/addons/proton_scatter/src/stack/inspector_plugin/ui/modifier/components/header/parameter_spinbox.gd
# Repo:    HungryProton/scatter (star 3017) | License: MIT | Collected: 2026-10-28
# Commit:  7198cc00078e
@tool
extends "../base_parameter.gd"


@onready var _spinbox = $SpinBox


func _ready() -> void:
	_spinbox.value_changed.connect(_on_value_changed)


func get_value() -> int:
	return int(_spinbox.get_value())


func _set_value(val: int) -> void:
	_spinbox.set_value(val)
