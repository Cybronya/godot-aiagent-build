# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/shaders/progress_fill.gdshader
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
shader_type canvas_item;

uniform float value:hint_range(0.0, 1.0);

void fragment() {
	COLOR.a = step(UV.x, value);
}


