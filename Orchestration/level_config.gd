class_name LevelConfig
extends RefCounted
## 关卡编排配置（Phase 1.14 通用化）：解析 + 校验 + 归一化。
##
## 与 Phase 1.13 的边界变化：本类从 `Scenes/timed_combat_arena.gd` 抽离为**场景无关**的
## 通用能力，只认 `.ai/context/level_schema.yaml` 契约，不依赖任何场景的节点路径 /
## 场景名称 / 专属状态。消费方（场景适配层）只使用本类的产出数据与错误诊断。
##
## 支持三种编排模式（schema version 2 引入；version 1 按遗留 waves 模式兼容）：
##   waves   —— 顺序波次：首波按 entries 生成，清空后推进下一波；出口/胜利由配置决定
##              （Phase 1.13 语义，TimedCombatArena 使用）。
##   holdout —— 生存坚守：按 spawns 调度表持续生成（间隔 / 延迟 / 上限），
##              生存到 survival_duration 即胜利；无出口概念（SurvivalArena 适配层使用）。
##   boss    —— Boss 战斗（Phase 1.20）：只有一个**显式声明**的 Boss 实体（boss.entity），
##              实例来源是 boss.spawn：existing（适配层按 boss.instance 点名绑定已存在实例）
##              或 on_start（编排器从 entities[boss.entity].scene 实例化）。Boss 死亡是唯一的
##              战斗完成信号；Boss 存活时不得提前胜利。绝不按 role / 节点名推断 Boss 身份。
##              Phase 1.21 可选 stages：clear_enemies → defeat_boss[ → complete_level] 的
##              显式有序阶段链；顺序只由数组决定，省略 stages 即 Phase 1.20 单阶段兼容。
##
## 诊断契约（G13）：每条错误以 `<配置文件>: <JSON 字段路径>: <说明>` 形式给出，
## stage 标记失败发生的编排阶段（config_load = 读取/解析，config_validate = 规则校验），
## 使失败可定位到关卡配置、错误字段与相关实体场景引用。
##
## 校验规则与 `gameplay_planner/level_planner.py::validate_level`（producer 与
## validator 的唯一实现）及 `.ai/context/level_schema.yaml` 保持镜像；改规则必须同改两处。

const SCHEMA_ID := "level_orchestration"
const VERSION := 2
const SUPPORTED_VERSIONS := [1, 2]
const MODE_WAVES := "waves"
const MODE_HOLDOUT := "holdout"
const MODE_BOSS := "boss"
const DEFAULT_WAVE_DURATION := 30.0

# 关卡配置合法值（与 level_schema.yaml 一致；拼错即失败，不静默回退）
const EXIT_ALL_WAVES_CLEARED := "all_waves_cleared"
const EXIT_NEVER := "never"
const EXIT_BOSS_DEFEATED := "boss_defeated"
const VICTORY_EXIT_REACHED := "exit_reached_after_unlock"
const VICTORY_ALL_WAVES_CLEARED := "all_waves_cleared"
const VICTORY_SURVIVE_DURATION := "survive_duration"
const VICTORY_BOSS_DEFEATED := "boss_defeated"
const BOSS_SPAWN_EXISTING := "existing"
const BOSS_SPAWN_ON_START := "on_start"
## 多阶段 Boss（Phase 1.21）：阶段类型；顺序由 stages 数组显式声明，绝不按节点遍历推断。
const STAGE_CLEAR_ENEMIES := "clear_enemies"
const STAGE_DEFEAT_BOSS := "defeat_boss"
const STAGE_COMPLETE_LEVEL := "complete_level"
const SUPPORTED_STAGE_TYPES := [STAGE_CLEAR_ENEMIES, STAGE_DEFEAT_BOSS, STAGE_COMPLETE_LEVEL]

## 失败阶段：none = 无失败；config_load = 读取/JSON 解析；config_validate = 规则校验
var stage := "none"
var source_path := ""
var errors: PackedStringArray = []

