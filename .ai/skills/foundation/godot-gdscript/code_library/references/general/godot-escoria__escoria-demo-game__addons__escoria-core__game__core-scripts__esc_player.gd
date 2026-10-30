# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/esc_player.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
@tool
@icon("res://addons/escoria-core/design/esc_player.svg")
## An Escoria playable character.
class_name ESCPlayer
extends ESCItem


## Whether the player can be hovered over and actions performed on like an item.
## This allows the user to perform actions or use items on the player character.
@export var selectable: bool = false

## Constructor method.[br]
## [br]
## #### Parameters[br]
## [br]
## None.
## [br]
## #### Returns[br]
## [br]
## Returns nothing.
func _init():
	# A player is always movable
	is_movable = true
	_force_registration = true


## Ready method.[br]
## [br]
## #### Parameters[br]
## [br]
## None.
## [br]
## #### Returns[br]
## [br]
## Returns nothing.
func _ready():
	super()
