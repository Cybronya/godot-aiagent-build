class_name SfxPool
extends Node
## 音效池组件：运行时创建一组 AudioStreamPlayer 轮转播放一次性音效（SFX），
## 避免频繁实例化播放器，也避免单播放器被后一个音效掐断。
##
## 设计抽象自外部参考片段（KenneyNL/Starter-Kit-3D-Platformer 的 audio.gd，MIT，
## 见 code_library references/audio/...audio.gd——12 池 + 队列 + 音调随机）。
## 简化与加固：
## - 去掉路径字符串与 _process 轮询队列：play(stream) 同步取播放器立即播放，
##   并同步广播 played（调用方不需要等 finished）。
## - 轮转取代队列：空闲池满时直接复用「下一个」播放器（round-robin 抢占最旧），
##   池永远不会满到拒绝——语义是"最新音效优先"。
## - 音调随机 pitch_scale = 1 ± pitch_range，避免同一段音效连播的重复感。
## - 忙碌簿记自管，绝不读引擎播放状态做判断（实测引擎行为随环境漂移：
##   完整项目里 headless 的 Dummy 驱动会真实混音（playing=true、时长到期
##   finished）；精简项目里同一驱动不启动播放且 finished 立即触发。两种环境下
##   读 playing/等 finished 都会得到不同簿记）。规则：
##     * 非无头环境：play 标记占用、finished 归还（真实回放语义）。
##     * 无头环境（DisplayServer "headless"）：引擎不会真正出声，不连接
##       finished——占用只能由抢占释放（active_count 上限 = pool_size，确定）。
##
## 所有权：独占自己创建的 AudioStreamPlayer 子节点（_ready 时生成，离开场景时
## 随子树释放）；不触碰宿主任何属性，不订阅任何 Feature 状态。

signal played()            ## 一次播放已触发（同步广播；无载荷——stream 由调用方持有）

@export var pool_size := 8        ## 池内播放器数量
@export var pitch_range := 0.1    ## 音调随机幅度：pitch_scale ∈ 1±pitch_range
@export var volume_db := 0.0      ## 池内播放器统一音量

var _players: Array[AudioStreamPlayer] = []
var _busy: Array[bool] = []
var _next := 0
var _active := 0
var _headless := false


func _ready() -> void:
	_headless = DisplayServer.get_name() == "headless"
	for i: int in pool_size:
		var p := AudioStreamPlayer.new()
		p.volume_db = volume_db
		if not _headless:
			p.finished.connect(_on_finished.bind(i))
		add_child(p)
		_players.append(p)
		_busy.append(false)


## 播放一段音效。stream 为空返回 false；否则取下一个播放器（若仍忙碌则抢占）
## 播放并同步广播 played。永远成功（除非池未初始化）——最新音效优先。
func play(stream: AudioStream) -> bool:
	if stream == null or _players.is_empty():
		return false
	var idx := _next
	_next = (_next + 1) % _players.size()
	if _busy[idx]:
		_busy[idx] = false
		_active -= 1            # 抢占最旧占用
	var p := _players[idx]
	p.stream = stream
	p.pitch_scale = 1.0 + randf_range(-pitch_range, pitch_range)
	p.play()
	_busy[idx] = true
	_active += 1
	played.emit()
	return true


## 当前被占用的播放器数量。非无头环境 = 正在回放（未 finished）；无头环境 =
## 自上次起尚未被抢占的播放数（上限 pool_size）。读的是自管簿记，不依赖引擎状态。
func active_count() -> int:
	return _active


func _on_finished(idx: int) -> void:
	if _busy[idx]:
		_busy[idx] = false
		_active -= 1
