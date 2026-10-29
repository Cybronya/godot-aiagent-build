# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/utility/input_field_resource/pa_array_remove.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends "prop_action.gd"


#-------------------------------------------------------------------------------
# Remove an array element at index
#-------------------------------------------------------------------------------




var index:int = -1




func _init(__prop:String, __val, __index:int):
	super(__prop, __val)
	set_meta("class", "PA_ArrayRemove")
	
	index = __index
	can_create_history = true


func _to_string():
	return "%s: [prop: %s, val: %s, index: %d, can_create_history: %s]" % [get_meta("class"), prop, str(val), index, str(can_create_history)]


func duplicate(deep:bool = false):
	var copy = self.get_script().new(prop, val, index)
	copy.can_create_history = can_create_history
	return copy
