# Source:  https://github.com/bukkbeek/GodotPixelRenderer/blob/main/PixelRenderer/data/SpecularMaterial.gdshader
# Repo:    bukkbeek/GodotPixelRenderer (star 802) | License: MIT | Collected: 2026-10-31
# Commit:  078f2078fb9e
shader_type spatial;

void vertex() {
	// Called for every vertex the material is visible on.
}

void fragment() {
	ALBEDO = vec3(SPECULAR);
}

//void light() {
//	// Called for every pixel for every light affecting the material.
//	// Uncomment to replace the default light processing function with this one.
//}
