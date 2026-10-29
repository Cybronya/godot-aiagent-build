# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/compute/post_shader/main.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node3D

@onready var compositor: Compositor = $WorldEnvironment.compositor


func _input(input_event: InputEvent) -> void:
	if input_event.is_action_pressed(&"toggle_grayscale_effect"):
		compositor.compositor_effects[0].enabled = not compositor.compositor_effects[0].enabled
		update_info_text()

	if input_event.is_action_pressed(&"toggle_shader_effect"):
		compositor.compositor_effects[1].enabled = not compositor.compositor_effects[1].enabled
		update_info_text()


func update_info_text() -> void:
	$Info.text = """Grayscale effect: %s
Shader effect: %s
""" % [
	"Enabled" if compositor.compositor_effects[0].enabled else "Disabled",
	"Enabled" if compositor.compositor_effects[1].enabled else "Disabled",
]
