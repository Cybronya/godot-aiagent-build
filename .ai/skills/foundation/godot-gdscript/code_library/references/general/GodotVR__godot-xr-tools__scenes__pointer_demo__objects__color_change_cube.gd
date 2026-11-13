# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/scenes/pointer_demo/objects/color_change_cube.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
extends RigidBody3D


var _material := StandardMaterial3D.new()


# Called when the node enters the scene tree for the first time.
func _ready():
	# Generate a random material color
	_set_random_color()

	# Change the mesh to use our generated material
	$MeshInstance3D.material_override = _material


# Handle pointer events
func pointer_event(event : XRToolsPointerEvent) -> void:
	# When pressed, randomize the color
	if event.event_type == XRToolsPointerEvent.Type.PRESSED:
		_set_random_color()


# Sets a random color on the material
func _set_random_color():
	# Set the albedo color to a random value
	_material.albedo_color = Color(randf(), randf(), randf())
