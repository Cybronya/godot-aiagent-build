class_name LevelOrchestrator
extends Node
## 通用关卡编排运行时（Phase 1.14）：波次 / 生成 / 计数 / 出口 / 胜利的场景无关实现。
##
## 设计边界（对应任务书 3.1 的职责切分）：
##   - 关卡配置解析与校验：`LevelConfig`（本类只消费其产出，不重复规则）。
##   - 关卡运行时状态：state / wave_index / alive_count / _elapsed（只存本节点，不写回配置）。
##   - 敌人实例化与注册：`_spawn()`（实例化 → target_path 接线 → enemies 组 → Health.died
##     订阅 → 登记计数；按实例幂等，重复 died 不重复计数）。
##   - 顺序波次调度：waves 模式（清一波起一波；倒计时耗尽仍有存活 → 失败）。
##   - 持续生成调度：holdout 模式（spawns 调度表：delay 后按 interval 生成，受
##     max_alive 上限约束；生存到 survival_duration → 胜利）。
##   - Boss 战斗（Phase 1.20）：boss 模式只认配置声明的单一 Boss 实体（boss.entity）；
##     实例来源由适配层显式注入（bind_boss：already-existing instance）或由编排器
##     从配置场景生成（boss.spawn = on_start）。Boss 死亡是唯一完成信号，
##     boss 存活时出口胜利路径被拒绝（不按 role / 节点名推断 Boss）。
##   - 多阶段 Boss（Phase 1.21）：配置提供 stages 时按数组顺序推进；clear_enemies
##     复用 _spawn / alive_count，defeat_boss 复用 Boss 死亡事件，complete_level 显式终结。
##     阶段开始/完成、Boss 死亡、关卡完成各只结算一次（幂等）；提前死亡不跳阶段。
##   - 诊断事件（Phase 1.22）：真实状态变更边界写入 `OrchestrationTrace`（版本化、
##     严格递增序号、相对毫秒时间戳）；只观测不驱动，`trace_enabled = false` 时零开销。
##   - 出口解锁与胜利判定：按 exit.unlock_when / victory.condition 配置执行。
##   - 场景专属节点引用与表现：**一律由消费场景注入**（player / entities / exit_door /
##     exit_zone / spawn_offset / HUD 信号），本类不写任何 NodePath，不 import 场景名。
##
## 复用证据（G1/G3）：同一实现同时驱动 `Scenes/timed_combat_arena.gd`（waves）与
## `Scenes/survival_arena.gd`（holdout），也可被任意其他宿主场景直接使用。
##
## 用法（场景适配层）：
##   var orch := LevelOrchestrator.new(); add_child(orch)
##   orch.player = ...; orch.entities = ...; orch.exit_door = ...; orch.exit_zone = ...
##   orch.spawn_offset = func() -> Vector2: ...      # 相对于 entities 容器的生成坐标
##   if orch.apply_config(LevelConfig.from_file(path)):
##       if config.mode == "boss" and config.boss_spawn == "existing":
##           orch.bind_boss(config.boss_entity, existing_node)   # 显式实例，必须来自配置路径
##       orch.start()

signal finished(success: bool)
signal wave_started(index: int, total: int)
signal alive_changed(count: int)
signal tick(elapsed: float, duration: float)
signal exit_unlocked()
signal enemy_spawned(enemy: Node)
## Boss 战斗完成信号（只发一次；与 finished 的区别：victory 可能要求走进出口）
signal boss_defeated()
## 多阶段 Boss 阶段事件（Phase 1.21）：阶段进入 / 完成各只发一次；E2E 与诊断消费。
signal stage_started(index: int, stage_id: String, stage_type: String)
signal stage_completed(index: int, stage_id: String, stage_type: String)
signal stages_completed()

enum State { Playing, Completed, Failed }

## 每个实体实例的「已结算」标记：重复 died 通知不得重复计数或重复推进波次
const DEFEAT_MARKER := "arena_defeat_counted"
## Boss 死亡只结算一次（重复 died 通知不得重复开门 / 重复胜利）
const BOSS_DEFEAT_MARKER := "boss_defeat_counted"
## 标记实例来自哪条 holdout 生成调度（用于按调度统计存活上限）
const SCHEDULE_MARKER := "arena_spawn_schedule"
## 实例的配置实体身份（仅由诊断事件携带；不参与任何判定）
const ENTITY_MARKER := "arena_entity_id"
## 诊断记录器脚本：用 preload 而非全局 class_name，避免 headless 运行依赖编辑器类缓存
const OrchestrationTraceScript := preload("res://Orchestration/orchestration_trace.gd")

