extends SceneTree
## SfxPool 组件自身验证：播放生效与同步广播、null 拒绝、簿记占用、池抢占、
## finished 归还、音调边界、池规模。
##
## 用法：godot --headless --path . -s res://Features/sfx_pool/test_sfx_pool.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []
var _play_count := 0


func _initialize() -> void:
	var packed: PackedScene = load("res://Features/sfx_pool/SfxPool.tscn")
	if packed == null:
		_failures.append("加载 res://Features/sfx_pool/SfxPool.tscn 失败")
		_report()
		return
	seed(1337)  # 音调随机可复现（只断言边界，不断言具体值）

	# ---- 1. 正常播放：返回 true、同步广播 played、簿记占用 1 ----
	var pool: Node = packed.instantiate()
	root.add_child(pool)
	pool.played.connect(_on_played)
	await physics_frame
	var wav := _make_wav()
	if not pool.play(wav):
		_failures.append("有效 play 应返回 true")
	if _play_count != 1:
		_failures.append("play 应同步广播一次 played，实际 %d" % _play_count)
	if pool.active_count() != 1:
		_failures.append("播放后占用应为 1，实际 %d" % pool.active_count())

	# ---- 2. null 流拒绝：不广播、不占用 ----
	if pool.play(null):
		_failures.append("null stream 应返回 false")
	if _play_count != 1 or pool.active_count() != 1:
		_failures.append("null 播放不应有副作用")

	# ---- 3. 池抢占：pool_size=8 时连续播 9 次，占用恒为 8（最旧被复用） ----
	for i: int in 8:
		pool.play(_make_wav())
	if pool.active_count() != 8:
		_failures.append("播满 8 次后占用应为 8，实际 %d" % pool.active_count())
	pool.play(_make_wav())
	if pool.active_count() != 8:
		_failures.append("第 9 次播放应抢占最旧，占用仍为 8，实际 %d" % pool.active_count())

	# ---- 4. finished 归还：手动触发最旧播放器的 finished，占用降为 7 ----
	# headless 下引擎不触发 finished（playing 恒 false），由测试模拟真实回放完成。
	var players := pool.get_children().filter(
			func(c: Node) -> bool: return c is AudioStreamPlayer)
	if players.size() != 8:
		_failures.append("池应有 8 个 AudioStreamPlayer 子节点，实际 %d" % players.size())
	players[0].finished.emit()
	if pool.active_count() != 7:
		_failures.append("finished 后占用应降为 7，实际 %d" % pool.active_count())
	players[0].finished.emit()  # 重复 finished 不应重复归还
	if pool.active_count() != 7:
		_failures.append("重复 finished 不应再次扣减，实际 %d" % pool.active_count())

	# ---- 5. 音调边界：每次播放的 pitch_scale 都落在 1±pitch_range ----
	for i: int in 20:
		pool.play(_make_wav())
	for p: AudioStreamPlayer in players:
		if p.pitch_scale < 0.9 or p.pitch_scale > 1.1:
			_failures.append("pitch_scale 超界：%s" % str(p.pitch_scale))
			break

	# ---- 6. 导出参数生效：pool_size=3 的池只建 3 个播放器 ----
	var small := packed.instantiate()
	small.pool_size = 3
	small.pitch_range = 0.2
	root.add_child(small)
	await physics_frame
	var small_players := small.get_children().filter(
			func(c: Node) -> bool: return c is AudioStreamPlayer)
	if small_players.size() != 3:
		_failures.append("pool_size=3 应建 3 个播放器，实际 %d" % small_players.size())
	if small.volume_db != 0.0:
		_failures.append("默认 volume_db 应为 0")

	_report()


func _on_played() -> void:
	_play_count += 1


func _make_wav() -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	# 1 秒静音：空数据流可能在音频 mix 线程调度下瞬间 finished（竞态），
	# 会导致占用簿记不确定；1s 远长于测试窗口，簿记确定。
	wav.data = PackedByteArray()
	wav.data.resize(44100)
	wav.format = AudioStreamWAV.FORMAT_8_BITS
	wav.mix_rate = 44100
	return wav


func _report() -> void:
	if _failures.is_empty():
		print("PASS: sfx_pool 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
