extends SceneTree
## PedestalInteraction 组件验证：放置/移除、正确性追踪、谜题组全对触发。
## 用法：godot --headless --path . -s res://Features/pedestal_interaction/test_pedestal_interaction.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

var _failures: PackedStringArray = []
var _solved_count: int = 0


func _initialize() -> void:
	var p1 := PedestalInteraction.new()
	p1.expected_item_id = 1
	var p2 := PedestalInteraction.new()
	p2.expected_item_id = 2
	var p3 := PedestalInteraction.new()
	p3.expected_item_id = 3

	root.add_child(p1)
	root.add_child(p2)
	root.add_child(p3)
	await physics_frame

	# 连接 puzzle_solved 信号（任一成员发射）
	p1.puzzle_solved.connect(_on_puzzle_solved)
	p2.puzzle_solved.connect(_on_puzzle_solved)
	p3.puzzle_solved.connect(_on_puzzle_solved)

	# ---- 1. 初始状态：无物品，不正确 ----
	if p1.is_correct():
		_failures.append("初始状态应不正确")
	if p1.current_item_id != -1:
		_failures.append("初始 current_item_id 应为 -1")

	# ---- 2. 放置正确物品 → 正确 ----
	p1.place_item(1)
	if not p1.is_correct():
		_failures.append("放置正确物品(1)后应正确")

	# ---- 3. 放置错误物品 → 不正确 ----
	p2.place_item(1)  # 期望 2，放置 1
	if p2.is_correct():
		_failures.append("放置错误物品(1)期望(2)后应不正确")

	# ---- 4. 移除物品 → 不正确 ----
	p1.remove_item()
	if p1.is_correct():
		_failures.append("移除后应不正确")
	# 重新放置
	p1.place_item(1)

	# ---- 5. 加入谜题组 ----
	p1.join_puzzle_group("test_puzzle")
	p2.join_puzzle_group("test_puzzle")
	p3.join_puzzle_group("test_puzzle")

	# ---- 6. 不全对 → 不触发 ----
	if _solved_count != 0:
		_failures.append("不全对不应触发 puzzle_solved")

	# ---- 7. 全部正确 → 触发 ----
	p2.place_item(2)
	p3.place_item(3)
	if _solved_count == 0:
		_failures.append("全部正确应触发 puzzle_solved")

	# ---- 8. 谜题解决后 is_active = false ----
	if p1.is_active:
		_failures.append("谜题解决后 p1.is_active 应为 false")
	if p2.is_active:
		_failures.append("谜题解决后 p2.is_active 应为 false")
	if p3.is_active:
		_failures.append("谜题解决后 p3.is_active 应为 false")

	_report()


func _on_puzzle_solved() -> void:
	_solved_count += 1


func _report() -> void:
	if _failures.is_empty():
		print("PASS: pedestal_interaction 全部检查通过")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		quit(1)
