# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/multiple_windows/scenes/text_field.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends LineEdit


@export var submit_button: Button


func _ready() -> void:
	text_submitted.connect(func(_s): clear(), ConnectFlags.CONNECT_DEFERRED)
	if submit_button:
		submit_button.pressed.connect(func(): text_submitted.emit(text))
