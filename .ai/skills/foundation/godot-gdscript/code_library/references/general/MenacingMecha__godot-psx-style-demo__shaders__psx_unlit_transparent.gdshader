# Source:  https://github.com/MenacingMecha/godot-psx-style-demo/blob/master/shaders/psx_unlit_transparent.gdshader
# Repo:    MenacingMecha/godot-psx-style-demo (star 741) | License: MIT | Collected: 2026-10-31
# Commit:  91bd24988f70
shader_type spatial;

#define LIT unshaded
#define CULL cull_back
#define DEPTH depth_draw_always
#define BLEND blend_mix
#define ALPHA_BLEND

#include "psx_base.gdshaderinc"
