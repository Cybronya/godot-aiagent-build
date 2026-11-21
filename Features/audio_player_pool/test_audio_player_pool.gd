extends SceneTree
## AudioPlayerPool 组件验证：池创建、prepare/play、动态扩容、归还、淡入淡出。
## 用法：godot --headless --path . -s res://Features/audio_player_pool/test_audio_player_pool.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var pool := AudioPlayerPool.new()
	pool.default_pool_size = 4
	pool.max_pool_size = 8
	root.add_child(pool)
	await physics_frame

	# ---- 1. 池创建：4 个可用播放器 ----
	if pool.get_available_count() != 4:
		_failures.append("池应创建 4 个可用播放器，实际 %d" % pool.get_available_count())

	# ---- 2. prepare() 返回播放器并标记忙碌 ----
	var wav := _make_wav()
	var p1 := pool.prepare(wav)
	if p1 == null:
		_failures.append("prepare 应返回播放器")
	else:
		if pool.get_busy_count() != 1:
			_failures.append("prepare 后忙碌应为 1，实际 %d" % pool.get_busy_count())
		if pool.get_available_count() != 3:
			_failures.append("prepare 后可用应为 3，实际 %d" % pool.get_available_count())
		if p1.stream != wav:
			_failures.append("prepare 后 stream 应已装载")

	# ---- 3. play() 快捷播放 ----
	var p2 := pool.play(_make_wav())
	if p2 == null:
		_failures.append("play 应返回播放器")
	elif pool.get_busy_count() != 2:
		_failures.append("play 后忙碌应为 2，实际 %d" % pool.get_busy_count())

	# ---- 4. prepare(null) 返回 null ----
	if pool.prepare(null) != null:
		_failures.append("prepare(null) 应返回 null")

	# ---- 5. 池满后自动扩容 ----
	for i: int in 2:
		pool.prepare(_make_wav())
	if pool.get_busy_count() != 4:
		_failures.append("应忙碌 4，实际 %d" % pool.get_busy_count())
	var p5 := pool.prepare(_make_wav())
	if p5 == null:
		_failures.append("第 5 次 prepare 应扩容成功")
	elif pool.get_busy_count() != 5:
		_failures.append("扩容后忙碌应为 5，实际 %d" % pool.get_busy_count())

	# ---- 6. 归还后可用恢复 ----
	pool._mark_available(p1)
	if pool.get_busy_count() != 4:
		_failures.append("归还后忙碌应为 4，实际 %d" % pool.get_busy_count())
	if pool.get_available_count() != 1:
		_failures.append("归还后可用应为 1，实际 %d" % pool.get_available_count())

	# ---- 7. fade_volume 不崩溃 ----
	pool.fade_volume(p5, 0.0, -12.0, 0.1)
	if p5.volume_db != 0.0:
		_failures.append("fade_volume 起始应设 from_db，实际 %.1f" % p5.volume_db)

	_report()


func _make_wav() -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	wav.data = PackedByteArray()
	wav.data.resize(480000)
	wav.format = AudioStreamWAV.FORMAT_8_BITS
	wav.mix_rate = 8000
	return wav


func _report() -> void:
	if _failures.is_empty():
		print("PASS: audio_player_pool 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
