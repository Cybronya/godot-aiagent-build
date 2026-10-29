# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/utils/mcp_adoption_label.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
class_name McpAdoptionLabel
extends RefCounted

## Retired v4 lifecycle vocabulary kept only because this class_name and its
## constants were published. Runtime ownership now lives in the tagged episode.
const MANAGED := "managed"
const EXTERNAL := "external"
