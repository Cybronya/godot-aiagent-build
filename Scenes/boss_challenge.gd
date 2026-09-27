extends Node2D
## Boss Challenge 场景胶水：完成判定呈现、Boss 血量 HUD 与重开轮询。
##
## 机关关系（三开关→条件聚合→Boss 门、Boss 死亡→出口门）全部由
## tscn [connection] 数据表达，本脚本不参与；这里只做本场景专属的
## 一次性逻辑：出口进入判定、状态文案与重开，不可复用故不 Feature 化。
## 移动/生命/追击/接触伤害/治疗/血条全部复用 Features/ 下已验证组件。

@export var boss_path := NodePath("Entities/Boss")
@export var boss_door_path := NodePath("Mechanism/BossDoor")
@export var exit_door_path := NodePath("Mechanism/ExitDoor")
@export var exit_zone_path := NodePath("Mechanism/ExitZone")

signal boss_challenge_finished(success: bool)

enum State { Playing, Completed, Failed }

var state := State.Playing

@onready var _player: CharacterBody2D = $Player
@onready var _boss: CharacterBody2D = get_node(boss_path)
@onready var _boss_door: StaticBody2D = get_node(boss_door_path)
@onready var _exit_door: StaticBody2D = get_node(exit_door_path)
@onready var _exit_zone: Area2D = get_node(exit_zone_path)
@onready var _boss_health_label: Label = $HUD/BossHealthLabel
@onready var _status_label: Label = $HUD/StatusLabel


func _ready() -> void:
	var player_health: Health = _player.get_node("Health")
	player_health.died.connect(_on_player_died)
	var boss_health: Health = _boss.get_node("Health")
	boss_health.health_changed.connect(_on_boss_health_changed)
	boss_health.died.connect(_on_boss_died)
	_exit_zone.body_entered.connect(_on_exit_zone_body_entered)
	_update_boss_health_label()
	_update_status_label()


func _process(_delta: float) -> void:
	match state:
		State.Playing:
			# 门前段进度（开关/门/Boss 状态）由数据连接驱动，文案按当前状态轮询刷新
			_update_status_label()
		_:
			if Input.is_action_just_pressed("restart"):
				get_tree().reload_current_scene()


func _on_boss_health_changed(_current: int, _amount: int) -> void:
	_update_boss_health_label()


func _on_boss_died() -> void:
	# 死亡表现由订阅方决定（AD-002）：停摆 Boss 整棵子树（追击 + 接触伤害节拍）
	_boss.process_mode = Node.PROCESS_MODE_DISABLED
	_update_boss_health_label()
	_update_status_label()


func _on_player_died() -> void:
	_finish(false)


func _on_exit_zone_body_entered(body: Node2D) -> void:
	if state != State.Playing or not body.is_in_group("players"):
		return
	# 出口区位于出口门后，门未开时物理上不可达；此处再做门状态校验兜底
	if not _exit_door.is_open():
		return
	_finish(true)


func _finish(success: bool) -> void:
	if state != State.Playing:
		return
	state = State.Completed if success else State.Failed
	_update_status_label()
	boss_challenge_finished.emit(success)


func _update_boss_health_label() -> void:
	var boss_health: Health = _boss.get_node("Health")
	if boss_health.is_dead():
		_boss_health_label.text = "Boss 已被击败"
	else:
		_boss_health_label.text = "Boss HP: %d / %d" % [boss_health.get_current_health(), boss_health.max_health]


func _update_status_label() -> void:
	match state:
		State.Playing:
			_status_label.text = _playing_status_text()
		State.Completed:
			_status_label.text = "挑战完成！按 R 重新开始"
		State.Failed:
			_status_label.text = "挑战失败，按 R 重新开始"


func _playing_status_text() -> String:
	if _boss_health_is_dead():
		return "Boss 已被击败！出口已打开，进入出口完成挑战"
	if _boss_door.is_open():
		return "三个开关已触发！Boss 门已打开，小心 Boss（空格攻击）"
	return "触发三个开关打开 Boss 门，击败 Boss 后从出口逃脱（空格攻击，R 重开）"


func _boss_health_is_dead() -> bool:
	var boss_health: Health = _boss.get_node("Health")
	return boss_health.is_dead()
