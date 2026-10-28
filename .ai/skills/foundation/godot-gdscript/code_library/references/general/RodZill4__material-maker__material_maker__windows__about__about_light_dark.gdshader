# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/about/about_light_dark.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
shader_type canvas_item;

uniform sampler2D tex;
uniform float scale = 1.0;
uniform bool invert = false;

void fragment() {
	vec4 col = texture(tex, UV*scale);
	COLOR = invert ? col : vec4(1.0-col.rgb, col.a);
}
