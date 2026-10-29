# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/tools/painter/shaders/brush_common_decl.gdshader
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
shader_type canvas_item;

uniform bool      texture_space   = false;
uniform bool      texture_view    = false;
uniform vec2      rect_size;
uniform vec2      brush_pos       = vec2(0.5, 0.5);
uniform vec2      brush_ppos      = vec2(0.5, 0.5);
uniform float     brush_size      = 0.5;
uniform float     brush_hardness  = 0.5;
const float       brush_opacity   = 1.0;
uniform float     stroke_length   = 0.0;
uniform float     stroke_angle    = 0.0;
uniform float     stroke_seed     = 0.0;
uniform float     pattern_scale   = 10.0;
uniform float     pattern_angle   = 0.0;
uniform float     pattern_alpha   = 0.0;
uniform float     pressure        = 1.0;

uniform sampler2D view2tex_tex;
uniform vec3      mesh_aabb_position = vec3(-0.5);
uniform vec3      mesh_aabb_size = vec3(1.0);
uniform sampler2D mesh_inv_uv_tex;
uniform sampler2D mesh_normal_tex;
uniform sampler2D mask_tex;
uniform sampler2D layer_albedo_tex;
uniform sampler2D layer_mr_tex;
uniform sampler2D layer_emission_tex;
uniform sampler2D layer_depth_tex;
