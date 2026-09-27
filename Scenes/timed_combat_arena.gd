extends Node2D
## Timed Combat Arena 游戏侧编排：波次生成、存活计数、阶段倒计时、胜负与重开。
##
## 场景级组合胶水（遵循 AD-003，不 Feature 化）：只做波次/计数/计时编排，
## 移动/生命/追击/接触伤害/血条/出口门分别复用 Features/ 下已验证组件，
## 本脚本不实现任何这类行为。计时与波次的 Feature 提升条件（AD-003）：
## 出现第二个需要独立计时/波次编排的场景。
##
## 波次数据（waves，由场景配置）：每波一个 Dictionary：
##   enemy_scene: PackedScene   普通敌人场景
##   enemy_count: int           普通敌人生成数量
##   elite_scene: PackedScene   可选，精英敌人场景
##   elite_count: int           可选，精英敌人生成数量
##   duration: float            本阶段倒计时（秒）
## 不同波次可配置不同敌人组合，同一套生成/接线/计数/计时机制覆盖全部波次。

@export var waves: Array[Dictionary] = []
@export var player_path := NodePath("Player")
@export var exit_door_path := NodePath("Mechanism/ExitDoor")
@export var exit_zone_path := NodePath("Mechanism/ExitZone")

signal arena_finished(success: bool)

enum State { Playing, Completed, Failed }

var state := State.Playing
var wave_index := 0
var alive_count := 0
var _elapsed := 0.0

@onready var _player: CharacterBody2D = get_node(player_path)
@onready var _entities: Node2D = $Entities
@onready var _exit_door: StaticBody2D = get_node(exit_door_path)
@onready var _exit_zone: Area2D = get_node(exit_zone_path)
@onready var _wave_label: Label = $HUD/WaveLabel
@onready var _alive_label: Label = $HUD/AliveLabel
@onready var _timer_label: Label = $HUD/TimerLabel
@onready var _status_label: Label = $HUD/StatusLabel


func _ready() -> void:
	var player_health: Health = _player.get_node("Health")
	player_health.health_changed.connect(_on_player_health_changed)
	player_health.died.connect(_on_player_died)
	_exit_zone.body_entered.connect(_on_exit_zone_body_entered)
	_start_wave(0)
	_update_status_label()


func _process(delta: float) -> void:
	if state != State.Playing:
		if Input.is_action_just_pressed("restart"):
			get_tree().reload_current_scene()
		return
	_elapsed += delta
	_update_timer_label()
	# 倒计时耗尽且仍有敌人存活 → 超时失败；提前清场会在死亡回调中立即推进阶段，
	# 计时器随 _start_wave 重置，因此走到这里必然仍有敌人存活（需求 10/11）
	if _elapsed >= current_duration():
		_finish(false)


func current_duration() -> float:
	if wave_index < 0 or wave_index >= waves.size():
		return 0.0
	return float(waves[wave_index].get("duration", 30.0))


func _start_wave(index: int) -> void:
	wave_index = index
	_elapsed = 0.0
	_spawn_wave(waves[index])
	_update_wave_label()
	_update_timer_label()


func _spawn_wave(wave: Dictionary) -> void:
	var enemy_scene: PackedScene = wave.get("enemy_scene")
	var enemy_count: int = wave.get("enemy_count", 0)
	for _i: int in enemy_count:
		_spawn_enemy(enemy_scene)
	var elite_scene: PackedScene = wave.get("elite_scene")
	var elite_count: int = wave.get("elite_count", 0)
	for _i: int in elite_count:
		_spawn_enemy(elite_scene)


func _spawn_enemy(scene: PackedScene) -> void:
	var enemy: CharacterBody2D = scene.instantiate()
	enemy.position = _spawn_offset()
	enemy.target_path = NodePath("../../" + _player.name)
	enemy.add_to_group("enemies")
	var enemy_health: Health = enemy.get_node("Health")
	# 死亡接线：退出战斗（移除）与存活计数都复用 Health.died 信号，同一机制覆盖所有敌人配置
	enemy_health.died.connect(enemy.queue_free)
	enemy_health.died.connect(_on_enemy_died)
	_entities.add_child(enemy)
	alive_count += 1
	_update_alive_label()


func _spawn_offset() -> Vector2:
	var angle := randf() * TAU
	return Vector2.from_angle(angle) * randf_range(200.0, 280.0)


func _on_enemy_died() -> void:
	alive_count -= 1
	_update_alive_label()
	if alive_count <= 0:
		_advance_wave()


## 提前击败全部敌人立即进入下一阶段（需求 11）；最后一阶段清场后打开出口（需求 13）
func _advance_wave() -> void:
	var next := wave_index + 1
	if next >= waves.size():
		_exit_door.set_open(true)
		_update_status_label()
	else:
		_start_wave(next)


func _on_exit_zone_body_entered(body: Node2D) -> void:
	if state != State.Playing or not body.is_in_group("players"):
		return
	# 出口区位于出口门后，门未开时物理上不可达；此处再做门状态校验兜底
	if not _exit_door.is_open():
		return
	_finish(true)


func _on_player_died() -> void:
	_finish(false)


func _finish(success: bool) -> void:
	if state != State.Playing:
		return
	state = State.Completed if success else State.Failed
	_update_status_label()
	arena_finished.emit(success)


func _on_player_health_changed(_current: int, _amount: int) -> void:
	pass


func _update_wave_label() -> void:
	_wave_label.text = "阶段 %d / %d" % [wave_index + 1, waves.size()]


func _update_alive_label() -> void:
	_alive_label.text = "存活敌人: %d" % alive_count


func _update_timer_label() -> void:
	_timer_label.text = "倒计时: %.1f / %.0f 秒" % [_elapsed, current_duration()]


func _update_status_label() -> void:
	match state:
		State.Playing:
			_status_label.text = "在倒计时内击败全部敌人，坚持到最终阶段打开出口（空格攻击，R 重开）"
		State.Completed:
			_status_label.text = "挑战完成！按 R 重新开始"
		State.Failed:
			_status_label.text = "挑战失败，按 R 重新开始"
