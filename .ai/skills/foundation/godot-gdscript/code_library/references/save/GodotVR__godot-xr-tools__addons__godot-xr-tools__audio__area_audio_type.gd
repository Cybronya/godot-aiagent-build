# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/audio/area_audio_type.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@tool
@icon("res://addons/godot-xr-tools/editor/icons/audio.svg")
class_name XRToolsAreaAudioType
extends Resource


## XRTools Area Audio Type Resource
##
## This resource defines the audio stream to play when
## a objects enters it

## Surface name
@export var name: String = ""

## Optional audio stream to play when the player lands on this surface
@export var touch_sound: AudioStream


# This method checks for configuration issues.
func _get_configuration_warnings() -> PackedStringArray:
	var warnings := PackedStringArray()

	if name == "":
		warnings.append("Area audio type must have a name")

	# Return warnings
	return warnings
