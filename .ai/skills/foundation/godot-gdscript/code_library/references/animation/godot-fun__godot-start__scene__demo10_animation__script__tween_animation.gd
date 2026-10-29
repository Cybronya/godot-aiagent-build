# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo10_animation/script/tween_animation.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends Sprite2D


var tween: Tween = null;
var targetPosition = null


func _ready():
	tween = create_tween()
	tween.set_loops()
	# 会在起始点和终点不断的插值计算
	tween.tween_property(self, "position", Vector2.RIGHT * 300, 1).as_relative().set_trans(Tween.TRANS_SINE)
