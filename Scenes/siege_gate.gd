extends Node2D
## Siege Gate 场景胶水：仅重开轮询。
##
## 四条机制线（伤害/眩晕/死亡/开门）汇聚于 Guard 实体，但全部状态由
## 各自 Feature 独立拥有（Health=HP/死亡、Stun=眩晕时长、OpenableDoor=门态），
## 关系由 tscn [connection] 与机关胶水 stun_tripwire 表达，本脚本不持有
## 任何玩法状态、不做任何冲突仲裁（Round 8 实验主体场景）。

func _process(_delta: float) -> void:
	if Input.is_action_just_pressed("restart"):
		get_tree().reload_current_scene()
