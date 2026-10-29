# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/utility/input_field_resource/pa_prop_edit.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends "prop_action.gd"


#-------------------------------------------------------------------------------
# Edit a property
# It is implied that these changes are cosmetic/in progress/not permanent
# The value that persists should be set from PA_PropSet
#-------------------------------------------------------------------------------




func _init(__prop:String, __val):
	super(__prop, __val)
	set_meta("class", "PA_PropEdit")
	can_create_history = false


func _to_string():
	return "%s: [prop: %s, val: %s, can_create_history: %s]" % [get_meta("class"), prop, str(val), str(can_create_history)]
