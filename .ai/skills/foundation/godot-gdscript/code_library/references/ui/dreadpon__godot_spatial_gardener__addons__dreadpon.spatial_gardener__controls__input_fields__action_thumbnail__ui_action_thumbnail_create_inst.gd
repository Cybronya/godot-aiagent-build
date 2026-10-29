# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/controls/input_fields/action_thumbnail/ui_action_thumbnail_create_inst.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends "ui_action_thumbnail.gd"


#-------------------------------------------------------------------------------
# An action thumbnail version that is pressed to create new action thumbnails
#-------------------------------------------------------------------------------


func _init():
	set_meta("class", "UI_ActionThumbnailCreateInst")




#-------------------------------------------------------------------------------
# Resizing
#-------------------------------------------------------------------------------


func _set_default_textures():
	super._set_default_textures()
	%TextureRect.texture = new_texture




#-------------------------------------------------------------------------------
# Interaction flags
#-------------------------------------------------------------------------------


# Overrides parent function, since it has no features to set
func enable_features_to_flag(flag:int, state:bool):
	return
