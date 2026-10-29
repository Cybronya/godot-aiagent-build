# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/sprite_shaders/shaders/offsetshadow.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
shader_type canvas_item;
render_mode blend_mix;

uniform vec2 offset = vec2(8.0, 8.0);
uniform vec4 modulate : source_color;

void fragment() {
	vec2 ps = TEXTURE_PIXEL_SIZE;

	vec4 shadow = vec4(modulate.rgb, texture(TEXTURE, UV - offset * ps).a * modulate.a);
	vec4 col = texture(TEXTURE, UV);

	COLOR = mix(shadow, col, col.a);
}
