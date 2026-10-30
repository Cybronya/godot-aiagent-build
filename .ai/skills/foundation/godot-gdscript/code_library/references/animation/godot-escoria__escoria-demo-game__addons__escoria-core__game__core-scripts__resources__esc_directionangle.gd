# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/resources/esc_directionangle.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
@tool
## Class defining an angle, with a start angle (between 0 and 360) and a size.
class_name ESCDirectionAngle
extends Resource

## Start angle of the directional angle.
@export var angle_start: int

## Size of the angle.
@export var angle_size: int
