# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/layers/layer_tooltip_thumbnail.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
shader_type canvas_item;

uniform sampler2D tex;

void fragment() {
	vec4 color = texture(tex, UV);
	vec2 uv = floor(16.0 * UV);
	float checkerboard = 0.5+0.5*mod(uv.x + uv.y, 2.);
	COLOR = vec4(mix(vec3(checkerboard), color.rgb, color.a), 1.0);
}