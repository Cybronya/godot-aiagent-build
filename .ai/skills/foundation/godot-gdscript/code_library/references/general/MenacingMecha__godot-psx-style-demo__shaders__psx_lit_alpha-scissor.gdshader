# Source:  https://github.com/MenacingMecha/godot-psx-style-demo/blob/master/shaders/psx_lit_alpha-scissor.gdshader
# Repo:    MenacingMecha/godot-psx-style-demo (star 741) | License: MIT | Collected: 2026-10-31
# Commit:  91bd24988f70
shader_type spatial;

#define LIT diffuse_lambert, vertex_lighting
#define CULL cull_disabled
#define DEPTH depth_prepass_alpha
#define BLEND blend_mix
#define ALPHA_SCISSOR

#include "psx_base.gdshaderinc"
