extends Node2D
## Survival Arena 场景适配层（Phase 1.14）：敌人生成 / 生存计时 / 胜负交由通用编排管线。
##
## 通用编排部分（与 TimedCombatArena **同一套实现**）：
##   `Orchestration/level_orchestrator.gd` 的 holdout 模式 + `Levels/survival_arena.json`
##   （schema version 2）驱动：生成哪些敌人（entities）、按什么节奏持续生成
##   （holdout.spawns: interval / delay / max_alive + holdout.max_alive 总上限）、
##   生存时长（holdout.survival_duration）与胜利条件（victory = survive_duration）。
##   玩家死亡 → 失败、胜负事件只触发一次、重开轮询均由编排器统一处理。
##
## 场景专属部分（不纳入关卡编排配置，保持既有玩法原样）：
##   - 拾取物生成（pickup_scene / pickup_interval / max_pickups）：拾取物不是关卡编排的
##     「敌人」契约对象（无 target_path / Health 管理接口），继续由本场景管理；
##   - 陷阱与奖励机关（tscn [connection] 数据连接）；
##   - HUD 表现、结束时的伤害源递归冻结、R 重开（重开轮询在编排器）。
##
## 遗留导出（level_config_path 留空时按既有语义驱动；配置优先，绝不静默混用）：
##   survival_duration / spawn_interval / max_enemies / enemy_scene / elite_scene /
##   elite_spawn_delay / elite_spawn_interval / max_elites。
##
## 已知限制（不宣称为配置已支持）：holdout 模式无出口概念；波次顺序推进仅 waves 模式支持。

@export var level_config_path := "res://Levels/survival_arena.json"
@export var player_path := NodePath("Player")
# ---- 场景专属：拾取物（不属于关卡编排的敌人生成契约）----
@export var pickup_scene: PackedScene
@export var pickup_interval := 4.0
@export var max_pickups := 3
# ---- 遗留导出：level_config_path 留空时使用（配置驱动时以配置为准）----
@export var survival_duration := 30.0
@export var spawn_interval := 1.2
@export var max_enemies := 12
@export var enemy_scene: PackedScene
@export var elite_scene: PackedScene
@export var elite_spawn_delay := 10.0
@export var elite_spawn_interval := 8.0
@export var max_elites := 2

signal arena_finished(player_won: bool)

enum State { Playing, Won, Lost }

var _orchestrator: LevelOrchestrator
var _player: CharacterBody2D
var _entities: Node2D
var _health_label: Label
var _timer_label: Label
var _status_label: Label
var _pickup_timer := 0.0

## 只读属性转发到通用编排器（Won/Lost 与编排器 Completed/Failed 序号一致）
var state: int:
	get:
		return _orchestrator.state if _orchestrator != null else State.Playing
var alive_count: int:
	get:
		return _orchestrator.alive_count if _orchestrator != null else 0


## 配置校验错误（空 = 无错误）；供测试与诊断读取
func get_config_errors() -> PackedStringArray:
	return _orchestrator.get_config_errors() if _orchestrator != null else PackedStringArray()


## 结构化诊断（G13）：在编排器诊断上补本消费场景路径
## 诊断事件 trace 导出（Phase 1.22/1.24）：转发到内部编排器；与 LevelHost 的
## 诊断 API 对齐。编排器不存在（配置未应用）时返回 false，绝不影响游戏行为。
func export_trace_json(path: String) -> bool:
	return _orchestrator.export_trace_json(path) if _orchestrator != null else false


func get_diagnostics() -> Dictionary:
	var diagnostics: Dictionary = _orchestrator.get_diagnostics() if _orchestrator != null else {}
	diagnostics["consumer_scene"] = scene_file_path
	return diagnostics


