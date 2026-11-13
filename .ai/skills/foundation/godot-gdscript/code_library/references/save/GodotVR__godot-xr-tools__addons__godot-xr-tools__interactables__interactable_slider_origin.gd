# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/interactables/interactable_slider_origin.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@tool
class_name XRToolsInteractableSliderOrigin
extends Node3D

## XR Tools Interactable Slider Origin script
##
## The interactable slider origin is parent of an [XRToolsInteractableSlider]
## node and defines the extent of travel the slider can move throught.

## Smallest distance of the slider
@export var limit_minimum := 0.0 : set = set_limit_minimum

## Largest distance of the slider
@export var limit_maximum := 1.0 : set = set_limit_maximum


# Checks for configuration warnings
func _get_configuration_warnings() -> PackedStringArray:
	var ret := PackedStringArray()

	# Check for invalid limits
	if limit_maximum <= limit_minimum:
		ret.append("Invalid slider range")

	# Check for a hinge child
	if get_children().all(
			func(n: Node) -> bool:
				return not n is XRToolsInteractableSlider
	):
		ret.append("Missing XRToolsInteractableSlider child")

	return ret


## Adds support for [method is_xr_class] on XRTools classes
func is_xr_class(xr_name: String) -> bool:
	return xr_name == "XRToolsInteractableSliderOrigin"


## Handles setting the maximum limit
func set_limit_maximum(p_limit_maximum: float) -> void:
	limit_maximum = p_limit_maximum
	update_configuration_warnings()
	update_gizmos()


## Handles setting the minimum limit
func set_limit_minimum(p_limit_minimum: float) -> void:
	limit_minimum = p_limit_minimum
	update_configuration_warnings()
	update_gizmos()
