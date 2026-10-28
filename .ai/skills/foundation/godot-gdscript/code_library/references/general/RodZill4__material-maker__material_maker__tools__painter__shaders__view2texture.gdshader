# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/tools/painter/shaders/view2texture.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
shader_type spatial;
render_mode unshaded;

uniform float near;
uniform float far;

void fragment() {
	float depth = (FRAGCOORD.z/FRAGCOORD.w-near)/(far-near);
	ALBEDO = vec3(UV.xy, depth);
}
