extends Node2D
## Three Altars Puzzle 场景胶水：完成判定呈现与重开轮询。
##
## 机关关系（祭坛→AtLeast 聚合→出口门）全部由 tscn [connection] 表达，
## 本脚本不参与；这里只做本场景专属的一次性逻辑：
## 完成区进入判定、胜利文案与重开，不可复用故不 Feature 化。

@export var complete_zone_path := NodePath("Mechanism/CompleteZone")

signal puzzle_completed

enum State { Playing, Completed }

var state := State.Playing

@onready var _zone: Area2D = get_node(complete_zone_path)
@onready var _status_label: Label = $HUD/StatusLabel


func _ready() -> void:
	_zone.body_entered.connect(_on_zone_body_entered)
	_update_status_label()


func _process(_delta: float) -> void:
	if state != State.Playing:
		if Input.is_action_just_pressed("restart"):
			get_tree().reload_current_scene()
		return


func _on_zone_body_entered(body: Node2D) -> void:
	if state != State.Playing or not body.is_in_group("players"):
		return
	state = State.Completed
	_update_status_label()
	puzzle_completed.emit()


func _update_status_label() -> void:
	match state:
		State.Playing:
			_status_label.text = "激活至少两个祭坛，打开出口逃脱（再触一次可取消；R 重开）"
		State.Completed:
			_status_label.text = "谜题完成！按 R 重新开始"
