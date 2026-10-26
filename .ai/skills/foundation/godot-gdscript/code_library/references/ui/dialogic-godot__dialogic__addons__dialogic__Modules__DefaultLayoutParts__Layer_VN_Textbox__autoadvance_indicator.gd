# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/DefaultLayoutParts/Layer_VN_Textbox/autoadvance_indicator.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends Range

var enabled: bool = true

func _process(_delta : float) -> void:
	if !enabled:
		hide()
		return
	if DialogicUtil.autoload().Inputs.auto_advance.get_progress() < 0:
		hide()
	else:
		show()
		value = DialogicUtil.autoload().Inputs.auto_advance.get_progress()
