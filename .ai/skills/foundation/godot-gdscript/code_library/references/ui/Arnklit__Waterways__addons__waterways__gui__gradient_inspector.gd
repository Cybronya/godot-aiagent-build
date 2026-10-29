# Source:  https://github.com/Arnklit/Waterways/blob/main/addons/waterways/gui/gradient_inspector.gd
# Repo:    Arnklit/Waterways (star 1342) | License: MIT | Collected: 2026-10-29
# Commit:  cd2e2193fe2c
# Copyright © 2021 Kasper Arnklit Frandsen - MIT License
# See `LICENSE.md` included in the source distribution for details.
tool
extends HBoxContainer


func set_value(gradient : Transform):
	$Color1.color = Color(gradient[0].x, gradient[0].y, gradient[0].z)
	$Color2.color = Color(gradient[1].x, gradient[1].y, gradient[1].z)
	$Gradient.material.set_shader_param("color1", $Color1.color)
	$Gradient.material.set_shader_param("color2", $Color2.color)


func get_value() -> Transform:
	var gradient = Transform()
	gradient[0] = Vector3($Color1.color.r, $Color1.color.g, $Color1.color.b)
	gradient[1] = Vector3($Color2.color.r, $Color2.color.g, $Color2.color.b)
	return gradient
