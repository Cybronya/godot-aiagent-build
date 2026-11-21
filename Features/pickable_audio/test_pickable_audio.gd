extends SceneTree
## InteractionAudio3D 组件验证：音效设置、交互触发、速度衰减。
## 用法：godot --headless --path . -s res://Features/pickable_audio/test_pickable_audio.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []


func _initialize() -> void:
	var audio := InteractionAudio3D.new()
	root.add_child(audio)
	await physics_frame

	var wav := _make_wav()

	# ---- 1. 初始无流 ----
	if audio.stream != null:
		_failures.append("初始 stream 应为 null")

	# ---- 2. on_picked_up 设置 grab_sound ----
	audio.grab_sound = wav
	audio.on_picked_up()
	if audio.stream != wav:
		_failures.append("on_picked_up 后 stream 应为 grab_sound")

	# ---- 3. on_body_entered 设置 drop_sound（未拿起） ----
	audio.drop_sound = wav
	audio.on_body_entered(null)
	if audio.stream != wav:
		_failures.append("on_body_entered 后 stream 应已设置")

	# ---- 4. 高速 → 音量 0 ----
	audio.move_velocity = Vector3(0, 10, 0)
	audio.volume_db = -10.0
	audio._physics_process(0.1)
	if audio.volume_db != 0.0:
		_failures.append("高速(>5)应音量=0，实际 %.2f" % audio.volume_db)

	# ---- 5. 低速 → 音量衰减 ----
	audio.move_velocity = Vector3(0, 1, 0)
	audio.volume_db = 0.0
	audio._physics_process(0.1)
	if not is_equal_approx(audio.volume_db, -0.1):
		_failures.append("低速应衰减约 -0.1，实际 %.4f" % audio.volume_db)

	# ---- 6. on_dropped 停止播放 ----
	audio.on_dropped()
	if audio.playing:
		_failures.append("on_dropped 后应停止播放")

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
		print("PASS: pickable_audio 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
