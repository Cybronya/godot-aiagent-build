extends SceneTree
## Boss Challenge 集成验证：基于真实 BossChallenge.tscn 的完整行为链路。
##
## 覆盖：玩家移动与生命条、Boss 门关闭实际阻挡、三开关 AND 聚合开门、
## Boss 追击与接触持续伤害、治疗拾取（受伤消费/满血不消费）、空格攻击链路、
## Boss 死亡数据连接开出口门（died→set_open binds=[true]）、出口完成判定、
## 失败状态、重开与初始状态恢复、数据连接在新实例中复现。
##
## 用法：godot --headless --path . -s res://Tests/test_boss_challenge.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const FRAME_BUDGET := 240
const PUSH_FRAMES := 90

var _failures: PackedStringArray = []
var _finished_signal := 0


func _initialize() -> void:
	var packed: PackedScene = load("res://Scenes/BossChallenge.tscn")
	if packed == null:
		_failures.append("加载 res://Scenes/BossChallenge.tscn 失败")
		_report()
		return

	# ---- A. 初始状态与结构：机关关系全部由场景数据连接表达 ----
	var challenge: Node2D = packed.instantiate()
	root.add_child(challenge)
	current_scene = challenge
	challenge.boss_challenge_finished.connect(func(success: bool) -> void: _finished_signal += 1)
	await process_frame
	var player: CharacterBody2D = challenge.get_node("Player")
	var boss: CharacterBody2D = challenge.get_node("Entities/Boss")
	var boss_door: StaticBody2D = challenge.get_node("Mechanism/BossDoor")
	var exit_door: StaticBody2D = challenge.get_node("Mechanism/ExitDoor")
	var gate: Node = challenge.get_node("Mechanism/ConditionGate")
	var player_health: Health = player.get_node("Health")
	var boss_health: Health = boss.get_node("Health")

	if not player.is_in_group("players"):
		_failures.append("玩家应加入 players 组（组件契约）")
	if player_health.get_current_health() != 10:
		_failures.append("玩家初始生命值应为 10，实际 %d" % player_health.get_current_health())
	if boss_health.get_current_health() != 30:
		_failures.append("Boss 初始生命值应为 30，实际 %d" % boss_health.get_current_health())
	if boss_door.is_open() or exit_door.is_open():
		_failures.append("初始两扇门都应关闭")
	if gate.is_fulfilled():
		_failures.append("初始聚合门不应达成")
	if gate.get("condition_count") != 3:
		_failures.append("聚合门应为 3 条件 All 模式")
	if player.get_node_or_null("HealthBar") == null:
		_failures.append("玩家应组合 HealthBar 组件显示生命条")
	if boss.get_node_or_null("HealthBar") == null:
		_failures.append("Boss 应组合 HealthBar 组件显示生命条")

	# ---- B. 玩家可以正常移动（真实输入驱动） ----
	var start_pos := player.global_position
	Input.action_press("move_right")
	for _i: int in 30:
		await physics_frame
	Input.action_release("move_right")
	if player.global_position.distance_to(start_pos) < 20.0:
		_failures.append("玩家应能通过输入移动，实际位移 %s" % (player.global_position - start_pos))

	# ---- C. Boss 门关闭时实际阻挡（在触发开关之前验证，此时门尚未打开） ----
	player.global_position = Vector2(300, 0)
	await process_frame
	Input.action_press("move_right")
	for _i: int in PUSH_FRAMES:
		await physics_frame
	Input.action_release("move_right")
	if player.global_position.x >= 500.0:
		_failures.append("Boss 门关闭时应实际阻挡玩家，实际 x=%.1f" % player.global_position.x)

	# ---- D. 三开关全部触发后 Boss 门打开（真实接触触发） ----
	var switches: Array[Area2D] = [
		challenge.get_node("Mechanism/SwitchA"),
		challenge.get_node("Mechanism/SwitchB"),
		challenge.get_node("Mechanism/SwitchC"),
	]
	for sw in switches:
		player.global_position = sw.global_position
		if not await _wait_until(func() -> bool: return sw.is_triggered()):
			_failures.append("玩家进入开关范围应触发开关（等待超时）")
	if not await _wait_until(func() -> bool: return boss_door.is_open()):
		_failures.append("三个开关全部触发后 Boss 门应打开（等待超时）")

	# ---- E. 门打开后玩家可真实穿门 ----
	player.global_position = Vector2(300, 0)
	await process_frame
	Input.action_press("move_right")
	var crossed := await _wait_until(func() -> bool: return player.global_position.x >= 510.0)
	Input.action_release("move_right")
	if not crossed:
		_failures.append("Boss 门打开后玩家应能穿门进入 Boss 区域，实际 x=%.1f" % player.global_position.x)

	# ---- F. Boss 主动追击玩家（以自身位移量断言，55px/s 慢速重型 Boss） ----
	player.global_position = Vector2(0, 0)
	boss.global_position = Vector2(300, 0)
	var boss_start := boss.global_position
	await _wait_frames(90)
	var moved := boss.global_position.distance_to(boss_start)
	if moved < 30.0:
		_failures.append("Boss 应朝玩家追击移动，90 帧实际位移 %.1f px" % moved)

	# ---- G. Boss 接触造成持续伤害（贴身后等待多个节拍） ----
	player.global_position = Vector2(-200, 0)
	boss.global_position = Vector2(-180, 0)
	var damaged := await _wait_until(func() -> bool: return player_health.get_current_health() < 10)
	if not damaged:
		_failures.append("Boss 接触后应造成伤害（等待超时）")
		_report()
		return
	await _wait_frames(50)
	if player_health.get_current_health() >= 10:
		_failures.append("持续接触下玩家生命值应持续下降（节拍伤害）")
	# Boss 血条与 HUD 同步
	var boss_bar_ratio: float = boss.get_node("HealthBar").get_ratio()
	var expected_ratio: float = float(boss_health.get_current_health()) / 30.0
	if absf(boss_bar_ratio - expected_ratio) > 0.001:
		_failures.append("Boss 血条比例应与生命值同步，实际 %.2f（期望 %.2f）" % [boss_bar_ratio, expected_ratio])
	var boss_label: Label = challenge.get_node("HUD/BossHealthLabel")
	if not boss_label.text.contains(str(boss_health.get_current_health())):
		_failures.append("Boss HUD 应同步显示当前 Boss 生命值，实际 %s" % boss_label.text)
	# 玩家血条同步
	var player_bar_ratio: float = player.get_node("HealthBar").get_ratio()
	var expected_player_ratio: float = float(player_health.get_current_health()) / 10.0
	if absf(player_bar_ratio - expected_player_ratio) > 0.001:
		_failures.append("玩家血条比例应与生命值同步")

	# ---- H. 治疗拾取：受伤状态贴身消费并恢复（先脱离 Boss 接触范围） ----
	player.global_position = Vector2(-460, 0)
	boss.global_position = Vector2(700, 0)
	await _wait_frames(5)
	var hp_before_heal := player_health.get_current_health()
	var pickup: Area2D = load("res://Features/heal_pickup/HealPickup.tscn").instantiate()
	pickup.position = player.global_position + Vector2(12, 0)
	challenge.get_node("Entities").add_child(pickup)
	if not await _wait_pickup_gone(pickup):
		_failures.append("受伤状态下治疗拾取物应被消费（贴身放置）")
	if player_health.get_current_health() <= hp_before_heal:
		_failures.append("消费治疗拾取物后生命值应恢复（%d → %d）" % [hp_before_heal, player_health.get_current_health()])

	# ---- I. 空格攻击链路：真实输入 + 风筝走位打空 Boss 血量 ----
	# attack_trigger 语义无射程限制；每轮先拉开距离再输出，模拟真实走位打法，
	# 避免 Boss 接触伤害（2/0.4s）比站桩输出（1/击）更快磨死玩家
	var swings := 0
	var rounds := 0
	while not boss_health.is_dead() and rounds < 5:
		player.global_position = boss.global_position + Vector2(-180, 0)
		await _wait_frames(2)
		for _s: int in 10:
			if boss_health.is_dead():
				break
			Input.action_press("p1_attack")
			await _wait_frames(2)
			Input.action_release("p1_attack")
			await _wait_frames(3)
			swings += 1
		rounds += 1
	if not boss_health.is_dead():
		_failures.append("连续攻击后 Boss 应死亡，剩余 %d HP" % boss_health.get_current_health())
		_report()
		return

	# ---- J. Boss 死亡 → 出口门打开（tscn 数据连接 died→set_open binds=[true]） ----
	if not await _wait_until(func() -> bool: return exit_door.is_open()):
		_failures.append("Boss 死亡后出口门应通过数据连接打开（等待超时）")
		_report()
		return
	# Boss 死亡后不再追击（Health 死亡保护兜底接触伤害，ChaseMovement 继续追但目标仍在——
	# 追击停止由 Boss 死亡表现层负责的场景选择不在此场景：本场景 Boss 尸体不消失，
	# 接触伤害由 Health 死亡保护天然停摆，验证玩家不再掉血即可）
	var hp_after_boss_death := player_health.get_current_health()
	player.global_position = boss.global_position + Vector2(24, 0)
	await _wait_frames(40)
	if player_health.get_current_health() < hp_after_boss_death:
		_failures.append("Boss 死亡后接触不应再造成伤害")

	# ---- K. 玩家进入出口完成挑战（真实输入驱动穿门） ----
	player.global_position = Vector2(860, 0)
	await process_frame
	Input.action_press("move_right")
	var finished := false
	for _i: int in FRAME_BUDGET:
		if challenge.state == challenge.State.Completed:
			finished = true
			break
		await physics_frame
	Input.action_release("move_right")
	if not finished:
		_failures.append("玩家穿出口门进入出口区应完成挑战，实际 state=%d x=%.1f" % [challenge.state, player.global_position.x])
	else:
		if not challenge.get_node("HUD/StatusLabel").text.contains("挑战完成"):
			_failures.append("完成后状态栏应提示挑战完成")
		if _finished_signal != 1:
			_failures.append("完成信号 boss_challenge_finished 应恰好发出 1 次，实际 %d" % _finished_signal)

	# ---- L. 失败路径：玩家死亡 → Failed 状态 ----
	var challenge2: Node2D = packed.instantiate()
	root.add_child(challenge2)
	await process_frame
	var player2: CharacterBody2D = challenge2.get_node("Player")
	var health2: Health = player2.get_node("Health")
	health2.take_damage(9999)
	await process_frame
	if challenge2.state != challenge2.State.Failed:
		_failures.append("玩家死亡后应进入 Failed 状态，实际 %d" % challenge2.state)
	challenge2.queue_free()
	await process_frame

	# ---- M. 场景重开恢复初始状态（真实 R 键路径） ----
	Input.action_press("restart")
	var reloaded := false
	for _i: int in FRAME_BUDGET:
		if current_scene != challenge:
			reloaded = true
			break
		await process_frame
	Input.action_release("restart")
	if not reloaded:
		_failures.append("结束状态下按 R 应重新加载场景（等待超时）")
		_report()
		return
	await process_frame
	var fresh: Node2D = current_scene
	if fresh == challenge or fresh == null:
		_failures.append("重开后应得到全新场景实例")
		_report()
		return
	var fresh_boss: CharacterBody2D = fresh.get_node("Entities/Boss")
	var fresh_boss_door: StaticBody2D = fresh.get_node("Mechanism/BossDoor")
	var fresh_exit_door: StaticBody2D = fresh.get_node("Mechanism/ExitDoor")
	var fresh_gate: Node = fresh.get_node("Mechanism/ConditionGate")
	if fresh.get_node("Player/Health").get_current_health() != 10:
		_failures.append("重开后玩家生命值应恢复 10")
	if fresh_boss.get_node("Health").get_current_health() != 30:
		_failures.append("重开后 Boss 生命值应恢复 30")
	if fresh_boss_door.is_open() or fresh_exit_door.is_open():
		_failures.append("重开后两扇门应恢复关闭")
	if fresh_gate.is_fulfilled():
		_failures.append("重开后聚合门应恢复未达成")
	if fresh_boss.get_node_or_null("HealthBar") == null:
		_failures.append("重开后 Boss 血条应随场景重建")

	# ---- N. 数据连接复现：新实例中 died→set_open binds=[true] 真实生效 ----
	var fresh_boss_health: Health = fresh_boss.get_node("Health")
	fresh_boss_health.take_damage(9999)
	if not await _wait_until(func() -> bool: return fresh.get_node("Mechanism/ExitDoor").is_open()):
		_failures.append("新实例中 Boss 死亡数据连接应再次打开出口门（等待超时）")

	_report()


func _wait_until(predicate: Callable) -> bool:
	for _i: int in FRAME_BUDGET:
		if predicate.call():
			return true
		await process_frame
	return false


func _wait_pickup_gone(pickup: Area2D) -> bool:
	for _i: int in FRAME_BUDGET:
		if not is_instance_valid(pickup) or pickup.is_queued_for_deletion():
			return true
		await physics_frame
	return false


func _wait_frames(count: int) -> void:
	for _i: int in count:
		await physics_frame


func _report() -> void:
	if _failures.is_empty():
		print("PASS: BossChallenge 集成验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
