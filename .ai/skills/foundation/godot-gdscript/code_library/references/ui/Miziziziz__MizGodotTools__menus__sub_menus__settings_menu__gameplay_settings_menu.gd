# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/menus/sub_menus/settings_menu/gameplay_settings_menu.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
extends ScrollContainer

@onready var difficulty_drop_down: OptionButton = $VBoxContainer/Difficulty/OptionButton

func _ready():
	difficulty_drop_down.item_selected.connect(update_difficulty)

func update_difficulty(_difficulty_val:int):
	pass # TODO manual implementation

func load_settings_data(settings_data: Dictionary):
	if "difficulty" in settings_data:
		difficulty_drop_down.selected = roundi(settings_data.difficulty)

func get_settings_save_data()->Dictionary:
	return {
		"difficulty": difficulty_drop_down.selected,
	}
