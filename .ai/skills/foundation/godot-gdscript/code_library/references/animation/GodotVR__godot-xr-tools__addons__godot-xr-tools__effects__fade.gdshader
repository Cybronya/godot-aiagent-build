# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/addons/godot-xr-tools/effects/fade.gdshader
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
shader_type spatial;
render_mode depth_test_disabled, skip_vertex_transform, unshaded, cull_disabled;

uniform vec4 albedo : source_color;

void vertex() {
	POSITION = vec4(VERTEX.x, -VERTEX.y, 0.0, 1.0);
}

void fragment() {
	ALBEDO = albedo.rgb;
	ALPHA = albedo.a;
}
