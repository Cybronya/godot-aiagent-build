# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/menus/sub_menus/sub_menu.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
class_name SubMenu extends Control

@onready var back_button = $BackButton

@export var custom_focus_button : Button #optional

func switch_to_this_menu():
	show()
	back_button.grab_focus()
	if custom_focus_button:
		custom_focus_button.grab_focus()
