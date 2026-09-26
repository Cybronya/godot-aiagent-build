extends Node2D
## Escape Room 场景胶水：成功反馈呈现与重开轮询。
##
## 机关关系（开关→条件聚合→出口门）全部由 tscn [connection] 表达，本脚本不参与；
## 这里只做 Escape Room 专属的一次性逻辑：胜利文案与重开，不可复用故不 Feature 化。

@export var exit_path := NodePath("Mechanism/ExitDoor")

signal escape_finished(success: bool)

enum State { Playing, Escaped }

var state := State.Playing
var _won := false

@onready var _exit_door: StaticBody2D = get_node(exit_path)
@onready var _status_label: Label = $HUD/StatusLabel


func _ready() -> void:
	var gate: Node = get_node("Mechanism/ConditionGate")
	gate.fulfilled.connect(_on_gate_fulfilled)
	_update_status_label()


func _process(_delta: float) -> void:
	if state != State.Playing:
		if Input.is_action_just_pressed("restart"):
			get_tree().reload_current_scene()
		return


func _on_gate_fulfilled(fulfilled: bool) -> void:
	if not fulfilled or _won:
		return
	_won = true
	state = State.Escaped
	_update_status_label()
	escape_finished.emit(true)


func _update_status_label() -> void:
	match state:
		State.Playing:
			_status_label.text = "找到并触发两个机关，打开出口逃脱（R 重开）"
		State.Escaped:
			_status_label.text = "逃脱成功！按 R 重新开始"
