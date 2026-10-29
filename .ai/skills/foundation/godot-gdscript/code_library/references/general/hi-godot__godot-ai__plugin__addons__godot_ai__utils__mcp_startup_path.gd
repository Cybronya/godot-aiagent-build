# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/utils/mcp_startup_path.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
class_name McpStartupPath
extends RefCounted

## Retired v4 lifecycle vocabulary kept only because this class_name and its
## constants were published. Runtime startup state lives in one tagged episode.
const UNSET := ""
const GUARDED := "guarded"
const ADOPTED := "adopted"
const SPAWNED := "spawned"
const CRASHED := "crashed"
const RESERVED := "reserved"
const NO_COMMAND := "no_command"
const INCOMPATIBLE := "incompatible"
const FREE := "free"
