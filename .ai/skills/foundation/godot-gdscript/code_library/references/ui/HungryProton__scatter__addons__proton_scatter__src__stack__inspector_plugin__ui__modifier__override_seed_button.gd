# Source:  https://github.com/HungryProton/scatter/blob/main/addons/proton_scatter/src/stack/inspector_plugin/ui/modifier/override_seed_button.gd
# Repo:    HungryProton/scatter (star 3017) | License: MIT | Collected: 2026-10-28
# Commit:  7198cc00078e
@tool
extends Control


@onready var _button: Button = $OverrideGlobalSeed/Button
@onready var _spinbox_root: Control = $SpinBoxRoot


func _ready():
	_button.toggled.connect(_on_toggled)


func _on_toggled(enabled: bool) -> void:
	_spinbox_root.visible = enabled
