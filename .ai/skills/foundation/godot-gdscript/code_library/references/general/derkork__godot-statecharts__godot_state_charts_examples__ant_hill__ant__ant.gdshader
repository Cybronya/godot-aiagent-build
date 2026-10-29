# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/ant_hill/ant/ant.gdshader
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
shader_type canvas_item;

void fragment() {
	COLOR = COLOR + vec4(.3,.3,.1,.0); 
}
