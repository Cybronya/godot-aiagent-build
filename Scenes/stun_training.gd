extends Node2D
## Stun Training 场景胶水：仅重开轮询（训练场无胜负流程状态）。
##
## 全部玩法行为（眩晕/追击/伤害/治疗/开门）由 Feature 组件与
## tscn [connection] 数据表达，本脚本不参与任何机制，只做场景生命周期操作。

func _process(_delta: float) -> void:
	if Input.is_action_just_pressed("restart"):
		get_tree().reload_current_scene()