func _ready() -> void:
	_player = get_node(player_path)
	_entities = $Entities
	_health_label = $HUD/HealthLabel
	_timer_label = $HUD/TimerLabel
	_status_label = $HUD/StatusLabel
	var player_health: Health = _player.get_node("Health")
	player_health.health_changed.connect(_on_player_health_changed)

	_orchestrator = LevelOrchestrator.new()
	add_child(_orchestrator)
	_orchestrator.player = _player
	_orchestrator.entities = _entities
	_orchestrator.spawn_offset = _enemy_spawn_offset
	_orchestrator.finished.connect(_on_orchestrator_finished)
	_orchestrator.tick.connect(_on_tick)

	var config: LevelConfig
	if not level_config_path.is_empty():
		config = LevelConfig.from_file(level_config_path)
	else:
		config = LevelConfig.make_holdout(survival_duration, max_enemies, _legacy_spawns())
	# 配置无效：拒绝开始（不生成敌人、不生成拾取物、不静默回退到遗留导出）
	if not _orchestrator.apply_config(config):
		_update_status_label()
		return
	_orchestrator.start()
	_spawn_pickup()
	_update_health_label()
	_update_status_label()
	_update_timer_label()


func _process(delta: float) -> void:
	if state != State.Playing:
		return
	_pickup_timer += delta
	if _pickup_timer >= pickup_interval:
		_pickup_timer = 0.0
		if _count_pickups() < max_pickups:
			_spawn_pickup()


## 显式生成一个敌人（测试与兼容入口）：默认取配置/遗留数据中的首个敌人生成场景
func _spawn_enemy(scene: PackedScene = null) -> void:
	if scene == null:
		scene = _orchestrator.get_default_enemy_scene() if _orchestrator != null else enemy_scene
	if scene == null:
		return
	_orchestrator.spawn_enemy(scene)


## 强制结束入口（测试与兼容用）：委托通用编排执行，保持「Won/Lost + 伤害源冻结 +
## arena_finished 恰好一次」的原有语义
func _finish(player_won: bool) -> void:
	if _orchestrator != null:
		_orchestrator.finish(player_won)


## 敌人生成坐标（相对于 Entities 容器）：环绕玩家的随机环，与迁移前一致
func _enemy_spawn_offset() -> Vector2:
	var angle := randf() * TAU
	return _player.global_position + Vector2.from_angle(angle) * randf_range(180.0, 260.0) \
		- _entities.global_position


## 遗留生成调度（level_config_path 留空时由导出参数构造，语义与迁移前一致）
func _legacy_spawns() -> Array:
	var spawns: Array = []
	if enemy_scene != null:
		spawns.append({"scene": enemy_scene, "interval": spawn_interval, "delay": 0.0, "max_alive": 0})
	if elite_scene != null:
		spawns.append({
			"scene": elite_scene,
			"interval": elite_spawn_interval,
			"delay": elite_spawn_delay,
			"max_alive": max_elites,
		})
	return spawns


# ---------- 场景专属：拾取物 ----------


func _spawn_pickup() -> void:
	var pickup: Area2D = pickup_scene.instantiate()
	pickup.position = _player.global_position + _spawn_offset()
	_entities.add_child(pickup)


func _spawn_offset() -> Vector2:
	var angle := randf() * TAU
	return Vector2.from_angle(angle) * randf_range(180.0, 260.0)


func _count_pickups() -> int:
	var count := 0
	for entity in _entities.get_children():
		if entity.is_in_group("pickups"):
			count += 1
	return count


# ---------- 编排器信号 → 场景表现 ----------


func _on_tick(elapsed: float, duration: float) -> void:
	_timer_label.text = "生存时间: %.1f / %.0f 秒" % [elapsed, duration]


func _on_orchestrator_finished(player_won: bool) -> void:
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


func _on_player_health_changed(_current: int, _amount: int) -> void:
	_update_health_label()


func _update_health_label() -> void:
	var player_health: Health = _player.get_node("Health")
	_health_label.text = "HP: %d / %d" % [player_health.get_current_health(), player_health.max_health]


func _update_timer_label() -> void:
	var duration := _orchestrator.current_duration() if _orchestrator != null else survival_duration
	_timer_label.text = "生存时间: %.1f / %.0f 秒" % [_orchestrator.get_elapsed() if _orchestrator != null else 0.0, duration]


func _update_status_label() -> void:
	var errors := _orchestrator.get_config_errors() if _orchestrator != null else PackedStringArray()
	if not errors.is_empty():
		_status_label.text = "关卡配置无效：%s" % errors[0]
		return
	match state:
		State.Playing:
			_status_label.text = ""
		State.Won:
			_status_label.text = "生存成功！按 R 重新开始"
		State.Lost:
			_status_label.text = "玩家死亡，按 R 重新开始"