# ---- 场景注入（消费场景负责解析与提供；本类不依赖任何专属节点路径）----
var player: Node
var entities: Node
## waves 模式出口门：需提供 is_open() / set_open(bool)（OpenableDoor 即满足；可留空）
var exit_door: Node
## waves 模式出口区：玩家组实体进入且门已开 → 胜利（可留空）
var exit_zone: Area2D
## 生成坐标回调：返回相对于 entities 容器的局部坐标（Callable 无效时生成于原点）
var spawn_offset: Callable
var restart_action := "restart"

# ---- 运行时状态 ----
var state := State.Playing
var waves: Array[Dictionary] = []
var wave_index := 0
var alive_count := 0

var _mode := LevelConfig.MODE_WAVES
var _config_path := ""
var _config_errors: PackedStringArray = []
var _failure_stage := "none"
var _exit_unlock_when := LevelConfig.EXIT_ALL_WAVES_CLEARED
var _victory_condition := LevelConfig.VICTORY_EXIT_REACHED
var _survival_duration := 0.0
var _max_alive_total := 0
var _spawn_schedules: Array[Dictionary] = []
var _next_spawn_at: Array[float] = []
var _schedule_alive: Array[int] = []
var _elapsed := 0.0
# ---- boss 模式 ----
var _boss_entity := ""
var _boss_spawn := ""
var _boss_scene: PackedScene
var _boss_instance_path := ""
var _boss: Node
var _boss_is_defeated := false
var _boss_defeated_events := 0
# ---- 多阶段 Boss（Phase 1.21）----
## 配置声明的阶段（空 = 单阶段 boss，Phase 1.20 兼容）
var _stages: Array[Dictionary] = []
var _stage_index := -1
var _stage_id := ""
var _stage_type := ""
## 所有阶段完成（单阶段 boss / waves / holdout 恒为 true；出口守卫据此拒绝提前胜利）
var _stages_done := true
var _stage_started_events := 0
var _stage_completed_events := 0
var _stage_history: Array[String] = []
## start() 之前不推进任何编排 / 超时逻辑（适配层可以先入树再注入配置）
var _started := false
# ---- 诊断事件（Phase 1.22）----
## 结构化事件记录器（只读观测；真实状态机仍是唯一权威）
var trace = OrchestrationTraceScript.new()
## Phase 1.25：已写入 wave_cleared 事件的波次索引（幂等守卫——同一波次清空
## 转换只记录一次事件；由真实转换边界写入，不是测试补写）。
var _traced_cleared_wave := -1
## 关闭后不产生任何事件，游戏行为与阶段推进完全不变
var trace_enabled := true
## 终结原因稳定代码：由真实触发点设置，供 level_victory / level_failed 事件与诊断读取
var _victory_reason := "unspecified"
var _failure_reason := "unspecified"
## 最近一次进入活动状态的阶段（终结 / 重复 / 非法事件携带该上下文；-1 = 尚无阶段）
var _last_active_stage_id := ""
var _last_active_stage_index := -1


## 应用关卡配置（或适配层构造的内存配置）。无效配置 → state=Failed + 可定位诊断，
## 绝不静默回退到场景内数据（返回 false；调用方不得 start）。
func apply_config(config: LevelConfig) -> bool:
	_started = false
	_config_errors = config.errors
	_failure_stage = config.stage
	_config_path = config.source_path
	if not config.errors.is_empty():
		state = State.Failed
		return false
	_mode = config.mode
	waves = config.waves
	_exit_unlock_when = config.exit_unlock_when
	_victory_condition = config.victory_condition
	_survival_duration = config.survival_duration
	_max_alive_total = config.max_alive_total
	_spawn_schedules = config.spawn_schedules
	_boss_entity = config.boss_entity
	_boss_spawn = config.boss_spawn
	_boss_scene = config.boss_scene
	_boss_instance_path = config.boss_instance_path
	_boss = null
	_boss_is_defeated = false
	_boss_defeated_events = 0
	_stages = config.stages.duplicate(true)
	_stage_index = -1
	_stage_id = ""
	_stage_type = ""
	_stages_done = _stages.is_empty()
	_stage_started_events = 0
	_stage_completed_events = 0
	_stage_history.clear()
	_last_active_stage_id = ""
	_last_active_stage_index = -1
	_victory_reason = "unspecified"
	_failure_reason = "unspecified"
	trace = OrchestrationTraceScript.new()
	_traced_cleared_wave = -1
	_next_spawn_at.clear()
	_schedule_alive.clear()
	for schedule in _spawn_schedules:
		# 首次生成时间：delay > 0 时延迟到达即生成第一波、随后按 interval 续进
		#（精英语义，与迁移前 survival_arena.gd 一致）；delay = 0 时等一个 interval
		#（敌人生成语义：每 interval 一个，首个也在 interval 后）。
		var first_at := float(schedule.get("delay", 0.0))
		if first_at <= 0.0:
			first_at = float(schedule.get("interval", 1.0))
		_next_spawn_at.append(first_at)
		_schedule_alive.append(0)
	return true


