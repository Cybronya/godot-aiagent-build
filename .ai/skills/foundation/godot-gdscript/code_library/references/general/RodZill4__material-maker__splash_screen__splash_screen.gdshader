# Source:  https://github.com/RodZill4/material-maker/blob/master/splash_screen/splash_screen.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
shader_type canvas_item;

void fragment() {
	COLOR=vec4(vec3(0.0), 0.75*UV.y);
}
