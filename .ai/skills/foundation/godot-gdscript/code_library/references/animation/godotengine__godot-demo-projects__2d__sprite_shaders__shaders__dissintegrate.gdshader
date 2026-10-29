# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/sprite_shaders/shaders/dissintegrate.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
shader_type canvas_item;
render_mode blend_mix;

uniform float amount = 20.0;

void fragment() {
	vec2 uv = UV * 0.05;
	float a = fract(sin(dot(UV, vec2(12.9898, 78.233))) * 438.5453);
	vec4 col = texture(TEXTURE, UV);

	col.a *= pow(a, amount);

	COLOR = col;
}