## 开始编排：接线玩家死亡 / 出口区，并按模式启动第一波或生存计时。
func start() -> void:
	if state != State.Playing:
		return
	_started = true
	_wire_player()
	_wire_exit_zone()
	_start_trace()
	if _mode == LevelConfig.MODE_BOSS:
		if _stages.is_empty():
			_start_boss_phase()
		else:
			_start_stages()
		return
	if _mode == LevelConfig.MODE_WAVES:
		_start_wave(0)
	else:
		_elapsed = 0.0
		tick.emit(_elapsed, current_duration())


func _process(delta: float) -> void:
	if not _started:
		return
	if state != State.Playing:
		if Input.is_action_just_pressed(restart_action):
			get_tree().reload_current_scene()
		return
	_elapsed += delta
	tick.emit(_elapsed, current_duration())
	if _mode == LevelConfig.MODE_BOSS:
		# Boss 战没有倒计时；完成只由 Boss 死亡（或适配层显式结束）触发
		return
	if _mode == LevelConfig.MODE_WAVES:
		# 倒计时耗尽且仍有敌人存活 → 超时失败；提前清场会在死亡回调中立即推进阶段，
		# 计时器随 _start_wave 重置，因此走到这里必然仍有敌人存活
		if _elapsed >= current_duration():
			_failure_reason = "wave_timeout"
			_finish(false)
			return
		return
	if _elapsed >= _survival_duration:
		_victory_reason = "survive_duration"
		_finish(true)
		return
	_run_spawn_schedules()


func current_duration() -> float:
	if _mode == LevelConfig.MODE_HOLDOUT:
		return _survival_duration
	if _mode == LevelConfig.MODE_BOSS:
		return 0.0
	if wave_index < 0 or wave_index >= waves.size():
		return 0.0
	return float(waves[wave_index].get("duration", LevelConfig.DEFAULT_WAVE_DURATION))


## 配置校验错误（空 = 无错误）；供测试与诊断读取。消息格式：
## `<配置文件>: <JSON 字段路径>: <说明>`，可定位到关卡配置与错误字段。
func get_config_errors() -> PackedStringArray:
	return _config_errors


func get_exit_unlock_when() -> String:
	return _exit_unlock_when


func get_victory_condition() -> String:
	return _victory_condition


func get_mode() -> String:
	return _mode


## 当前 Boss 实例（boss 模式；未绑定/未生成时为 null）
func get_boss() -> Node:
	return _boss


func is_boss_defeated() -> bool:
	return _boss_is_defeated


## Boss 死亡结算次数（重复 died 通知不得增加；供测试与诊断读取）
func get_boss_defeated_events() -> int:
	return _boss_defeated_events


## 多阶段 Boss 诊断 / 测试入口（只读；阶段推进只由生产逻辑触发）。
func has_stages() -> bool:
	return not _stages.is_empty()


func are_stages_done() -> bool:
	return _stages_done


func get_stage_index() -> int:
	return _stage_index


func get_stage_id() -> String:
	return _stage_id


func get_stage_type() -> String:
	return _stage_type


func get_stages() -> Array[Dictionary]:
	return _stages


func get_stage_history() -> Array[String]:
	return _stage_history


func get_stage_event_counts() -> Dictionary:
	return {"started": _stage_started_events, "completed": _stage_completed_events}


## 结构化诊断事件（Phase 1.22）：完整 trace 文档（只读副本，可 JSON 序列化）。
func get_trace_report() -> Dictionary:
	return trace.to_dict() if trace != null else {}


func get_trace_events() -> Array:
	return trace.events.duplicate(true) if trace != null else []


func get_trace_summary() -> Dictionary:
	return trace.summary() if trace != null else {}


