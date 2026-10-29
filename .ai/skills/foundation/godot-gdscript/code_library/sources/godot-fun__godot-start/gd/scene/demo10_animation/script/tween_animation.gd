extends Sprite2D


var tween: Tween = null;
var targetPosition = null


func _ready():
	tween = create_tween()
	tween.set_loops()
	# 会在起始点和终点不断的插值计算
	tween.tween_property(self, "position", Vector2.RIGHT * 300, 1).as_relative().set_trans(Tween.TRANS_SINE)
