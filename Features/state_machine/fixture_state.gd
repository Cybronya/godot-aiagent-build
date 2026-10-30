class_name FixtureState
extends StateNode
## state_machine 行为夹具状态：纯占位状态节点，验证状态机的注册/切换/回退行为。

var visit_count := 0


func enter() -> void:
	visit_count += 1
