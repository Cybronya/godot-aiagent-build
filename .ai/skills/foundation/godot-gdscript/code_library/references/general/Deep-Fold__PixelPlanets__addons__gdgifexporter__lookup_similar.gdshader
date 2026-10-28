# Source:  https://github.com/Deep-Fold/PixelPlanets/blob/main/addons/gdgifexporter/lookup_similar.gdshader
# Repo:    Deep-Fold/PixelPlanets (star 1403) | License: MIT | Collected: 2026-10-28
# Commit:  main
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D lut;

void fragment() {
	vec4 color = texture(TEXTURE, UV);
	vec4 similar = texture(lut, vec2(0.5 / 256.0, 0.5));
	float index = 0.0;
	if (color.a > 0.0) {
		float dist = distance(color.xyz, similar.xyz);
		for (int i = 1; i < 256; i++) {
			vec4 c = texture(lut, vec2((float(i) + 0.5) / 256.0, 0.5));
			float d = distance(color.xyz, c.xyz);
			if (d < dist) {
				dist = d;
				index = float(i) / 255.0;
			}
		}
	}
	COLOR = vec4(vec3(index), 1.0);
}