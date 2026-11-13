# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/objects/interactable_area.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
@tool
class_name XRToolsInteractableArea
extends Area3D
## Area3D that emits [XRToolsPointerEvent]s whenever pointed at by
## [XRToolsFunctionPointer]s


## Emitted when pointer event occurs on area
signal pointer_event(event: XRToolsPointerEvent)


## Adds support for [method is_xr_class] on XRTools classes
func is_xr_class(xr_name: String) -> bool:
	return xr_name == "XRToolsInteractableArea"
