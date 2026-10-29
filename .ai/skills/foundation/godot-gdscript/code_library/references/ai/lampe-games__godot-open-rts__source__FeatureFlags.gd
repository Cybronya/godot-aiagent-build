# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/FeatureFlags.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Node

@export_group("Game")
@export var show_logos_on_startup = true
@export var save_user_files_in_tmp = false

@export_group("Match")
@export var allow_resources_deficit_spending = false
@export var handle_match_end = true
@export var show_minimap = true
@export var allow_navigation_rebaking = true

@export_group("Match/Debug")
@export var frame_incrementer = false
@export var god_mode = false
