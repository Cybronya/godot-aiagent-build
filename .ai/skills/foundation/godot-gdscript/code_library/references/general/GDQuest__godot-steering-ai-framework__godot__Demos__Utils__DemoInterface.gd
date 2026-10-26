# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/Utils/DemoInterface.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends PanelContainer

@export_multiline var text_bbcode := "": set = set_text_bbcode

@onready var rich_text_label: RichTextLabel = $MarginContainer/RichTextLabel


func _ready():
	get_tree().root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_tree().root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_EXPAND

func set_text_bbcode(value: String) -> void:
	text_bbcode = value
	if not rich_text_label:
		await self.ready
	rich_text_label.text = text_bbcode
