# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/labels_and_texts/curvature.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
shader_type spatial;

void vertex() {
	VERTEX.z -= 0.6 - cos(VERTEX.x) * 0.6;
	VERTEX.x *= 0.8 + cos(VERTEX.x) * 0.2;
}

void fragment() {
	ALBEDO = vec3(1.0, 0.6, 0.1);
}
