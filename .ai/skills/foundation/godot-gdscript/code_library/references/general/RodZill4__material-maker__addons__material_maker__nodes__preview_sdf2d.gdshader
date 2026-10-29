# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/nodes/preview_sdf2d.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
uniform float variation = 0.0;

vec4 preview_2d(vec2 uv) {
	float _seed_variation_ = variation;
	vec4 _controlled_variation_ = vec4(0.0);
	$(code)
	float d = $(value);
	vec3 col = vec3(clamp(6.0*cos(d*min((256), preview_size))-5.0, 0.0, 1.0));
	col *= clamp(1.0-d*d, 0.0, 1.0);
	col *= vec3(1.0, vec2(step(-0.015, d)));
	col *= vec3(vec2(step(d, 0.015)), 1.0);
	return vec4(col, 1.0);
}
