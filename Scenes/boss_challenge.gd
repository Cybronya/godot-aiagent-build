extends Node2D
## Boss Challenge 场景适配层（Phase 1.20）：Boss 生命周期已接入通用关卡编排。
##
## 编排职责（与 TimedCombatArena / SurvivalArena 同一套实现）：
##   `Orchestration/level_config.gd`（LevelConfig，boss 模式：boss.entity / boss.instance /
##   boss.spawn / exit / victory）+ `Orchestration/level_orchestrator.gd`
##   （Boss 死亡只结算一次、Boss 存活时不判胜、出口解锁、玩家死亡失败、R 重开）。
##   关卡数据 = `Levels/boss_challenge.json`；Boss 身份与实例路径都来自配置显式声明，
##   本脚本不再按节点名 / role 猜测 Boss，也不自己维护第二套胜负状态机。
##
## 场景专属（保留原样）：
##   - 三开关→条件聚合→Boss 门、Boss 死亡→出口门的机关关系由 tscn [connection] 数据表达；
##   - Boss 血量 HUD、状态文案、Boss 死亡后的表现（停摆整棵子树）。
##
## 配置无效 / Boss 实例无法解析：拒绝开始（零生成、零胜负事件），状态栏给出可定位字段。

## res://Levels/<id>.json（boss 模式配置；Boss 身份与实例路径由它声明）
@export var level_config_path := "res://Levels/boss_challenge.json"
## 配置未声明 boss.instance 时的场景默认引用（配置优先）
@export var boss_path := NodePath("Entities/Boss")
@export var boss_door_path := NodePath("Mechanism/BossDoor")
@export var exit_door_path := NodePath("Mechanism/ExitDoor")
@export var exit_zone_path := NodePath("Mechanism/ExitZone")

signal boss_challenge_finished(success: bool)

enum State { Playing, Completed, Failed }

var _orchestrator: LevelOrchestrator
var _config: LevelConfig
var _boss: CharacterBody2D

## 只读转发：保持既有测试/调用方的 challenge.state 语义（枚举序号与编排器一致）
var state: int:
	get:
		return _orchestrator.state if _orchestrator != null else State.Playing

@onready var _player: CharacterBody2D = $Player
@onready var _boss_door: StaticBody2D = get_node(boss_door_path)
@onready var _exit_door: StaticBody2D = get_node(exit_door_path)
@onready var _exit_zone: Area2D = get_node(exit_zone_path)
@onready var _boss_health_label: Label = $HUD/BossHealthLabel
@onready var _status_label: Label = $HUD/StatusLabel


func _ready() -> void:
	_config = LevelConfig.from_file(level_config_path)
	_orchestrator = LevelOrchestrator.new()
	_orchestrator.name = "LevelOrchestrator"
	add_child(_orchestrator)
	_orchestrator.player = _player
	_orchestrator.entities = $Entities
	_orchestrator.exit_door = _exit_door
	_orchestrator.exit_zone = _exit_zone
	_orchestrator.finished.connect(_on_orchestrator_finished)
	_orchestrator.boss_defeated.connect(_on_boss_defeated)
	_orchestrator.tick.connect(_on_tick)

	if not _orchestrator.apply_config(_config):
		_update_status_label()
		return

	_boss = _resolve_boss()
	if _boss == null:
		_orchestrator.fail_setup("boss.instance",
			"无法解析 Boss 实例（配置 %s / 场景默认 %s）"
			% [_config.boss_instance_path, str(boss_path)])
		_update_status_label()
		return
	if not _orchestrator.bind_boss(_config.boss_entity, _boss):
		_update_status_label()
		return

	var boss_health: Health = _boss.get_node("Health")
	boss_health.health_changed.connect(_on_boss_health_changed)
	_orchestrator.start()
	_update_boss_health_label()
	_update_status_label()


func _process(_delta: float) -> void:
	# 重开轮询与状态机由编排器统一处理；这里只刷新游玩中的进度文案
	if state == State.Playing:
		_update_status_label()


## 通用编排器（供测试与诊断确认 BossChallenge 确实走同一套实现）
func get_orchestrator() -> LevelOrchestrator:
	return _orchestrator


func get_config_errors() -> PackedStringArray:
	return _orchestrator.get_config_errors() if _orchestrator != null else PackedStringArray()


func get_diagnostics() -> Dictionary:
	var diagnostics := _orchestrator.get_diagnostics() if _orchestrator != null else {}
	diagnostics["consumer_scene"] = scene_file_path
	return diagnostics


func _resolve_boss() -> CharacterBody2D:
	if not _config.boss_instance_path.is_empty():
		return get_node_or_null(NodePath(_config.boss_instance_path)) as CharacterBody2D
	return get_node_or_null(boss_path) as CharacterBody2D


func _on_tick(_elapsed: float, _duration: float) -> void:
	_update_status_label()


func _on_boss_health_changed(_current: int, _amount: int) -> void:
	_update_boss_health_label()


## Boss 死亡表现由订阅方决定（AD-002）：停摆 Boss 整棵子树（追击 + 接触伤害节拍）。
## 胜负结算已经在编排器里完成（出口开门 / once-only victory），这里只做表现。
func _on_boss_defeated() -> void:
	if _boss != null and is_instance_valid(_boss):
		_boss.process_mode = Node.PROCESS_MODE_DISABLED
	_update_boss_health_label()
	_update_status_label()


func _on_orchestrator_finished(success: bool) -> void:
	_update_status_label()
	boss_challenge_finished.emit(success)


func _update_boss_health_label() -> void:
	if _boss == null or not is_instance_valid(_boss):
		_boss_health_label.text = "Boss 未就绪"
		return
	var boss_health: Health = _boss.get_node("Health")
	if boss_health.is_dead():
		_boss_health_label.text = "Boss 已被击败"
	else:
		_boss_health_label.text = "Boss HP: %d / %d" % [boss_health.get_current_health(),
			boss_health.max_health]


func _update_status_label() -> void:
	var errors := get_config_errors()
	if not errors.is_empty():
		_status_label.text = "关卡配置无效：%s" % errors[0]
		return
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
	if _boss == null or not is_instance_valid(_boss):
		return false
	var boss_health: Health = _boss.get_node("Health")
	return boss_health.is_dead()
