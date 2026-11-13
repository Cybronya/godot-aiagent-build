# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/objects/wind_area.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@tool
class_name XRToolsWindArea
extends Area3D

## Vector (direction and magnitude) of wind in this area
@export var wind_vector : Vector3 = Vector3.ZERO

## Wind drag factor
@export var drag : float = 1.0


# Add support for is_xr_class on XRTools classes
func is_xr_class(xr_name:  String) -> bool:
	return xr_name == "XRToolsWindArea"
