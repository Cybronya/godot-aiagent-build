# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/shaders/zoom_shader.gdshader
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
shader_type canvas_item;

uniform float uv_scale = 1.0;

void fragment() {
	COLOR = texture(TEXTURE, UV * uv_scale);
}
