# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/sprites/shaders/negative.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
shader_type spatial;
render_mode depth_prepass_alpha, unshaded;

uniform sampler2D texture_albedo : filter_nearest;

void fragment() {
	vec4 albedo = texture(texture_albedo, UV);
	float alpha = albedo.a;

	vec4 albedo_negative = vec4(1.0) - albedo;

	ALBEDO = vec3(albedo_negative.rgb);
	ALPHA = alpha;
}
