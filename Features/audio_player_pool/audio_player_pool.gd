class_name AudioPlayerPool
extends Node
## 音频播放器池：管理一组 AudioStreamPlayer，提供 prepare() 获取播放器、
## play() 快捷播放、fade_volume() 淡入淡出，池满时自动扩容至 max_pool_size。
##
## 抽象自 nathanhoad/godot_sound_manager (MIT)，简化：
## - 去掉多格式 bus 名称匹配，直接用传入名或回退 "Master"
## - 忙碌簿记自管，不依赖引擎播放状态判断（无头/真实环境行为一致）
## - prepare() 返回播放器节点，play() = prepare + play 快捷方式
## - 池满自动扩容，空闲超额自动回收至 default_pool_size
##
## 用法：作为 Node 挂载到场景树，调用 prepare(stream) 或 play(stream)。

signal player_prepared(player: AudioStreamPlayer)

@export var default_pool_size: int = 8
@export var max_pool_size: int = 32
@export var default_bus: String = "Master"

var _available: Array[AudioStreamPlayer] = []
var _busy: Array[AudioStreamPlayer] = []
var _bus: String = "Master"
var _tweens: Dictionary[AudioStreamPlayer, Tween] = {}


func _ready() -> void:
	_bus = _resolve_bus(default_bus)
	for i: int in default_pool_size:
		_add_player()


## 获取一个可用播放器并装载音频流。resource 为 null 返回 null。
## 返回的播放器已设好 stream/bus/volume，调用方可直接 play() 或操作。
func prepare(resource: AudioStream, override_bus: String = "") -> AudioStreamPlayer:
	if resource == null:
		return null
	var player: AudioStreamPlayer = _get_available()
	if player == null:
		return null
	player.stream = resource
	player.bus = override_bus if override_bus != "" else _bus
	player.volume_db = 0.0
	player.pitch_scale = 1.0
	_mark_busy(player)
	player_prepared.emit(player)
	return player


## 快捷方式：prepare + play。返回播放器节点（可用于 fade_volume 等后续操作）。
func play(resource: AudioStream, override_bus: String = "") -> AudioStreamPlayer:
	var player: AudioStreamPlayer = prepare(resource, override_bus)
	if player != null:
		player.play()
	return player


func _get_available() -> AudioStreamPlayer:
	if _available.is_empty():
		if _busy.size() >= max_pool_size:
			return null
		_add_player()
	return _available.pop_front()


func _add_player() -> void:
	var player := AudioStreamPlayer.new()
	add_child(player)
	player.bus = _bus
	player.finished.connect(_on_player_finished.bind(player))
	_available.append(player)


func _mark_busy(player: AudioStreamPlayer) -> void:
	if _available.has(player):
		_available.erase(player)
	if not _busy.has(player):
		_busy.append(player)


func _mark_available(player: AudioStreamPlayer) -> void:
	if _busy.has(player):
		_busy.erase(player)
	if _available.size() >= default_pool_size:
		_available.erase(player)
		player.queue_free()
	elif not _available.has(player):
		_available.append(player)


## 音量淡入淡出。from_db → to_db，duration 秒。淡出至 ≤-79dB 时自动停止并归还。
func fade_volume(player: AudioStreamPlayer, from_db: float, to_db: float, duration: float) -> void:
	_remove_tween(player)
	var tween := create_tween().bind_node(self)
	player.volume_db = from_db
	tween.tween_property(player, "volume_db", to_db, duration)
	_tweens[player] = tween
	tween.finished.connect(_on_fade_completed.bind(player, tween))


func _remove_tween(player: AudioStreamPlayer) -> void:
	if _tweens.has(player):
		_tweens[player].kill()
		_tweens.erase(player)


func _on_player_finished(player: AudioStreamPlayer) -> void:
	_mark_available(player)


func _on_fade_completed(player: AudioStreamPlayer, _tween: Tween) -> void:
	_remove_tween(player)
	if player.volume_db <= -79.0:
		player.stop()
		_mark_available(player)


func _resolve_bus(bus_name: String) -> String:
	if AudioServer.get_bus_index(bus_name) > -1:
		return bus_name
	return "Master"


func get_busy_count() -> int:
	return _busy.size()


func get_available_count() -> int:
	return _available.size()
