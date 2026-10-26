# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/base/nodes/menus/options_menu/option_control/vector_2_list_option_control.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
class_name Vector2ListOptionControl
extends ListOptionControl

func _value_title_map(value : Variant) -> String:
	if value is Vector2 or value is Vector2i:
		return "%d x %d" % [value.x , value.y]
	else:
		return super._value_title_map(value)
