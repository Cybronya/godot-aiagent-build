# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/combat/ui/action_menu/ui_action_button.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
## A button representing a single [BattlerAction], shown in the player's [UIActionMenu].
class_name UIActionButton extends TextureButton

## Setup the button's icon and label to match a given [BattlerAction].
var action: BattlerAction:
	set(value):
		action = value
		
		if not is_inside_tree():
			await ready
		
		_icon.texture = action.icon
		_name_label.text = action.name
		
		await get_tree().process_frame
		custom_minimum_size = $MarginContainer.size

@onready var _icon: = $MarginContainer/Items/Icon
@onready var _name_label: = $MarginContainer/Items/Name


func _ready() -> void:
	pressed.connect(release_focus)
