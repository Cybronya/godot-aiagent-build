# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/sprite_shaders/shaders/silouette.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
shader_type canvas_item;

render_mode blend_mix;
uniform vec4 modulate : source_color;

void fragment() {
	COLOR = vec4(modulate.rgb, texture(TEXTURE, UV).a * modulate.a);
}
