# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/objects/snap_path_guide.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@tool
class_name XRToolsSnapPathGuide
extends Marker3D


## XRToolsSnapRailGuide depicts a guide for [XRToolsSnapPath] to judge the
## length of an [XRToolsPickable], helping place pickables within its bounds.
## Add as a child node to any [XRToolsPickable], then move negatively along
## the Z-Axis to define a length.


var length : float:
	get:
		return abs(position.z)
