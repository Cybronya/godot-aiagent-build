# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/shaders/animated_stroke_static.gdshader
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
shader_type canvas_item;

#include "res://src/shaders/animated_stroke_common.gdshaderinc"

varying float cos_skew;
varying float max_rotation_factor;

void vertex() {
	cos_skew = get_cos_skew(MODEL_MATRIX[0].xy, MODEL_MATRIX[1].xy);
	max_rotation_factor = get_max_rotation_factor(MODEL_MATRIX[0].xy);
}

void fragment() {
	COLOR = fragment_common(UV, 0.0, cos_skew, max_rotation_factor);
}