## ---- 校验通过后的归一化产出（运行时只读）----
var mode := MODE_WAVES
var arena_scene := ""
## waves 模式：[{id, duration, entries: [{scene: PackedScene, count: int}]}]
var waves: Array[Dictionary] = []
var exit_unlock_when := EXIT_ALL_WAVES_CLEARED
var victory_condition := VICTORY_EXIT_REACHED
## holdout 模式：
var survival_duration := 0.0
var max_alive_total := 0
## [{entity, scene: PackedScene, interval, delay, max_alive}]
var spawn_schedules: Array[Dictionary] = []
## boss 模式：
var boss_entity := ""
## 已存在实例的相对节点路径（spawn = existing 时必填；空串 = on_start 生成）
var boss_instance_path := ""
var boss_spawn := BOSS_SPAWN_ON_START
var boss_scene: PackedScene
## 多阶段 Boss（可选）：[{id, type, entity, entries: [{entity, scene: PackedScene, count}]}]
## 空数组 = 单阶段 boss（Phase 1.20 兼容）；非空时由编排器按数组顺序推进。
var stages: Array[Dictionary] = []


func is_valid() -> bool:
	return errors.is_empty()


## 从 res:// 路径读取并校验关卡配置。任何失败都返回带 errors/stage 的对象（不抛异常）。
static func from_file(path: String) -> LevelConfig:
	var config := LevelConfig.new()
	config.source_path = path
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		config.stage = "config_load"
		config.errors.append("%s: 无法读取关卡配置文件" % path)
		return config
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		config.stage = "config_load"
		config.errors.append("%s: root: 配置不是 JSON 对象" % path)
		return config
	config._validate(parsed)
	if not config.errors.is_empty():
		config.stage = "config_validate"
		return config
	config._build(parsed)
	return config


## 遗留 waves 数据 → 内存配置（场景内手写 waves 兼容通道；导出数据受信任，不做规则校验）。
## 每波接受两种形态：entries（配置形态）或 enemy_scene/enemy_count/elite_scene/elite_count。
static func make_waves(raw_waves: Array) -> LevelConfig:
	var config := LevelConfig.new()
	config.mode = MODE_WAVES
	for wave in raw_waves:
		if not (wave is Dictionary):
			continue
		var entries: Array[Dictionary] = []
		if wave.get("entries") != null:
			for entry in wave["entries"]:
				entries.append({
					"scene": entry.get("scene"),
					"count": int(entry.get("count", 0)),
				})
		else:
			if wave.get("enemy_scene") != null:
				entries.append({"scene": wave["enemy_scene"], "count": int(wave.get("enemy_count", 0))})
			if wave.get("elite_scene") != null:
				entries.append({"scene": wave["elite_scene"], "count": int(wave.get("elite_count", 0))})
		config.waves.append({
			"id": "",
			"duration": float(wave.get("duration", DEFAULT_WAVE_DURATION)),
			"entries": entries,
		})
	if config.waves.is_empty():
		config.stage = "config_validate"
		config.errors.append("waves: 必填非空数组（场景内手写 waves 为空）")
	return config


## 遗留 holdout 导出 → 内存配置（SurvivalArena 适配层的无配置兼容通道）。
## spawns: [{scene: PackedScene, interval, delay, max_alive}]；scene 为 null 的条目跳过。
static func make_holdout(survival_duration: float, max_alive_total: int, spawns: Array) -> LevelConfig:
	var config := LevelConfig.new()
	config.mode = MODE_HOLDOUT
	config.survival_duration = survival_duration
	config.max_alive_total = int(max_alive_total)
	config.victory_condition = VICTORY_SURVIVE_DURATION
	for spawn in spawns:
		if not (spawn is Dictionary):
			continue
		var scene: Variant = spawn.get("scene")
		if scene == null:
			continue
		config.spawn_schedules.append({
			"entity": str(spawn.get("entity", "")),
			"scene": scene,
			"interval": float(spawn.get("interval", 1.0)),
			"delay": float(spawn.get("delay", 0.0)),
			"max_alive": int(spawn.get("max_alive", 0)),
		})
	return config


