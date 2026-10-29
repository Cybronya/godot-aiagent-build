# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/tools/painter/shaders/paint_apply_background.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
shader_type canvas_item;
render_mode blend_disabled, unshaded;

uniform sampler2D tex;

void fragment() {
	COLOR = texture(tex, UV);
}
