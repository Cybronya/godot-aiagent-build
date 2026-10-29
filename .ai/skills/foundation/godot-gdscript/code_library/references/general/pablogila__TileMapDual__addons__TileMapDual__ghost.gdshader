# Source:  https://github.com/pablogila/TileMapDual/blob/main/addons/TileMapDual/ghost.gdshader
# Repo:    pablogila/TileMapDual (star 1292) | License: MIT | Collected: 2026-10-29
# Commit:  b4dc77500354
// A shader that sets all pixels to 0 alpha, making the object invisible.

shader_type canvas_item;
void fragment() {
    COLOR = vec4(0);
}