# ---------- 校验（镜像 level_schema.yaml 规则集） ----------


func _validate(config: Dictionary) -> void:
	var schema: Variant = config.get("schema")
	var version := 0
	if not (schema is Dictionary):
		_fail("schema", "需要 {id: %s, version: %d}" % [SCHEMA_ID, VERSION])
	else:
		version = int((schema as Dictionary).get("version", 0))
		if str((schema as Dictionary).get("id", "")) != SCHEMA_ID:
			_fail("schema", "需要 {id: %s, version: %d}" % [SCHEMA_ID, VERSION])
		elif not SUPPORTED_VERSIONS.has(version):
			_fail("schema", "不支持的版本 %d（支持 %s）" % [version, str(SUPPORTED_VERSIONS)])

	var level_block: Variant = config.get("level")
	if not (level_block is Dictionary) \
			or str((level_block as Dictionary).get("id", "")).strip_edges().is_empty():
		_fail("level.id", "必填非空字符串")
	else:
		var arena: Variant = (level_block as Dictionary).get("arena_scene")
		if arena != null and (not (arena is String) or not str(arena).begins_with("res://")):
			_fail("level.arena_scene", "必须是 res:// 路径字符串，实际 %s" % str(arena))

	var entities: Variant = config.get("entities")
	var entity_ids: Array = []
	if not (entities is Dictionary) or (entities as Dictionary).is_empty():
		_fail("entities", "必填非空对象")
	else:
		for entity_id in (entities as Dictionary).keys():
			var node: Variant = (entities as Dictionary)[entity_id]
			var scene_path := ""
			if node is Dictionary:
				scene_path = str((node as Dictionary).get("scene", ""))
			if not scene_path.begins_with("res://"):
				_fail("entities.%s.scene" % entity_id, "必填 res:// 路径")
				continue
			if not ResourceLoader.exists(scene_path):
				_fail("entities.%s.scene" % entity_id, "场景不存在 %s" % scene_path)
				continue
			entity_ids.append(entity_id)

	var mode_value := MODE_WAVES
	var mode_block: Variant = config.get("mode")
	if mode_block != null:
		if not (mode_block is String) \
				or (str(mode_block) != MODE_WAVES and str(mode_block) != MODE_HOLDOUT \
					and str(mode_block) != MODE_BOSS):
			_fail("mode", "只支持 %s / %s / %s，实际 %s"
				% [MODE_WAVES, MODE_HOLDOUT, MODE_BOSS, str(mode_block)])
		else:
			mode_value = str(mode_block)
	if version == 1 and (mode_value == MODE_HOLDOUT or config.get("holdout") != null):
		_fail("mode", "version 1 配置不支持 holdout 编排（请使用 version 2）")
	if version == 1 and (mode_value == MODE_BOSS or config.get("boss") != null):
		_fail("mode", "version 1 配置不支持 boss 编排（请使用 version 2）")

	if mode_value == MODE_HOLDOUT:
		_validate_holdout(config, entity_ids)
	elif mode_value == MODE_BOSS:
		_validate_boss(config, entity_ids)
	else:
		_validate_waves(config, entity_ids)


