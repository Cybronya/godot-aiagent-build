# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/nodes/preview_f.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
uniform float variation = 0.0;

vec4 preview_2d(vec2 uv) {
	float _seed_variation_ = variation;
	vec4 _controlled_variation_ = vec4(0.0);
	$(code)
	return vec4(vec3($(value)), 1.0);
}
