# Source:  https://github.com/MrEliptik/godot_ui_components/blob/main/scenes/balatro/shaders/noise_move.gdshader
# Repo:    MrEliptik/godot_ui_components (star 777) | License: MIT | Collected: 2026-10-31
# Commit:  22d235569061
shader_type canvas_item;

uniform sampler2D noise_texture;
uniform vec2 dir = vec2(0.5, 0.5);

void fragment() {
	//COLOR.rgb = texture(noise_texture, UV + (normalize(dir) * TIME)).rgb;
	COLOR.rgb = texture(noise_texture, UV).rgb;
}

