# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/xr/openxr_passthrough/holepunch.gdshader
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, shadow_to_opacity, unshaded;

void fragment() {
    ALBEDO = vec3(0.0, 0.0, 0.0);
}
