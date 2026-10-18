class_name LevelHost
extends Node
## 通用宿主适配层（Phase 1.20）：把**任意已存在的宿主场景**接到统一关卡编排。
##
## 定位（AD-003：跨实体流程由场景侧组合承担）：
##   - `LevelConfig` + `LevelOrchestrator` 仍是配置解析与运行时行为的唯一实现；
##   - 本类只做「宿主节点引用解析 + 实例绑定 + 信号转发」，不重新实现生成 / 计数 /
##     Boss 死亡判定 / 开门 / 胜负规则；
##   - 生成链路产出的组合宿主（Scene Composer `--compose-plan` 的 .tscn）没有专属脚本，
##     由调用方把本节点挂到宿主根下，即可用 `Levels/<id>.json` 驱动。
##
## Boss 实例来源（绝不按节点名 / role 猜测）：
##   - `boss.spawn = existing`：本类按 `LevelConfig.boss_instance_path` 解析真实实例，
##     再调用 `LevelOrchestrator.bind_boss(配置声明的 entity id, 实例)`；
##   - `boss.spawn = on_start`：本类不绑定，交给编排器从配置场景生成。
##
## 用法：
##   var host := load("res://Scenes/GeneratedHost.tscn").instantiate()
##   add_child(host)
##   var adapter := LevelHost.new()
##   adapter.level_config_path = "res://Levels/<id>.json"
##   adapter.player_path = NodePath("Player")      # 生成宿主的实例名（可覆盖）
##   host.add_child(adapter)
##
## 诊断：配置无效 / 宿主实例解析失败时，`setup_errors` 给出可定位字段路径，
## 编排器进入 Failed（零生成、零胜负事件），绝不静默回退。

signal level_finished(success: bool)

## res://Levels/<id>.json（必填）
@export var level_config_path := ""
## 宿主根下的玩家实例（可为空：没有玩家死亡判定的关卡）
@export var player_path := NodePath("Player")
## 生成敌人的容器（缺省 = 宿主根）
@export var entities_path := NodePath(".")
## 出口门 / 出口区（可为空：Boss 死亡即胜利或无需出口的关卡）
@export var exit_door_path := NodePath("")
@export var exit_zone_path := NodePath("")
## on_start 生成 Boss 时的局部坐标
@export var spawn_position := Vector2.ZERO

## 最近一次应用的配置（配置读取失败时仍非 null，errors 可读）
var config: LevelConfig
var orchestrator: LevelOrchestrator
var setup_errors: PackedStringArray = []

var _host: Node


func is_setup_ok() -> bool:
	return setup_errors.is_empty() and orchestrator != null \
		and orchestrator.state != LevelOrchestrator.State.Failed


func _ready() -> void:
	_host = get_parent()
	if _host == null:
		_fail("host", "LevelHost 必须作为宿主场景根的子节点使用（找不到父节点）")
		return
	if level_config_path.is_empty():
		_fail("level_config_path", "必填 res:// 关卡配置路径")
		return

	config = LevelConfig.from_file(level_config_path)
	orchestrator = LevelOrchestrator.new()
	orchestrator.name = "LevelOrchestrator"
	add_child(orchestrator)
	orchestrator.player = _resolve(player_path)
	orchestrator.entities = _resolve(entities_path) if not entities_path.is_empty() else _host
	if orchestrator.entities == null:
		orchestrator.entities = _host
	orchestrator.exit_door = _resolve(exit_door_path)
	orchestrator.exit_zone = _resolve(exit_zone_path) as Area2D
	orchestrator.spawn_offset = func() -> Vector2: return spawn_position
	orchestrator.finished.connect(_on_finished)

	if not orchestrator.apply_config(config):
		setup_errors.append_array(orchestrator.get_config_errors())
		return

	if config.mode == LevelConfig.MODE_BOSS and config.boss_spawn == LevelConfig.BOSS_SPAWN_EXISTING:
		var boss := _resolve_path(config.boss_instance_path)
		if boss == null:
			# 编排器负责登记 bind 阶段诊断并进入 Failed
			orchestrator.fail_setup("boss.instance",
				"配置声明的 Boss 实例 %s 在宿主 %s 中不存在"
				% [config.boss_instance_path, _host.scene_file_path])
			setup_errors.append_array(orchestrator.get_config_errors())
			return
		if not orchestrator.bind_boss(config.boss_entity, boss):
			setup_errors.append_array(orchestrator.get_config_errors())
			return

	# 宿主正在 _ready 组装子节点时直接生成会触发 Godot「Parent node is busy」；
	# 延后到本帧 idle 再启动编排（生成/接线仍在生产代码内完成，探针不参与）。
	orchestrator.call_deferred("start")


## 当前配置要求的 Boss 实例（boss 模式；其他模式返回 null）
func get_boss() -> Node:
	return orchestrator.get_boss() if orchestrator != null else null


func get_diagnostics() -> Dictionary:
	if orchestrator == null:
		return {"stage": "bind", "errors": setup_errors, "config_path": level_config_path,
			"consumer_scene": _host.scene_file_path if _host != null else ""}
	var diagnostics := orchestrator.get_diagnostics()
	diagnostics["consumer_scene"] = _host.scene_file_path if _host != null else ""
	return diagnostics


func _resolve(path: NodePath) -> Node:
	if path.is_empty():
		return null
	return _host.get_node_or_null(path)


## 配置里的实例路径按字符串声明（JSON）；解析前拒绝越界路径。
func _resolve_path(path_text: String) -> Node:
	if path_text.strip_edges().is_empty():
		return null
	for segment in path_text.split("/"):
		if segment == "..":
			return null
	return _host.get_node_or_null(NodePath(path_text))


func _on_finished(success: bool) -> void:
	level_finished.emit(success)


func _fail(field: String, message: String) -> void:
	setup_errors.append("%s: %s" % [field, message])
	orchestrator = null
