# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/src/Shaders/SetIndices.gdshader
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  fae9327992f1
shader_type texture_blit;
render_mode blend_disabled;

#include "res://src/Shaders/FindPaletteColorIndex.gdshaderinc"
uniform sampler2D rgb_texture : filter_nearest;
uniform sampler2D palette_texture : filter_nearest;


void blit() {
	vec4 color = texture(rgb_texture, UV);
	if (color.a <= 0.0001) {
		COLOR0.r = 0.0;
	}
	else {
		int color_index = find_index(color, textureSize(palette_texture, 0).x, palette_texture);
		COLOR0.r = float(color_index + 1) / 255.0;
	}
}
