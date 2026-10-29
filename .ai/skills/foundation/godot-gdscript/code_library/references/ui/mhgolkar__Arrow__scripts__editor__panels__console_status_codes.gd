# Source:  https://github.com/mhgolkar/Arrow/blob/main/scripts/editor/panels/console_status_codes.gd
# Repo:    mhgolkar/Arrow (star 1363) | License: MIT | Collected: 2026-10-29
# Commit:  5c0291c72e0f
# Arrow
# Game Narrative Design Tool
# Mor. H. Golkar

# Console Status Codes
# (sent by nodes being played, interpreted by the console)
class_name CONSOLE_STATUS_CODE

# the outgoing played slot is connected to no other node
const END_EDGE = 0
const END_EDGE_MESSAGE = "CONSOLE_STATUS_END_EDGE_MESSAGE" # Translated ~ "◆ EOL: {name} ({uid})"

# no default action is taken by the node (e.g. due to being skipped)
const NO_DEFAULT = 1
const NO_DEFAULT_MESSAGE = "CONSOLE_STATUS_NO_DEFAULT_MESSAGE" # Translated ~ "⚠ No DEFAULT: {name} ({uid})"
