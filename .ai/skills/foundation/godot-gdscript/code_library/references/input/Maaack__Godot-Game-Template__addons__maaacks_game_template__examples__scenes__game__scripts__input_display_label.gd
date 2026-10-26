# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/game/scripts/input_display_label.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends Label

@onready var action_names := AppSettings.get_action_names()

func _get_inputs_as_string() -> String:
	var all_inputs : String = ""
	var is_first : bool = true
	for action_name in action_names:
			if Input.is_action_pressed(action_name):
				if is_first:
					is_first = false
					all_inputs += action_name
				else:
					all_inputs += " + " + action_name
	return all_inputs

func _process(_delta : float) -> void:
	if Input.is_anything_pressed():
		text = _get_inputs_as_string()
	else:
		text = ""
