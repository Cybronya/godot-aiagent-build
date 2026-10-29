# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Character/default_portrait.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends DialogicPortrait

## Default portrait scene.
## The parent class has a character and portrait variable.

@export_group('Main')
@export_file var image := ""


## Load anything related to the given character and portrait
func _update_portrait(passed_character:DialogicCharacter, passed_portrait:String) -> void:
	apply_character_and_portrait(passed_character, passed_portrait)

	apply_texture($Portrait, image)
