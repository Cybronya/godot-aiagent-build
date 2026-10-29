# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/windows/main_menu_credits_window.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
@tool
extends PopupWindowSceneContainer

func _ready() -> void:
	super._ready()
	if instance and instance.has_signal(&"end_reached"):
		instance.connect(&"end_reached", close)
