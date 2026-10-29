# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/tools/painter/shaders/init.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
shader_type canvas_item;
render_mode blend_disabled, unshaded;

uniform vec4      col = vec4(1.0, 1.0, 1.0, 1.0);
uniform sampler2D tex : hint_default_white;

void fragment() {
	COLOR = col * texture(tex, UV);
}
