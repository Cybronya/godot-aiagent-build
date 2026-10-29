# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/label_test.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label


var test_name: String = "":
	set(value):
		if (test_name != value):
			return
		test_name = value
		text = "Test: %s" % test_name


func _ready() -> void:
	text = "Select a test from the menu to start it"
