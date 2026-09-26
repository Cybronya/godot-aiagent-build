extends Node2D
## Survival Arena 游戏侧编排：敌人生成、生存计时、胜负状态与重开。
##
## 场景级组合胶水（遵循 AD-003，不 Feature 化）：只做生成与状态编排，
## 移动/生命值/伤害/恢复/血条显示分别复用 Features/ 下已验证组件，
## 本脚本不实现任何这类行为。

@export var survival_duration := 30.0
@export var spawn_interval := 1.2
@export var max_enemies := 12
@export var pickup_interval := 4.0
@export var max_pickups := 3
@export var enemy_scene: PackedScene
@export var pickup_scene: PackedScene
@export var elite_scene: PackedScene
@export var elite_spawn_delay := 10.0
@export var elite_spawn_interval := 8.0
@export var max_elites := 2
@export var player_path := NodePath("Player")

signal arena_finished(player_won: bool)

enum State { Playing, Won, Lost }

var state := State.Playing
var _elapsed := 0.0
var _spawn_timer := 0.0
var _pickup_timer := 0.0
var _elite_timer := 0.0

@onready var _player: CharacterBody2D = get_node(player_path)
@onready var _entities: Node2D = $Entities
@onready var _hud: CanvasLayer = $HUD
@onready var _health_label: Label = $HUD/HealthLabel
@onready var _timer_label: Label = $HUD/TimerLabel
@onready var _status_label: Label = $HUD/StatusLabel


func _ready() -> void:
	var player_health: Health = _player.get_node("Health")
	player_health.health_changed.connect(_on_player_health_changed)
	player_health.died.connect(_on_player_died)
	_spawn_pickup()
	_update_health_label()
	_update_status_label()
	_update_timer_label()


func _process(delta: float) -> void:
	if state != State.Playing:
		if Input.is_action_just_pressed("restart"):
			get_tree().reload_current_scene()
		return
	_elapsed += delta
	if _elapsed >= survival_duration:
		_finish(true)
		return
	_spawn_timer += delta
	if _spawn_timer >= spawn_interval and _count_enemies() < max_enemies:
		_spawn_timer = 0.0
		_spawn_enemy()
	_pickup_timer += delta
	if _pickup_timer >= pickup_interval:
		_pickup_timer = 0.0
		if _count_pickups() < max_pickups:
			_spawn_pickup()
	if elite_scene != null and _elapsed >= elite_spawn_delay:
		if _elite_timer <= 0.0 or _elite_timer >= elite_spawn_interval:
			if _count_elites() < max_elites:
				_spawn_enemy(elite_scene)
				_elite_timer = 0.001 if _elite_timer <= 0.0 else _elite_timer
			else:
				_elite_timer = elite_spawn_interval
			if _elite_timer > 0.0:
				_elite_timer += delta
	else:
		_elite_timer = 0.0
	_update_timer_label()


func _spawn_enemy(scene: PackedScene = null) -> void:
	if scene == null:
		scene = enemy_scene
	var enemy: CharacterBody2D = scene.instantiate()
	enemy.position = _player.global_position + _spawn_offset()
	enemy.target_path = NodePath("../../" + _player.name)
	_wire_enemy(enemy)
	_entities.add_child(enemy)


## 敌人生成共享接线：死亡判定复用 Health（died 信号），移除由编排层负责；
## 普通与精英敌人走同一接线，行为差异全部由场景实例的参数覆写表达。
func _wire_enemy(enemy: CharacterBody2D) -> void:
	enemy.add_to_group("enemies")
	var enemy_health: Health = enemy.get_node("Health")
	enemy_health.died.connect(enemy.queue_free)


func _spawn_pickup() -> void:
	var pickup: Area2D = pickup_scene.instantiate()
	pickup.position = _player.global_position + _spawn_offset()
	_entities.add_child(pickup)


func _spawn_offset() -> Vector2:
	var angle := randf() * TAU
	return Vector2.from_angle(angle) * randf_range(180.0, 260.0)


func _count_enemies() -> int:
	var count := 0
	for entity in _entities.get_children():
		if entity.is_in_group("enemies"):
			count += 1
	return count


func _count_elites() -> int:
	var count := 0
	for entity in _entities.get_children():
		if entity.name.begins_with("EliteEnemy"):
			count += 1
	return count


func _count_pickups() -> int:
	var count := 0
	for entity in _entities.get_children():
		if entity.is_in_group("pickups"):
			count += 1
	return count


func _finish(player_won: bool) -> void:
	state = State.Won if player_won else State.Lost
	# 伤害源统一停摆：敌人（根脚本驱动）与陷阱（ContactDamage 子组件驱动）
	# 都用递归冻结，确保子节点驱动的伤害源同样停止
	for enemy in get_tree().get_nodes_in_group("enemies"):
		_set_physics_enabled(enemy, false)
	for trap in get_tree().get_nodes_in_group("traps"):
		_set_physics_enabled(trap, false)
	_update_status_label()
	arena_finished.emit(player_won)


func _set_physics_enabled(node: Node, enabled: bool) -> void:
	node.set_physics_process(enabled)
	for child in node.get_children():
		_set_physics_enabled(child, enabled)


func _on_player_died() -> void:
	_finish(false)


func _on_player_health_changed(_current: int, _amount: int) -> void:
	_update_health_label()


func _update_health_label() -> void:
	var player_health: Health = _player.get_node("Health")
	_health_label.text = "HP: %d / %d" % [player_health.get_current_health(), player_health.max_health]


func _update_timer_label() -> void:
	_timer_label.text = "生存时间: %.1f / %.0f 秒" % [_elapsed, survival_duration]


func _update_status_label() -> void:
	match state:
		State.Playing:
			_status_label.text = ""
		State.Won:
			_status_label.text = "生存成功！按 R 重新开始"
		State.Lost:
			_status_label.text = "玩家死亡，按 R 重新开始"