## 导出本次运行事件到显式路径；失败返回 false（绝不影响编排结果）。
func export_trace_json(path: String) -> bool:
	if trace == null:
		return false
	return trace.export_json(path)


func get_survival_duration() -> float:
	return _survival_duration


## 当前阶段累计时长（波次内 / 生存计时）；供测试与诊断读取
func get_elapsed() -> float:
	return _elapsed


## holdout 模式默认敌人生成场景（第一条调度）；waves 模式返回 null。
func get_default_enemy_scene() -> PackedScene:
	if _spawn_schedules.is_empty():
		return null
	return _spawn_schedules[0].get("scene")


## 结构化诊断（G13）：失败时可定位到关卡配置文件、失败阶段、错误字段与消费场景
## （消费场景由适配层补 consumer_scene 键）。
func get_diagnostics() -> Dictionary:
	return {
		"stage": _failure_stage,
		"phase": _current_phase(),
		"config_path": _config_path,
		"mode": _mode,
		"errors": _config_errors,
		"wave_index": wave_index,
		"alive_count": alive_count,
		"boss_entity": _boss_entity,
		"boss_instance": _boss_instance_path,
		"boss_defeated": _boss_is_defeated,
		"stage_index": _stage_index,
		"stage_id": _stage_id,
		"stage_type": _stage_type,
		"stages_done": _stages_done,
		"stage_started_events": _stage_started_events,
		"stage_completed_events": _stage_completed_events,
		"stage_history": _stage_history.duplicate(),
	}


func _current_phase() -> String:
	if not _config_errors.is_empty():
		return "config_rejected"
	match state:
		State.Playing:
			if _mode == LevelConfig.MODE_WAVES:
				return "wave_%d" % (wave_index + 1)
			if _mode == LevelConfig.MODE_BOSS:
				if not _stages.is_empty():
					if _stage_index < 0:
						return "stages_pending"
					return "stage_%d_%s" % [_stage_index, _stage_type]
				return "boss_defeated" if _boss_is_defeated else "boss"
			return "holdout"
		State.Completed:
			return "completed"
		State.Failed:
			return "failed"
	return "unknown"


## 公开生成入口：适配层 / 测试可显式生成一个敌人（不走调度上限，计入存活计数）。
func spawn_enemy(scene: PackedScene) -> Node:
	return _spawn(scene, -1)


## 显式绑定已存在的 Boss 实例（boss.spawn = existing）。
## 只接受配置声明的实体 id + 真实带 Health 的实例；不按节点名 / role 猜测。
## 失败时登记可定位诊断并进入 Failed（绝不静默继续）。
func bind_boss(entity_id: String, boss: Node) -> bool:
	if _mode != LevelConfig.MODE_BOSS:
		fail_setup("boss", "当前配置不是 boss 模式（%s），不接受 Boss 绑定" % _mode)
		return false
	if entity_id != _boss_entity:
		fail_setup("boss.entity", "绑定实体 %s 与配置声明的 %s 不一致"
			% [entity_id, _boss_entity])
		return false
	if boss == null or not is_instance_valid(boss):
		fail_setup("boss.instance", "配置声明了已存在的 Boss 实例 %s，但无法解析"
			% _boss_instance_path)
		return false
	var health := boss.get_node_or_null("Health") as Health
	if health == null:
		fail_setup("boss.entity", "Boss 实例 %s 缺少 Health 组件（无法与死亡事件对应）"
			% boss.name)
		return false
	_boss = boss
	if not health.died.is_connected(_on_boss_died):
		health.died.connect(_on_boss_died)
	return true


## 运行期接线失败（配置静态合法但宿主实例无法解析）：可定位诊断 + 拒绝开始。
## stage 用 bind 区分于 config_validate，便于诊断是「配置写错」还是「宿主不匹配」。
func fail_setup(field: String, message: String) -> void:
	var already_failed := state == State.Failed
	_config_errors.append("%s: %s" % [field, message])
	_failure_stage = "bind"
	state = State.Failed
	if already_failed:
		_trace_duplicate("already_finished")
		return
	_failure_reason = "setup_failed"
	_trace_event("level_failed", "orchestrator", "setup_failed",
		_last_active_stage_id if _last_active_stage_index >= 0 else null,
		_last_active_stage_index if _last_active_stage_index >= 0 else null,
		_boss_entity, "", {"field": field, "message": message})


# ---------- 接线 ----------


