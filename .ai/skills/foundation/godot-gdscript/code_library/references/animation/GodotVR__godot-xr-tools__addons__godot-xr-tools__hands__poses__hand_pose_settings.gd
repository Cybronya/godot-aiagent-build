# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/hands/poses/hand_pose_settings.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@tool
@icon("res://addons/godot-xr-tools/editor/icons/hand.svg")
class_name XRToolsHandPoseSettings
extends Resource


## XR Tools Hand Pose Settings Resource
##
## This resource defines the settings for hand poses such as the poses for
## hand-open and hand-closed.


## Hand-open pose
@export var open_pose : Animation : set = set_open_pose

## Hand-closed pose
@export var closed_pose : Animation : set = set_closed_pose


# Called when the open pose is changed
func set_open_pose(p_open_pose : Animation) -> void:
	open_pose = p_open_pose
	emit_changed()


# Called when the closed pose is changed
func set_closed_pose(p_closed_pos : Animation) -> void:
	closed_pose = p_closed_pos
	emit_changed()
