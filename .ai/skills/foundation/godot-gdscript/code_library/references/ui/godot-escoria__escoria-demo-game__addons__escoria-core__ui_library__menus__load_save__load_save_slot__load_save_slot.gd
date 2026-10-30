# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/ui_library/menus/load_save/load_save_slot/load_save_slot.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends Button


func set_slot_name_date(p_name: String, p_date: String):
	$VBoxContainer/slot_name.text = p_name
	$VBoxContainer/date.text = p_date

