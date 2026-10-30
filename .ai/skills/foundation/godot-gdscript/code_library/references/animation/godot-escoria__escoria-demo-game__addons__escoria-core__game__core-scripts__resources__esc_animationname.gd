# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/resources/esc_animationname.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
@tool
## Class defining an animation to use for an angle.
class_name ESCAnimationName
extends Resource

## Name of the animation
@export var animation: String

## Animation mirror (false is no mirror, true is mirrored)
@export var mirrored: bool
