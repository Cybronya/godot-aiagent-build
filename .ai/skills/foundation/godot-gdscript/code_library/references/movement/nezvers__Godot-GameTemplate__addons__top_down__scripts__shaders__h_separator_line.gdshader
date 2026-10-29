# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/shaders/h_separator_line.gdshader
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
shader_type canvas_item;

uniform vec4 tint:source_color;

void fragment() {
	float s = (UV.x - 0.5) * 2.0;
	float a = cos(s * (PI * 0.5));
	COLOR = vec4(tint.xyz, a * 2.0 * tint.a);
}
