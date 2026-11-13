# Source:  https://github.com/MakovWait/godots/blob/main/src/components/asset_lib_projects/filter_edit.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends LineEdit

signal changed

## seconds
@export var _debounce_time := 0.25


func _init() -> void:
	var debounce_timer := Timer.new()
	add_child(debounce_timer)
	debounce_timer.one_shot = true
	debounce_timer.timeout.connect(func() -> void: changed.emit())
	text_changed.connect(func(_new_text: String) -> void:
		debounce_timer.start(_debounce_time)
	)


func fill_params(params: AssetLib.Params) -> void:
	params.filter_raw = text


func _on_fetch_disable() -> void:
	editable = false


func _on_fetch_enable() -> void:
	editable = true
