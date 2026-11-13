# Source:  https://github.com/MakovWait/godots/blob/main/src/components/godots_releases/list/godots_releases_list.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends VBoxList


signal download_and_install_requested(url: String)


func _post_add(item_data: Object, raw_item_control: Control) -> void:
	var item_control: GodotsReleasesListItemControl = raw_item_control
	item_control.download_and_install_requested.connect(func(url: String) -> void: 
		download_and_install_requested.emit(url)
	)


func _item_comparator(a: Dictionary, b: Dictionary) -> bool:
	return true


func _fill_sort_options(btn: OptionButton) -> void:
	pass
