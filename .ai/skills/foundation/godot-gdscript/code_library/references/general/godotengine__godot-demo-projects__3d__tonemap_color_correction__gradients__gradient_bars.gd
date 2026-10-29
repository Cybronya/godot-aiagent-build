# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/tonemap_color_correction/gradients/gradient_bars.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
class_name GradientBars extends Node3D

@export var sdr_bar: GeometryInstance3D
@export var hdr_bar: GeometryInstance3D
@export var label: Label3D

func set_num_steps(steps: int) -> void:
	var shader_mat: ShaderMaterial = hdr_bar.material_override as ShaderMaterial
	if shader_mat:
		shader_mat.set_shader_parameter(&"steps", min(1, steps))

func set_color(color: Color) -> void:
	var shader_mat: ShaderMaterial = sdr_bar.material_override as ShaderMaterial
	if shader_mat:
		shader_mat.set_shader_parameter(&"my_color", color)

	shader_mat = hdr_bar.material_override as ShaderMaterial
	if shader_mat:
		shader_mat.set_shader_parameter(&"my_color", color)

	label.text = "#" + color.to_html(false)
