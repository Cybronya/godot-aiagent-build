# Source:  https://github.com/MakovWait/godots/blob/main/src/components/asset_lib_projects/scroll_container.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name AssetLibScrollContainer
extends ScrollContainer


func dim() -> void:
	modulate = Color(1, 1, 1, 0.5)


func bright() -> void:
	modulate = Color(1, 1, 1, 1)
