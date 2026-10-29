# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/noise_viewer/noise_viewer.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
shader_type canvas_item;

uniform float min_value = -1;
uniform float max_value = 1;

void fragment() {
	// Get the color.
	vec4 color = texture(TEXTURE, UV);

	// Compare the value.
	float gray = color.x;
	if (gray < min_value) {
		color = vec4(0, 0, 0, 1);
	} else if (gray > max_value) {
		color = vec4(1, 1, 1, 1);
	}

	// Write back the color.
	COLOR = color;
}