func _wire_player() -> void:
	if player == null:
		return
	var health := player.get_node_or_null("Health") as Health
	if health != null:
		health.died.connect(_on_player_died)


func _wire_exit_zone() -> void:
	if exit_zone != null:
		exit_zone.body_entered.connect(_on_exit_zone_body_entered)


# ---------- boss 模式：单一 Boss 生命周期 ----------


func _start_boss_phase() -> void:
	_elapsed = 0.0
	if _boss_spawn == LevelConfig.BOSS_SPAWN_ON_START:
		if _spawn_boss() == null:
			fail_setup("boss.entity", "Boss 场景无法实例化或缺少 Health（%s）" % _boss_entity)
			return
	elif _boss == null:
		# 不静默生成第二个 Boss：existing 必须由适配层显式绑定
		fail_setup("boss.instance", "配置要求已存在的 Boss 实例 %s，但适配层未绑定"
			% _boss_instance_path)
		return
	if _boss_health_is_dead():
		_mark_boss_defeated()
		_settle_single_boss()
	tick.emit(_elapsed, current_duration())


# ---------- 多阶段 Boss：显式阶段推进（Phase 1.21） ----------


## 启动阶段链：existing Boss 必须在 start 前完成显式绑定；on_start 延迟到 defeat_boss 阶段。
func _start_stages() -> void:
	_elapsed = 0.0
	_stages_done = false
	if _boss_spawn == LevelConfig.BOSS_SPAWN_EXISTING and _boss == null:
		fail_setup("boss.instance", "配置要求已存在的 Boss 实例 %s，但适配层未绑定"
			% _boss_instance_path)
		return
	_start_stage(0)


## 进入阶段：clear_enemies 生成条目；defeat_boss 绑定/生成 Boss；complete_level 立即终结。
## 所有阶段推进只由本函数与完成阶段条件驱动，测试探针不得直接改 _stage_index。
func _start_stage(index: int) -> void:
	if state != State.Playing:
		_trace_invalid("stage_start_while_not_playing")
		return
	if index < 0 or index >= _stages.size():
		_trace_invalid("stage_index_out_of_range")
		return
	_stage_index = index
	_stage_id = str(_stages[index].get("id", ""))
	_stage_type = str(_stages[index].get("type", ""))
	_last_active_stage_id = _stage_id
	_last_active_stage_index = index
	_stage_started_events += 1
	_trace_event("stage_started", "orchestrator", _stage_type, _stage_id, index, "", "",
		{"stage_type": _stage_type, "stage_count": _stages.size()})
	stage_started.emit(index, _stage_id, _stage_type)
	match _stage_type:
		LevelConfig.STAGE_CLEAR_ENEMIES:
			for entry in _stages[index].get("entries", []):
				var scene: PackedScene = entry.get("scene")
				if scene == null:
					fail_setup("stages[%d].entries" % index,
						"阶段 %s 的实体场景无法加载" % _stage_id)
					return
				for _i: int in int(entry.get("count", 0)):
					_spawn(scene, -1, str(entry.get("entity", "")))
			tick.emit(_elapsed, current_duration())
			# 空条目在配置校验中已被拒绝；这里兜底为立即完成（仍只推进一次）。
			if alive_count <= 0:
				_complete_stage()
		LevelConfig.STAGE_DEFEAT_BOSS:
			if _boss == null:
				if _boss_spawn == LevelConfig.BOSS_SPAWN_ON_START:
					if _spawn_boss() == null:
						fail_setup("boss.entity", "Boss 场景无法实例化或缺少 Health（%s）"
							% _boss_entity)
						return
				else:
					fail_setup("boss.instance", "配置要求已存在的 Boss 实例 %s，但适配层未绑定"
						% _boss_instance_path)
					return
			# 提前死亡（清理阶段击杀）也在此一次性结算；Boss 存活时不得完成该阶段。
			if _boss_is_defeated or _boss_health_is_dead():
				_mark_boss_defeated()
				_complete_stage()
		LevelConfig.STAGE_COMPLETE_LEVEL:
			_complete_stage()


