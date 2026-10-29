# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/components/color_picker/color_picker.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
extends MarginContainer

@onready var color_picker_button: ColorPickerButton = $ColorPickerButton

signal color_selected(color: Color)


func _ready():
	color_picker_button.color_changed.connect(func(color): color_selected.emit(color))


func set_color(color: Color) -> void:
	color_picker_button.color = color
