# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/platformer/player/bullet/bullet.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
class_name Bullet
extends RigidBody3D

## If `true`, the bullet can hit enemies. This is set to `false` when the bullet
## hits an enemy so it can't hit an enemy multiple times while the bullet is fading out.
var enabled: bool = true