## 完成当前阶段并只推进一次；最后一个阶段完成 → 按配置开门 / 完成关卡。
func _complete_stage() -> void:
	if state != State.Playing:
		_trace_duplicate("stage_completion")
		return
	if _stage_index < 0 or _stage_index >= _stages.size():
		_trace_invalid("stage_index_out_of_range")
		return
	var completed_index := _stage_index
	var completed_id := _stage_id
	var completed_type := _stage_type
	_stage_completed_events += 1
	_stage_history.append(completed_id)
	_trace_event("stage_completed", "orchestrator", completed_type, completed_id,
		completed_index, "", "", {"stage_type": completed_type})
	stage_completed.emit(completed_index, completed_id, completed_type)
	_stage_index = completed_index + 1
	_stage_id = ""
	_stage_type = ""
	var to_index = null
	var to_id = null
	if _stage_index < _stages.size():
		to_index = _stage_index
		to_id = str(_stages[_stage_index].get("id", ""))
	_trace_event("stage_transitioned", "orchestrator",
		"stage_completed" if to_index != null else "stages_exhausted",
		to_id, to_index, "", "",
		{"from_stage_id": completed_id, "from_stage_index": completed_index,
			"to_stage_id": to_id, "to_stage_index": to_index})
	if _stage_index < _stages.size():
		_start_stage(_stage_index)
		return
	_stages_done = true
	stages_completed.emit()
	# 终结条件：complete_level 阶段已由契约强制 victory=boss_defeated；
	# 末阶段为 defeat_boss 时沿用 boss 模式既有 exit / victory 规则。
	if _victory_condition == LevelConfig.VICTORY_BOSS_DEFEATED:
		_victory_reason = "boss_defeated"
		_finish(true)
		return
	if _exit_unlock_when == LevelConfig.EXIT_BOSS_DEFEATED and exit_door != null:
		exit_door.set_open(true)
		exit_unlocked.emit()


func _mark_boss_defeated() -> void:
	if _mode != LevelConfig.MODE_BOSS or _boss_is_defeated:
		return
	_boss_is_defeated = true
	_boss_defeated_events += 1
	var instance_name := ""
	if _boss != null and is_instance_valid(_boss):
		instance_name = str(_boss.name)
	_trace_event("boss_death_confirmed", "boss_lifecycle", "health_died",
		_stage_id if not _stage_id.is_empty() else null,
		_stage_index if _stage_index >= 0 else null,
		_boss_entity, instance_name, {"boss_defeated_events": _boss_defeated_events})
	boss_defeated.emit()


func _boss_health_is_dead() -> bool:
	if _boss == null or not is_instance_valid(_boss):
		return false
	var health := _boss.get_node_or_null("Health") as Health
	return health != null and health.is_dead()


## 单阶段 boss 的终结语义（Phase 1.20 保持不变）。
func _settle_single_boss() -> void:
	if _exit_unlock_when == LevelConfig.EXIT_BOSS_DEFEATED and exit_door != null:
		exit_door.set_open(true)
		exit_unlocked.emit()
	if _victory_condition == LevelConfig.VICTORY_BOSS_DEFEATED:
		_victory_reason = "boss_defeated"
		_finish(true)


func _spawn_boss() -> Node:
	if _boss_scene == null or entities == null:
		return null
	# Boss 实体根不限定类型：只要求带 Health（死亡事件来源）；有 Node2D / target_path
	# 才做坐标与追击目标接线，不通过类型强转把契约收窄到 CharacterBody2D。
	var boss: Node = _boss_scene.instantiate()
	if boss is Node2D:
		(boss as Node2D).position = spawn_offset.call() if spawn_offset.is_valid() else Vector2.ZERO
	entities.add_child(boss)
	if player != null and boss is Node2D and "target_path" in boss:
		boss.set("target_path", (boss as Node2D).get_path_to(player))
	if not bind_boss(_boss_entity, boss):
		boss.queue_free()
		return null
	return boss


## Boss 死亡：只结算一次；先完成出口解锁，再按配置判定胜利。
## 重复 died 通知 / 旧实例信号不会造成重复开门或重复完成。
func _on_boss_died() -> void:
	if _mode != LevelConfig.MODE_BOSS:
		_trace_invalid("not_boss_mode")
		return
	if _boss_is_defeated:
		_trace_duplicate("boss_death")
		return
	_mark_boss_defeated()
	if not _stages.is_empty():
		# 只有当前处于 defeat_boss 阶段才推进；清理阶段提前击杀只记录，不跳阶段。
		if _stage_type == LevelConfig.STAGE_DEFEAT_BOSS:
			_complete_stage()
		return
	_settle_single_boss()


# ---------- waves 模式：顺序波次 ----------


