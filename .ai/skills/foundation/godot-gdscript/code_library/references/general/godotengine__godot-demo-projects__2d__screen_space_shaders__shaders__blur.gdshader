# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/screen_space_shaders/shaders/blur.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
shader_type canvas_item;

uniform sampler2D screen_texture : hint_screen_texture, filter_linear_mipmap;
uniform float amount : hint_range(0.0, 5.0);

void fragment() {
	COLOR.rgb = textureLod(screen_texture, SCREEN_UV, amount).rgb;
}
