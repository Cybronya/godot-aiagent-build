# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/esc_interaction_location.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
@tool
@icon("res://addons/escoria-core/design/esc_location.svg")
## A simple node extending Position2D with a global ID so that it can be
## referenced in ESC Scripts. Movement-based commands like `walk_to_pos` will
## automatically use an `ESCLocation` that is a child of the destination node.[br]
## Commands like `turn_to`--which are not movement-based--will ignore child
## `ESCLocation`s and refer to the parent node.
class_name ESCInteractionLocation
extends ESCLocation

## Whether this object's class is the same as given string class name.[br]
## [br]
## #### Parameters[br]
## [br]
## | Name | Type | Description | Required? |[br]
## |:-----|:-----|:------------|:----------|[br]
## |p_classname|`String (4.6.x), StringName (4.7.x)`|Class name to compare against this location.|yes|[br]
## [br]
## #### Returns[br]
## [br]
## Returns a `bool` value. (`bool`)
func is_class(p_classname) -> bool:
	return p_classname == "ESCInteractionLocation"
