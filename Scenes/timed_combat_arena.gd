extends Node2D
## Timed Combat Arena 场景适配层（Phase 1.14）：场景专属节点引用与 HUD 表现。
##
## 编排机制已通用化：波次调度 / 敌人生成与登记 / 存活计数 / 出口解锁 / 胜利判定全部由
## `Orchestration/level_orchestrator.gd`（LevelOrchestrator）+ `Orchestration/level_config.gd`
## （LevelConfig）承担；本脚本只做三件事：
##   1. 解析本场景的节点引用（Player / Entities / Mechanism/ExitDoor / ExitZone / HUD）；
##   2. 把引用与生成坐标策略注入通用编排器，转发其信号到 HUD 与 arena_finished；
##   3. 保留 Phase 1.13 起对外的同一套公开 API（state / waves / wave_index / alive_count /
##      current_duration / get_config_errors / get_exit_unlock_when / get_victory_condition），
##      既有测试与 e2e 探针无需改动。
##
## 关卡编排数据（Phase 1.13 起）：level_config_path 非空时，「生成哪些实体/几波/波次顺序/
## 出口何时开/胜利条件」全部由 `.ai/context/level_schema.yaml` 描述的配置驱动
## （Levels/<level_id>.json）。配置无效时拒绝开始（state=Failed + 状态栏给出可定位的错误），
## 绝不静默回退到场景内数据。运行时状态只存在于编排器，不写回配置。
##
## 波次数据两种来源（同一套生成/接线/计数/计时机制覆盖全部波次）：
##   1. 配置驱动（推荐）：level_config_path -> waves[i] = {duration, entries:[{scene,count}]}；
##   2. 场景内手写（兼容）：waves[i] = {duration, enemy_scene, enemy_count, elite_scene, elite_count}。
## 不同波次可配置不同敌人组合。

@export var waves: Array[Dictionary] = []
## res://Levels/<id>.json；非空时按关卡编排配置驱动，留空时使用场景内手写 waves
@export var level_config_path := ""
@export var player_path := NodePath("Player")
@export var exit_door_path := NodePath("Mechanism/ExitDoor")
@export var exit_zone_path := NodePath("Mechanism/ExitZone")

signal arena_finished(success: bool)

enum State { Playing, Completed, Failed }

var _orchestrator: LevelOrchestrator
var _player: CharacterBody2D
var _entities: Node2D
var _exit_door: StaticBody2D
var _exit_zone: Area2D
var _wave_label: Label
var _alive_label: Label
var _timer_label: Label
var _status_label: Label

## 以下只读属性转发到通用编排器（保持 Phase 1.13 公开 API；写入只在进入树前通过 waves）
var state: int:
	get:
		return _orchestrator.state if _orchestrator != null else State.Playing
var wave_index: int:
	get:
		return _orchestrator.wave_index if _orchestrator != null else 0
var alive_count: int:
	get:
		return _orchestrator.alive_count if _orchestrator != null else 0


func _ready() -> void:
	_player = get_node(player_path)
	_entities = $Entities
	_exit_door = get_node(exit_door_path)
	_exit_zone = get_node(exit_zone_path)
	_wave_label = $HUD/WaveLabel
	_alive_label = $HUD/AliveLabel
	_timer_label = $HUD/TimerLabel
	_status_label = $HUD/StatusLabel

	_orchestrator = LevelOrchestrator.new()
	add_child(_orchestrator)
	_orchestrator.player = _player
	_orchestrator.entities = _entities
	_orchestrator.exit_door = _exit_door
	_orchestrator.exit_zone = _exit_zone
	_orchestrator.spawn_offset = _enemy_spawn_offset
	_orchestrator.finished.connect(_on_orchestrator_finished)
	_orchestrator.wave_started.connect(_on_wave_started)
	_orchestrator.alive_changed.connect(_on_alive_changed)
	_orchestrator.tick.connect(_on_tick)
	_orchestrator.exit_unlocked.connect(_on_exit_unlocked)

	var config: LevelConfig
	if not level_config_path.is_empty():
		config = LevelConfig.from_file(level_config_path)
	else:
		config = LevelConfig.make_waves(waves)
	# 配置无效：拒绝开始（不生成任何敌人、不静默回退到场景内手写数据）
	if not _orchestrator.apply_config(config):
		waves = _orchestrator.waves
		_update_status_label()
		return
	# 与编排器共享同一 waves 数组引用：进入树后对 duration 的修改仍然生效
	waves = _orchestrator.waves
	_orchestrator.start()
	_update_status_label()


func current_duration() -> float:
	return _orchestrator.current_duration() if _orchestrator != null else 0.0


## 配置校验错误（空 = 无错误）；供测试与诊断读取
func get_config_errors() -> PackedStringArray:
	return _orchestrator.get_config_errors() if _orchestrator != null else PackedStringArray()


func get_exit_unlock_when() -> String:
	return _orchestrator.get_exit_unlock_when() if _orchestrator != null else ""


func get_victory_condition() -> String:
	return _orchestrator.get_victory_condition() if _orchestrator != null else ""


## 结构化诊断（G13）：在编排器诊断上补本消费场景路径，使失败可定位到
## 「关卡配置 + 错误字段 + 相关场景引用 + 失败编排阶段」。
## 诊断事件 trace 导出（Phase 1.22/1.24）：转发到内部编排器；与 LevelHost 的
## 诊断 API 对齐。编排器不存在（配置未应用）时返回 false，绝不影响游戏行为。
func export_trace_json(path: String) -> bool:
	return _orchestrator.export_trace_json(path) if _orchestrator != null else false


func get_diagnostics() -> Dictionary:
	var diagnostics: Dictionary = _orchestrator.get_diagnostics() if _orchestrator != null else {}
	diagnostics["consumer_scene"] = scene_file_path
	return diagnostics


## 敌人生成坐标（相对于 Entities 容器）：环绕竞技场原点的随机环，与 Phase 1.13 一致
func _enemy_spawn_offset() -> Vector2:
	var angle := randf() * TAU
	return Vector2.from_angle(angle) * randf_range(200.0, 280.0)


# ---------- 编排器信号 → HUD / 对外信号 ----------


func _on_wave_started(index: int, total: int) -> void:
	_wave_label.text = "阶段 %d / %d" % [index + 1, total]


func _on_alive_changed(count: int) -> void:
	_alive_label.text = "存活敌人: %d" % count


func _on_tick(elapsed: float, duration: float) -> void:
	_timer_label.text = "倒计时: %.1f / %.0f 秒" % [elapsed, duration]


func _on_exit_unlocked() -> void:
	_update_status_label()


func _on_orchestrator_finished(success: bool) -> void:
	_update_status_label()
	arena_finished.emit(success)


func _update_status_label() -> void:
	if not get_config_errors().is_empty():
		_status_label.text = "关卡配置无效：%s" % get_config_errors()[0]
		return
	match state:
		State.Playing:
			_status_label.text = "在倒计时内击败全部敌人，坚持到最终阶段打开出口（空格攻击，R 重开）"
		State.Completed:
			_status_label.text = "挑战完成！按 R 重新开始"
		State.Failed:
			_status_label.text = "挑战失败，按 R 重新开始"