func _start_wave(index: int) -> void:
	wave_index = index
	_elapsed = 0.0
	_spawn_wave(waves[index])
	wave_started.emit(index, waves.size())
	# Phase 1.25：波次开始事件（语义契约见 orchestration_trace_schema.yaml）。
	# data 来自当前配置事实：波次索引 / 总波数 / 本波配置敌人数。
	var planned := 0
	for entry in waves[index].get("entries", []):
		planned += int(entry.get("count", 0))
	_trace_event("wave_started", "orchestrator", "wave_begin",
		null, null, "", "",
		{"wave": index, "total": waves.size(), "enemies": planned})
	tick.emit(_elapsed, current_duration())


func _spawn_wave(wave: Dictionary) -> void:
	for entry in wave.get("entries", []):
		var scene: PackedScene = entry.get("scene")
		if scene == null:
			continue
		for _i: int in int(entry.get("count", 0)):
			_spawn(scene, -1, str(entry.get("entity", "")))


## 提前击败全部敌人立即进入下一阶段；最后一波清空后按关卡配置决定出口是否开启、
## 是否直接胜利（victory = all_waves_cleared 时清场即胜、不需要走到出口）
func _advance_wave() -> void:
	# Phase 1.25：波次清空事件（幂等：同一波次只记录一次）。
	if _traced_cleared_wave != wave_index:
		_traced_cleared_wave = wave_index
		_trace_event("wave_cleared", "orchestrator", "wave_cleared",
			null, null, "", "", {"wave": wave_index})
	var next := wave_index + 1
	if next < waves.size():
		_start_wave(next)
		return
	if _victory_condition == LevelConfig.VICTORY_ALL_WAVES_CLEARED:
		_victory_reason = "all_waves_cleared"
		_finish(true)
		return
	if _exit_unlock_when == LevelConfig.EXIT_ALL_WAVES_CLEARED and exit_door != null:
		exit_door.set_open(true)
		exit_unlocked.emit()
		_trace_event("exit_unlocked", "orchestrator", "all_waves_cleared",
			null, null, "", "", {"wave": wave_index})


# ---------- holdout 模式：持续生成调度 ----------


func _run_spawn_schedules() -> void:
	for index in _spawn_schedules.size():
		var schedule: Dictionary = _spawn_schedules[index]
		if _elapsed < float(schedule.get("delay", 0.0)):
			continue
		if _elapsed < _next_spawn_at[index]:
			continue
		if not _can_spawn(index):
			# 达到上限：不推进下次生成时间，解除上限后立即补生成
			continue
		var enemy := _spawn(schedule["scene"], index, str(schedule.get("entity", "")))
		if enemy != null:
			_next_spawn_at[index] = _elapsed + float(schedule.get("interval", 1.0))


func _can_spawn(index: int) -> bool:
	var schedule: Dictionary = _spawn_schedules[index]
	var max_alive := int(schedule.get("max_alive", 0))
	if max_alive > 0 and _schedule_alive[index] >= max_alive:
		return false
	if _max_alive_total > 0 and alive_count >= _max_alive_total:
		return false
	return true


# ---------- 生成与登记（两种模式共用） ----------


func _spawn(scene: PackedScene, schedule_index: int, entity_id: String = "") -> Node:
	if scene == null:
		return null
	var enemy: CharacterBody2D = scene.instantiate()
	enemy.position = spawn_offset.call() if spawn_offset.is_valid() else Vector2.ZERO
	enemy.add_to_group("enemies")
	if not entity_id.is_empty():
		enemy.set_meta(ENTITY_MARKER, entity_id)
	if schedule_index >= 0:
		enemy.set_meta(SCHEDULE_MARKER, schedule_index)
		_schedule_alive[schedule_index] += 1
	var enemy_health: Health = enemy.get_node("Health")
	# 死亡接线：退出战斗（移除）与存活计数都复用 Health.died 信号，同一机制覆盖所有敌人配置
	enemy_health.died.connect(enemy.queue_free)
	enemy_health.died.connect(_on_enemy_died.bind(enemy))
	entities.add_child(enemy)
	if player != null:
		# 追击目标相对路径：从实体节点指向玩家（入树后计算，不写死任何场景节点路径）
		enemy.target_path = enemy.get_path_to(player)
	alive_count += 1
	alive_changed.emit(alive_count)
	enemy_spawned.emit(enemy)
	return enemy


