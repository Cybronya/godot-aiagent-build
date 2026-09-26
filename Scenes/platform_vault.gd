extends Node2D
## Platform Vault 场景胶水：完成判定呈现与重开轮询。
##
## 机关关系（钥匙→条件聚合→门）全部由 tscn [connection] 表达，本脚本不参与；
## 这里只做本场景专属的一次性逻辑：完成区进入判定、胜利文案与重开，
## 不可复用故不 Feature 化。

@export var complete_zone_path := NodePath("Mechanism/CompleteZone")

signal vault_completed

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
	vault_completed.emit()


func _update_status_label() -> void:
	match state:
		State.Playing:
			_status_label.text = "乘平台渡过水道，拾取钥匙打开门，进入出口（R 重开）"
		State.Completed:
			_status_label.text = "关卡完成！按 R 重新开始"
