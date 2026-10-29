# Source:  https://github.com/mbrlabs/Lorien/blob/main/lorien/InfiniteCanvas/Cursor/cursor.gdshader
# Repo:    mbrlabs/Lorien (star 6865) | License: MIT | Collected: 2026-10-27
# Commit:  17e32227dfce
shader_type canvas_item;

uniform sampler2D SCREEN_TEXTURE: hint_screen_texture, filter_linear_mipmap;

void fragment() {
	vec4 background_color = texture(SCREEN_TEXTURE, SCREEN_UV);
	vec4 texture_color = texture(TEXTURE, UV);

	vec3 inverted = vec3(texture_color.rgb - background_color.rgb);
	float grayscale = (inverted.r + inverted.g + inverted.b) / 3.0;
	grayscale = min(1.0, grayscale*1.25);

	COLOR = vec4(grayscale, grayscale, grayscale, texture_color.a);
}