func _validate_waves(config: Dictionary, entity_ids: Array) -> void:
	if config.get("boss") != null:
		_fail("boss", "只支持 mode = boss（waves 模式请勿声明 boss 块）")
	if config.get("stages") != null:
		_fail("stages", "只有 mode = boss 支持多阶段 Boss（waves 模式请使用 waves）")
	var waves_block: Variant = config.get("waves")
	if not (waves_block is Array) or (waves_block as Array).is_empty():
		_fail("waves", "必填非空数组")
	else:
		var seen_ids: Array = []
		for index in (waves_block as Array).size():
			var wave: Variant = (waves_block as Array)[index]
			var where := "waves[%d]" % index
			if not (wave is Dictionary):
				_fail(where, "应为对象")
				continue
			var wave_id: Variant = (wave as Dictionary).get("id")
			if not (wave_id is String) or str(wave_id).strip_edges().is_empty():
				_fail("%s.id" % where, "必填非空字符串")
			elif seen_ids.has(wave_id):
				_fail("%s.id" % where, "重复的波次 id %s" % str(wave_id))
			else:
				seen_ids.append(wave_id)
			var duration: Variant = (wave as Dictionary).get("duration")
			if duration != null and not _is_positive_number(duration):
				_fail("%s.duration" % where, "必须为 > 0 的数")
			var entries: Variant = (wave as Dictionary).get("entries")
			if not (entries is Array) or (entries as Array).is_empty():
				_fail("%s.entries" % where, "必填非空数组")
				continue
			for entry_index in (entries as Array).size():
				var entry: Variant = (entries as Array)[entry_index]
				var entry_where := "%s.entries[%d]" % [where, entry_index]
				if not (entry is Dictionary):
					_fail(entry_where, "应为对象")
					continue
				var entity_id := str((entry as Dictionary).get("entity", ""))
				if entity_id.is_empty() or not entity_ids.has(entity_id):
					_fail("%s.entity" % entry_where, "未声明的实体 %s" % entity_id)
				if not _is_positive_integer((entry as Dictionary).get("count")):
					_fail("%s.count" % entry_where, "必须为 >= 1 的整数")

	var exit_block: Variant = config.get("exit")
	var unlock := EXIT_ALL_WAVES_CLEARED
	if exit_block != null:
		if not (exit_block is Dictionary):
			_fail("exit", "应为对象")
		else:
			unlock = str((exit_block as Dictionary).get("unlock_when", EXIT_ALL_WAVES_CLEARED))
	if unlock != EXIT_ALL_WAVES_CLEARED and unlock != EXIT_NEVER:
		_fail("exit.unlock_when", "不支持的值 %s" % unlock)

	var victory_block: Variant = config.get("victory")
	var condition := VICTORY_EXIT_REACHED
	if victory_block != null:
		if not (victory_block is Dictionary):
			_fail("victory", "应为对象")
		else:
			condition = str((victory_block as Dictionary).get("condition", VICTORY_EXIT_REACHED))
	if condition != VICTORY_EXIT_REACHED and condition != VICTORY_ALL_WAVES_CLEARED:
		_fail("victory.condition", "不支持的值 %s" % condition)
	# 交叉规则：出口永不开 + 胜利依赖出口 = 胜利不可达
	if unlock == EXIT_NEVER and condition == VICTORY_EXIT_REACHED:
		_fail("victory.condition", "胜利不可达（exit.unlock_when = never）")


