# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/lights_and_shadows/day_night_cycle.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends DirectionalLight3D


func _process(delta: float) -> void:
	rotate_object_local(Vector3.RIGHT, 0.025 * delta)
