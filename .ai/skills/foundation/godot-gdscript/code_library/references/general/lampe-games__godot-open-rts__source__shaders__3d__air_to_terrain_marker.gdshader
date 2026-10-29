# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/shaders/3d/air_to_terrain_marker.gdshader
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
shader_type spatial;
render_mode unshaded;

uniform vec4 albedo : source_color;
uniform float invisible_height = 0.0;
uniform float visible_height = 1.0;

void fragment()
{
  ALBEDO = albedo.rgb;
  vec4 model_vertex = inverse(MODEL_MATRIX) * INV_VIEW_MATRIX * vec4(VERTEX, 1.0);
  ALPHA = smoothstep(invisible_height, visible_height, model_vertex.y);
}