func _validate_holdout(config: Dictionary, entity_ids: Array) -> void:
	if config.get("waves") != null:
		_fail("waves", "holdout 模式不支持顺序波次（请用 holdout.spawns 持续生成调度）")
	if config.get("exit") != null:
		_fail("exit", "holdout 模式不支持出口配置（生存关卡无出口）")
	if config.get("boss") != null:
		_fail("boss", "holdout 模式不支持 Boss 阶段（请用 mode = boss）")
	if config.get("stages") != null:
		_fail("stages", "holdout 模式不支持多阶段 Boss（请用 mode = boss）")
	var holdout: Variant = config.get("holdout")
	if not (holdout is Dictionary):
		_fail("holdout", "必填对象（holdout 模式）")
	else:
		var duration: Variant = (holdout as Dictionary).get("survival_duration")
		if not _is_positive_number(duration):
			_fail("holdout.survival_duration", "必须为 > 0 的数")
		var max_alive: Variant = (holdout as Dictionary).get("max_alive")
		if max_alive != null and not _is_positive_integer(max_alive):
			_fail("holdout.max_alive", "必须为 >= 1 的整数")
		var spawns: Variant = (holdout as Dictionary).get("spawns")
		if not (spawns is Array) or (spawns as Array).is_empty():
			_fail("holdout.spawns", "必填非空数组")
		else:
			for index in (spawns as Array).size():
				var spawn: Variant = (spawns as Array)[index]
				var where := "holdout.spawns[%d]" % index
				if not (spawn is Dictionary):
					_fail(where, "应为对象")
					continue
				var entity_id := str((spawn as Dictionary).get("entity", ""))
				if entity_id.is_empty() or not entity_ids.has(entity_id):
					_fail("%s.entity" % where, "未声明的实体 %s" % entity_id)
				if (spawn as Dictionary).has("count"):
					_fail("%s.count" % where, "holdout 模式请用 max_alive（count 仅用于 waves 波次）")
				if not _is_positive_number((spawn as Dictionary).get("interval")):
					_fail("%s.interval" % where, "必须为 > 0 的数")
				var delay: Variant = (spawn as Dictionary).get("delay")
				if delay != null and not _is_non_negative_number(delay):
					_fail("%s.delay" % where, "必须为 >= 0 的数")
				var spawn_max_alive: Variant = (spawn as Dictionary).get("max_alive")
				if spawn_max_alive != null and not _is_positive_integer(spawn_max_alive):
					_fail("%s.max_alive" % where, "必须为 >= 1 的整数")

	var victory_block: Variant = config.get("victory")
	if victory_block == null:
		return
	if not (victory_block is Dictionary):
		_fail("victory", "应为对象")
		return
	var condition: Variant = (victory_block as Dictionary).get("condition", VICTORY_SURVIVE_DURATION)
	if str(condition) != VICTORY_SURVIVE_DURATION:
		_fail("victory.condition", "holdout 模式只支持 %s，实际 %s"
			% [VICTORY_SURVIVE_DURATION, str(condition)])


## boss 模式：waves / holdout 不得出现；Boss 身份与实例来源必须显式且可解析。
func _validate_boss(config: Dictionary, entity_ids: Array) -> void:
	if config.get("waves") != null:
		_fail("waves", "boss 模式不支持顺序波次（Boss 战由击败声明的 Boss 完成）")
	if config.get("holdout") != null:
		_fail("holdout", "boss 模式不支持持续生成调度")
	var boss: Variant = config.get("boss")
	if not (boss is Dictionary):
		_fail("boss", "必填对象（boss 模式）")
		return
	var entity_id := str((boss as Dictionary).get("entity", ""))
	if entity_id.is_empty() or not entity_ids.has(entity_id):
		_fail("boss.entity", "未声明的实体 %s" % entity_id)
	var instance: Variant = (boss as Dictionary).get("instance")
	if instance != null and not _is_relative_node_path(instance):
		_fail("boss.instance", "必须是相对节点路径字符串，实际 %s" % str(instance))
	var default_spawn := BOSS_SPAWN_EXISTING if instance != null else BOSS_SPAWN_ON_START
	var spawn := str((boss as Dictionary).get("spawn", default_spawn))
	if spawn != BOSS_SPAWN_EXISTING and spawn != BOSS_SPAWN_ON_START:
		_fail("boss.spawn", "只支持 %s / %s，实际 %s"
			% [BOSS_SPAWN_EXISTING, BOSS_SPAWN_ON_START, spawn])
	elif spawn == BOSS_SPAWN_EXISTING and not _is_relative_node_path(instance):
		_fail("boss.instance", "spawn = existing 时必须提供已存在实例的相对路径")

	var exit_block: Variant = config.get("exit")
	var unlock := EXIT_BOSS_DEFEATED
	if exit_block != null:
		if not (exit_block is Dictionary):
			_fail("exit", "应为对象")
		else:
			unlock = str((exit_block as Dictionary).get("unlock_when", EXIT_BOSS_DEFEATED))
	if unlock != EXIT_BOSS_DEFEATED and unlock != EXIT_NEVER:
		_fail("exit.unlock_when", "boss 模式只支持 %s / %s，实际 %s"
			% [EXIT_BOSS_DEFEATED, EXIT_NEVER, unlock])

	var victory_block: Variant = config.get("victory")
	var condition := VICTORY_BOSS_DEFEATED
	if victory_block != null:
		if not (victory_block is Dictionary):
			_fail("victory", "应为对象")
		else:
			condition = str((victory_block as Dictionary).get("condition", VICTORY_BOSS_DEFEATED))
	if condition != VICTORY_BOSS_DEFEATED and condition != VICTORY_EXIT_REACHED:
		_fail("victory.condition", "boss 模式只支持 %s / %s，实际 %s"
			% [VICTORY_BOSS_DEFEATED, VICTORY_EXIT_REACHED, condition])
	# 交叉规则：出口永不开 + 胜利依赖出口 = 胜利不可达
	if unlock == EXIT_NEVER and condition == VICTORY_EXIT_REACHED:
		_fail("victory.condition", "胜利不可达（exit.unlock_when = never）")

	if config.get("stages") != null:
		_validate_stages(config, entity_ids, entity_id, unlock, condition)


