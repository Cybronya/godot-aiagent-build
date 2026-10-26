# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/shaders/color_flash.gdshader
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
shader_type canvas_item;

uniform vec3 overlay:source_color = vec3(1.0);
uniform float blend:hint_range(0.0, 1.0);

void fragment(){
	COLOR.rgb = mix(COLOR.rgb, overlay, blend);
}
