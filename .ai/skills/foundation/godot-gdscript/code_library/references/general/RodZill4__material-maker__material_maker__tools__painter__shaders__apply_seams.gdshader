# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/tools/painter/shaders/apply_seams.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
shader_type canvas_item;

uniform sampler2D tex : hint_default_white;
uniform sampler2D seams : hint_default_white;

void fragment() {
	COLOR = texture(tex, UV+(texture(seams, UV).xy-vec2(0.5))/64.0);
}
