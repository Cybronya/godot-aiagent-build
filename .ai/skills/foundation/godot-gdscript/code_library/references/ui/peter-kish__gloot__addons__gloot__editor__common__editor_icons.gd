# Source:  https://github.com/peter-kish/gloot/blob/master/addons/gloot/editor/common/editor_icons.gd
# Repo:    peter-kish/gloot (star 989) | License: MIT | Collected: 2026-10-29
# Commit:  6b09b87ac07a
@tool

static func get_icon(icon_name: String) -> Texture2D:
    var gui = EditorInterface.get_base_control()
    var icon = gui.get_theme_icon(icon_name, "EditorIcons")
    return icon
