# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/objects/interactable_body.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
class_name XRToolsInteractableBody
extends Node3D
## [PhysicsBody3D] that emits [XRToolsPointerEvent]s when pointed at by
## [XRToolsFunctionPointer]s.
##
## Note: This should extend from [PhysicsBody3D],
## but [url]https://github.com/godotengine/godot/issues/46073[/url]


## Emitted when pointer event occurs on body
signal pointer_event(event: XRToolsPointerEvent)
