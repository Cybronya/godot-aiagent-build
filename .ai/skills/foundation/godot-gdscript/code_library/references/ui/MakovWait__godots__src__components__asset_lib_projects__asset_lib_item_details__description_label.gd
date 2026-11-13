# Source:  https://github.com/MakovWait/godots/blob/main/src/components/asset_lib_projects/asset_lib_item_details/description_label.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name AssetLibDetailsDescriptionLabel
extends RichTextLabel



func _ready() -> void:
	meta_clicked.connect(func(meta: Variant) -> void:
		OS.shell_open(str(meta))
	)


func configure(item: AssetLib.Item) -> void:
	clear()
	add_text(tr("Version:") + " " + item.version_string + "\n")
	add_text(tr("Contents:") + " ")
	push_meta(item.browse_url)
	add_text(tr("View Files"))
	pop()
	add_text("\n" + tr("Description:") + "\n\n")
	append_text(item.description)
	set_selection_enabled(true)
	set_context_menu_enabled(true)
