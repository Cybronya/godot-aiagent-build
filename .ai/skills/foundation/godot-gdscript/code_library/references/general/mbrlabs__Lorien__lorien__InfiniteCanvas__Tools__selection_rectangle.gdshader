# Source:  https://github.com/mbrlabs/Lorien/blob/main/lorien/InfiniteCanvas/Tools/selection_rectangle.gdshader
# Repo:    mbrlabs/Lorien (star 6865) | License: MIT | Collected: 2026-10-27
# Commit:  17e32227dfce
shader_type canvas_item;

uniform vec4 background_color;

void fragment() {
	vec3 inverted = vec3(1.0) - background_color.rgb;
	float grayscale = (inverted.r + inverted.g + inverted.b) / 3.0;
	grayscale = min(1.0, grayscale*1.25);

	COLOR = vec4(grayscale, grayscale, grayscale, COLOR.a);
}