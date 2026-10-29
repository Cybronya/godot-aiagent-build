# Source:  https://github.com/foxssake/netfox/blob/main/addons/vest/test/mixins/logging-mixin.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends VestTestMixin

# Manages logs added using [method Vest.message]

func _init():
	super()

	on_case_finish.connect(func(_case):
		var messages := Vest._get_messages()
		if not messages.is_empty():
			_result.data["messages"] = messages
		Vest._clear_messages()
	)
