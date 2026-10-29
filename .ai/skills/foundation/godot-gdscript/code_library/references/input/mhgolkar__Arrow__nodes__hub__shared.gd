# Source:  https://github.com/mhgolkar/Arrow/blob/main/nodes/hub/shared.gd
# Repo:    mhgolkar/Arrow (star 1363) | License: MIT | Collected: 2026-10-29
# Commit:  5c0291c72e0f
# Arrow
# Game Narrative Design Tool
# Mor. H. Golkar

# Hub Node Type Shared Class
# (shared functionalities and constants)
class_name HubSharedClass

# hubs are by definition, to merge multiple inputs,
# into one single output
# so there must be at least two incoming slots for any hub
const HUB_MINIMUM_ACCEPTABLE_IN_SLOTS = 2
# and there can be a limit for the sake of tidiness
const HUB_MAXIMUM_ACCEPTABLE_IN_SLOTS = 10

# Note: the one outgoing slot is always there in the `.tscn`
