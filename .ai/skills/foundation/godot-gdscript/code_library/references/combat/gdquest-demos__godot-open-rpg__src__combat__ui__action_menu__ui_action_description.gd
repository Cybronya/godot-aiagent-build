# Source:  https://github.com/gdquest-demos/godot-open-rpg/blob/main/src/combat/ui/action_menu/ui_action_description.gd
# Repo:    gdquest-demos/godot-open-rpg (star 3028) | License: MIT | Collected: 2026-10-26
# Commit:  d59f2f71bc04
## A text bar that displays the [member BattlerAction.description] of a [BattlerAction].
##
## This bar is shown to give the player information about actions as they select one from the
## [UIActionMenu].
class_name UIActionDescription extends MarginContainer

@export var description: = "":
	set(value):
		description = value
		
		if not is_inside_tree():
			await ready
			
		_description_label.text = description
		if description.is_empty():
			hide()
		else:
			show()

@onready var _description_label: = $CenterContainer/MarginContainer/Description as Label


func _ready() -> void:
	if not Engine.is_editor_hint():
		hide()