## 多阶段 Boss 契约（Phase 1.21）：
##   - stages 非空且 >= 2；id 唯一；type 只能是三种阶段类型之一；
##   - clear_enemies 必须引用已声明实体且不能是 Boss 本体，entries 非空、count >= 1；
##   - 必须且只能有一个 defeat_boss，且只能是最后一个阶段（或紧随 complete_level 之前）；
##   - complete_level 只能作为最后一个阶段，且要求 victory=boss_defeated + exit=never；
##   - 阶段顺序只由数组决定，不依赖目录顺序 / 节点遍历 / 名称匹配。
func _validate_stages(config: Dictionary, entity_ids: Array, boss_entity: String,
		unlock: String, condition: String) -> void:
	var stages_block: Variant = config.get("stages")
	if not (stages_block is Array) or (stages_block as Array).is_empty():
		_fail("stages", "必填非空数组（多阶段 Boss）")
		return
	var stages_array: Array = stages_block
	if stages_array.size() < 2:
		_fail("stages", "至少需要 2 个阶段（clear_enemies → defeat_boss[ → complete_level]）")
	var seen_ids: Array = []
	var clear_count := 0
	var defeat_count := 0
	var complete_count := 0
	for index in stages_array.size():
		var stage_block: Variant = stages_array[index]
		var where := "stages[%d]" % index
		if not (stage_block is Dictionary):
			_fail(where, "应为对象")
			continue
		var stage_id: Variant = (stage_block as Dictionary).get("id")
		if not (stage_id is String) or str(stage_id).strip_edges().is_empty():
			_fail("%s.id" % where, "必填非空字符串")
		elif seen_ids.has(stage_id):
			_fail("%s.id" % where, "重复的阶段 id %s" % str(stage_id))
		else:
			seen_ids.append(stage_id)
		var stage_type := str((stage_block as Dictionary).get("type", ""))
		if not SUPPORTED_STAGE_TYPES.has(stage_type):
			_fail("%s.type" % where, "不支持的类型 %s（支持 %s）"
				% [stage_type, str(SUPPORTED_STAGE_TYPES)])
			continue
		if stage_type == STAGE_CLEAR_ENEMIES:
			clear_count += 1
			var entries: Variant = (stage_block as Dictionary).get("entries")
			if not (entries is Array) or (entries as Array).is_empty():
				_fail("%s.entries" % where, "clear_enemies 必填非空数组")
				continue
			for entry_index in (entries as Array).size():
				var entry: Variant = (entries as Array)[entry_index]
				var entry_where := "%s.entries[%d]" % [where, entry_index]
				if not (entry is Dictionary):
					_fail(entry_where, "应为对象")
					continue
				var entry_entity := str((entry as Dictionary).get("entity", ""))
				if entry_entity.is_empty() or not entity_ids.has(entry_entity):
					_fail("%s.entity" % entry_where, "未声明的实体 %s" % entry_entity)
				elif entry_entity == boss_entity:
					_fail("%s.entity" % entry_where,
						"clear_enemies 不能引用 Boss 实体 %s（Boss 只能由 defeat_boss 阶段结算）"
						% boss_entity)
				if not _is_positive_integer((entry as Dictionary).get("count")):
					_fail("%s.count" % entry_where, "必须为 >= 1 的整数")
		elif stage_type == STAGE_DEFEAT_BOSS:
			defeat_count += 1
			var stage_entity := str((stage_block as Dictionary).get("entity", ""))
			if stage_entity.is_empty() or stage_entity != boss_entity:
				_fail("%s.entity" % where,
					"defeat_boss 必须引用 boss.entity（%s），实际 %s"
					% [boss_entity, stage_entity])
			var is_last := index == stages_array.size() - 1
			var before_complete := false
			if index == stages_array.size() - 2 and stages_array[index + 1] is Dictionary:
				before_complete = str((stages_array[index + 1] as Dictionary).get("type", "")) \
					== STAGE_COMPLETE_LEVEL
			if not is_last and not before_complete:
				_fail(where, "defeat_boss 必须是最后一个阶段（或紧随 complete_level 之前）")
		elif stage_type == STAGE_COMPLETE_LEVEL:
			complete_count += 1
			if index != stages_array.size() - 1:
				_fail(where, "complete_level 只能作为最后一个阶段")
	if clear_count == 0:
		_fail("stages", "至少需要一个 clear_enemies 阶段（Boss 不得在清理阶段前激活）")
	if defeat_count != 1:
		_fail("stages", "必须且只能有一个 defeat_boss 阶段（实际 %d）" % defeat_count)
	if complete_count > 1:
		_fail("stages", "complete_level 最多只能出现一次（实际 %d）" % complete_count)
	if complete_count == 1:
		if condition != VICTORY_BOSS_DEFEATED:
			_fail("victory.condition", "complete_level 阶段要求 victory.condition = %s，实际 %s"
				% [VICTORY_BOSS_DEFEATED, condition])
		if unlock != EXIT_NEVER:
			_fail("exit.unlock_when", "complete_level 阶段要求 exit.unlock_when = %s，实际 %s"
				% [EXIT_NEVER, unlock])


