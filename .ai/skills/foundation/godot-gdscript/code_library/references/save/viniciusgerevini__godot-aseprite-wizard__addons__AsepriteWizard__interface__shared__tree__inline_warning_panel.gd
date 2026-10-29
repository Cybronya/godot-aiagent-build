# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/shared/tree/inline_warning_panel.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends PanelContainer

@onready var _message = $MarginContainer/HBoxContainer/Label

func _ready():
	_configure_source_warning()


func _configure_source_warning():
	var sb = self.get_theme_stylebox("panel")
	var color = EditorInterface.get_editor_settings().get_setting("interface/theme/accent_color")
	color.a = 0.2
	sb.bg_color = color
	self.get_node("MarginContainer/HBoxContainer/Icon").texture = get_theme_icon("NodeInfo", "EditorIcons")


func set_text(text: String):
	_message.text = text
