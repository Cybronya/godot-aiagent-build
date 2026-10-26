# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/label_engine.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Label

func _ready() -> void:
	var engine_name: String = ""

	match System.get_physics_engine():
		System.PhysicsEngine.GODOT_PHYSICS:
			engine_name = "GodotPhysics 2D"
		System.PhysicsEngine.OTHER:
			var engine_setting := String(ProjectSettings.get_setting("physics/2d/physics_engine"))
			engine_name = "Other (%s)" % engine_setting

	text = "Physics engine: %s" % engine_name
