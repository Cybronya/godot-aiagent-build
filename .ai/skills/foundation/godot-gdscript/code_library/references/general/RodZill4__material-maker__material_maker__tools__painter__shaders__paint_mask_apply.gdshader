# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/tools/painter/shaders/paint_mask_apply.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
shader_type canvas_item;
render_mode blend_disabled, unshaded;

uniform bool erase = false;
uniform sampler2D tex;
uniform sampler2D SCREEN_TEXTURE : hint_screen_texture, filter_linear_mipmap;

void fragment() {
	vec4 screen_color = texture(SCREEN_TEXTURE, UV);
	vec4 color = texture(tex, UV);
	float a = color.a*COLOR.a;
	COLOR = vec4((vec3(erase?0.0:1.0)*a+screen_color.xyz*(1.0-a)), 1.0);
}
