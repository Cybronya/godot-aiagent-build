# Source:  https://github.com/mhgolkar/Arrow/blob/main/nodes/dialog/shared.gd
# Repo:    mhgolkar/Arrow (star 1363) | License: MIT | Collected: 2026-10-29
# Commit:  5c0291c72e0f
# Arrow
# Game Narrative Design Tool
# Mor. H. Golkar

# Dialog Node Shared Class
class_name DialogSharedClass

# IMPORTANT!
# Optional node properties (those with default values commonly used,)
# can be left from the saved project files, optimizing them for size.
# This is a tricky process and may depend on the version of Arrow, runtime and project file format.
# It's advised to be used on versions with universally trusted defaults (i.e. most of recent stable releases.)
const SAVE_UNOPTIMIZED = false

const DEFAULT_NODE_DATA = {
	"character": -1, # ~ anonymous or unset (hardcoded convention)
	"lines": ["Hey there!"],
	# -- optional(s) --
	# > Manual playability. Hint: To optimize, set it for majority.
	"playable": false, # (It's `false` for mostly NPC talk.)
}

const ANONYMOUS_CHARACTER = {
	"name": "Anonymous" ,
	"color": "ffffff", # white
}
