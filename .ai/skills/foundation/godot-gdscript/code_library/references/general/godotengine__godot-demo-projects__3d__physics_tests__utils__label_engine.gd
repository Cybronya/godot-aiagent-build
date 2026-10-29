# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/label_engine.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label


func _ready() -> void:
	var engine_name: String = ""
	match System.get_physics_engine():
		System.PhysicsEngine.GODOT_PHYSICS:
			engine_name = "GodotPhysics 3D"
		System.PhysicsEngine.JOLT_PHYSICS:
			engine_name = "Jolt Physics"
		System.PhysicsEngine.OTHER:
			var engine_setting := str(ProjectSettings.get_setting("physics/3d/physics_engine"))
			engine_name = "Other (%s)" % engine_setting

	text = "Physics engine: %s" % engine_name
