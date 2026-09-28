extends Node2D
## Harvest Grove 场景胶水：完成状态呈现与重开轮询。
##
## 机关关系（资源→条件聚合→宝箱）由 tscn [connection] 数据表达；
## 完成语义 = 收集完成（CollectGate.fulfilled）本身：曾评估在门口放
## trigger_switch 作完成区，但半径 40 的触发圈会被未开门前的阻挡玩家
## 距 12px 提前触发，语义不成立，故拒绝接入（本轮「允许不复用」实测点）。
## 本脚本只做完成文案与重开轮询，不可复用故不 Feature 化（AD-003）。

@onready var _status_label: Label = $HUD/StatusLabel

var _completed := false


func is_completed() -> bool:
	return _completed


func _ready() -> void:
	_update_status_label()


func _process(_delta: float) -> void:
	if Input.is_action_just_pressed("restart"):
		get_tree().reload_current_scene()


func _on_collect_gate_fulfilled(fulfilled: bool) -> void:
	if fulfilled and not _completed:
		_completed = true
		_update_status_label()


func _update_status_label() -> void:
	if _completed:
		_status_label.text = "采集完成！按 R 重新开始"
	else:
		_status_label.text = "采集区：收集静止晶体与移动浮台上的晶体，开启宝箱完成采集（R 重开）"