# ---------- 归一化产出 ----------
# （多阶段 stages 的归一化在同一函数内完成；PackedScene 在加载期解析，运行期只消费数据）


func _build(config: Dictionary) -> void:
	var mode_value := MODE_WAVES
	var mode_block: Variant = config.get("mode")
	if mode_block is String and (str(mode_block) == MODE_WAVES or str(mode_block) == MODE_HOLDOUT \
			or str(mode_block) == MODE_BOSS):
		mode_value = str(mode_block)
	mode = mode_value
	var level_block: Variant = config.get("level")
	if level_block is Dictionary:
		arena_scene = str((level_block as Dictionary).get("arena_scene", ""))

	if mode == MODE_BOSS:
		var boss: Dictionary = config["boss"]
		boss_entity = str(boss["entity"])
		boss_instance_path = str(boss.get("instance", ""))
		boss_spawn = str(boss.get("spawn", BOSS_SPAWN_EXISTING if not boss_instance_path.is_empty() else BOSS_SPAWN_ON_START))
		var entities: Dictionary = config["entities"]
		boss_scene = load(str((entities[boss_entity] as Dictionary)["scene"]))
		var boss_exit: Variant = config.get("exit")
		if boss_exit is Dictionary:
			exit_unlock_when = str((boss_exit as Dictionary).get("unlock_when", EXIT_BOSS_DEFEATED))
		else:
			exit_unlock_when = EXIT_BOSS_DEFEATED
		var boss_victory: Variant = config.get("victory")
		if boss_victory is Dictionary:
			victory_condition = str((boss_victory as Dictionary).get("condition", VICTORY_BOSS_DEFEATED))
		else:
			victory_condition = VICTORY_BOSS_DEFEATED
		var stage_block: Variant = config.get("stages")
		if stage_block is Array:
			for stage in stage_block:
				var built := {"id": str(stage.get("id", "")), "type": str(stage.get("type", "")),
					"entries": []}
				if built["type"] == STAGE_DEFEAT_BOSS:
					built["entity"] = str(stage.get("entity", ""))
				elif built["type"] == STAGE_CLEAR_ENEMIES:
					var entries: Array[Dictionary] = []
					for entry in stage.get("entries", []):
						var entry_entity := str(entry["entity"])
						entries.append({"entity": entry_entity,
							"scene": load(str(entities[entry_entity]["scene"])),
							"count": int(entry["count"])})
					built["entries"] = entries
				stages.append(built)
		return

	if mode == MODE_HOLDOUT:
		var holdout: Dictionary = config["holdout"]
		survival_duration = float(holdout["survival_duration"])
		max_alive_total = int(holdout.get("max_alive", 0))
		var entities: Dictionary = config["entities"]
		for spawn in holdout["spawns"]:
			var entity_id := str(spawn["entity"])
			spawn_schedules.append({
				"entity": entity_id,
				"scene": load(str(entities[entity_id]["scene"])),
				"interval": float(spawn["interval"]),
				"delay": float(spawn.get("delay", 0.0)),
				"max_alive": int(spawn.get("max_alive", 0)),
			})
		victory_condition = VICTORY_SURVIVE_DURATION
		return

	for wave in config["waves"]:
		waves.append({
			"id": str(wave.get("id", "")),
			"duration": float(wave.get("duration", DEFAULT_WAVE_DURATION)),
			"entries": _config_entries(wave, config["entities"]),
		})
	var exit_block: Variant = config.get("exit")
	if exit_block is Dictionary:
		exit_unlock_when = str((exit_block as Dictionary).get("unlock_when", EXIT_ALL_WAVES_CLEARED))
	var victory_block: Variant = config.get("victory")
	if victory_block is Dictionary:
		victory_condition = str((victory_block as Dictionary).get("condition", VICTORY_EXIT_REACHED))


