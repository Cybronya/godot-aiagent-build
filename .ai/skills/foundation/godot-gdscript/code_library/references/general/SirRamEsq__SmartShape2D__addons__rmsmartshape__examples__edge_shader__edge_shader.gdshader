# Source:  https://github.com/SirRamEsq/SmartShape2D/blob/master/addons/rmsmartshape/examples/edge_shader/edge_shader.gdshader
# Repo:    SirRamEsq/SmartShape2D (star 1761) | License: MIT | Collected: 2026-10-29
# Commit:  9617190250d0
shader_type canvas_item;
/**
 * This shader fixes normal textures looking wrong when used with SmartShape2D.
 * See: https://github.com/SirRamEsq/SmartShape2D/blob/master/addons/rmsmartshape/documentation/Normals.md
 */

varying mat2 NORMAL_MATRIX;

void vertex() {
	NORMAL_MATRIX = mat2(COLOR.rg, COLOR.ba) * 2.0 - mat2(vec2(1.0), vec2(1.0));
}

void fragment() {
	NORMAL.xy = NORMAL_MATRIX * NORMAL.xy;
	COLOR = texture(TEXTURE, UV);
}