## 单个实例只结算一次：重复 died 通知不得重复递减计数或重复推进波次。
## 参数不标类型：死亡会驱动 queue_free，重复通知时实例可能已释放。
func _on_enemy_died(enemy) -> void:
	if is_instance_valid(enemy):
		if enemy.has_meta(DEFEAT_MARKER):
			_trace_duplicate("enemy_death", _enemy_entity_id(enemy))
			return
		enemy.set_meta(DEFEAT_MARKER, true)
		if enemy.has_meta(SCHEDULE_MARKER):
			var schedule_index := int(enemy.get_meta(SCHEDULE_MARKER))
			if schedule_index >= 0 and schedule_index < _schedule_alive.size():
				_schedule_alive[schedule_index] = maxi(_schedule_alive[schedule_index] - 1, 0)
	alive_count = max(alive_count - 1, 0)
	alive_changed.emit(alive_count)
	if _mode == LevelConfig.MODE_WAVES and alive_count <= 0:
		_advance_wave()
	elif _mode == LevelConfig.MODE_BOSS and not _stages.is_empty() \
			and _stage_type == LevelConfig.STAGE_CLEAR_ENEMIES and alive_count <= 0:
		_complete_stage()


# ---------- 出口与胜负 ----------


func _on_exit_zone_body_entered(body: Node2D) -> void:
	if not body.is_in_group("players"):
		return
	if state != State.Playing:
		_trace_duplicate("exit_after_finish")
		return
	# boss 模式：Boss 存活 / 阶段链未完成时无论门状态如何都不得提前胜利
	if _mode == LevelConfig.MODE_BOSS and (not _boss_is_defeated or not _stages_done):
		_trace_invalid("victory_blocked")
		return
	# 出口区位于出口门后，门未开时物理上不可达；此处再做门状态校验兜底
	if exit_door != null and not exit_door.is_open():
		_trace_invalid("exit_locked")
		return
	_victory_reason = "exit_reached_after_unlock"
	_finish(true)


func _on_player_died() -> void:
	if state != State.Playing:
		_trace_duplicate("player_death")
		return
	_failure_reason = "player_died"
	_finish(false)


## 强制结束（适配层 / 测试入口）：与内部胜负判定共用同一守卫
##（仅 Playing 可结束；finished 信号只发一次）。
func finish(success: bool) -> void:
	if success:
		_victory_reason = "forced"
	else:
		_failure_reason = "forced"
	_finish(success)


func _finish(success: bool) -> void:
	if state != State.Playing:
		_trace_duplicate("already_finished")
		return
	state = State.Completed if success else State.Failed
	_trace_terminal(success)
	finished.emit(success)


# ---------- 诊断事件接线（只观测生产状态机，不驱动任何状态）----------


func _start_trace() -> void:
	if not trace_enabled or trace == null:
		return
	trace.begin("run-%d" % Time.get_ticks_usec(), Time.get_ticks_msec(), _config_path)
	_trace_event("orchestration_started", "orchestrator", _mode, null, null, "", "",
		{"mode": _mode, "stage_count": _stages.size()})


func _trace_event(event_type: String, source: String, reason: String,
		stage_id, stage_index, entity_id, instance_name, data: Dictionary = {}) -> void:
	if not trace_enabled or trace == null:
		return
	trace.record(event_type, source, reason, stage_id, stage_index, entity_id,
		instance_name, data)


## 已结算的重复通知：可观测但不重复结算（稳定 reason 代码）。
func _trace_duplicate(reason: String, entity_id := "") -> void:
	_trace_event("duplicate_event_ignored", "orchestrator", reason,
		_last_active_stage_id if _last_active_stage_index >= 0 else null,
		_last_active_stage_index if _last_active_stage_index >= 0 else null,
		entity_id, "", {})


## 被拒绝的非法转换：记录稳定原因，不改状态、不制造假胜利。
func _trace_invalid(reason: String) -> void:
	_trace_event("invalid_transition_rejected", "orchestrator", reason,
		_last_active_stage_id if _last_active_stage_index >= 0 else null,
		_last_active_stage_index if _last_active_stage_index >= 0 else null,
		"", "", {})


func _trace_terminal(success: bool) -> void:
	_trace_event("level_victory" if success else "level_failed", "orchestrator",
		_victory_reason if success else _failure_reason,
		_last_active_stage_id if _last_active_stage_index >= 0 else null,
		_last_active_stage_index if _last_active_stage_index >= 0 else null,
		"", "", {})


static func _enemy_entity_id(enemy) -> String:
	if enemy != null and is_instance_valid(enemy) and enemy.has_meta(ENTITY_MARKER):
		return str(enemy.get_meta(ENTITY_MARKER))
	return ""