func _config_entries(wave: Dictionary, entities: Dictionary) -> Array[Dictionary]:
	var entries: Array[Dictionary] = []
	for entry in wave["entries"]:
		var entity_id := str(entry["entity"])
		var scene_path := str(entities[entity_id]["scene"])
		entries.append({"entity": entity_id, "scene": load(scene_path), "count": int(entry["count"])})
	return entries


# ---------- 辅助 ----------


func _fail(field: String, message: String) -> void:
	if source_path.is_empty():
		errors.append("%s: %s" % [field, message])
	else:
		errors.append("%s: %s: %s" % [source_path, field, message])


## 相对节点路径：非空、不以 / 开头、不含 .. 段（不越出宿主场景根）
func _is_relative_node_path(value: Variant) -> bool:
	if not (value is String):
		return false
	var text := str(value).strip_edges()
	if text.is_empty() or text.begins_with("/"):
		return false
	for segment in text.split("/"):
		if segment == "..":
			return false
	return true


## JSON 数字一律解析为 float，因此「整数」判定按数值语义做（1.0 是合法整数）
func _is_positive_integer(value: Variant) -> bool:
	if not (value is float or value is int) or value is bool:
		return false
	var number := float(value)
	return number >= 1.0 and number == floor(number)


func _is_positive_number(value: Variant) -> bool:
	if not (value is float or value is int) or value is bool:
		return false
	return float(value) > 0.0


func _is_non_negative_number(value: Variant) -> bool:
	if not (value is float or value is int) or value is bool:
		return false
	return float(value) >= 0.0
