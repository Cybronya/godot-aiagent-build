# Source:  https://github.com/don-tnowe/godot-resources-as-sheets-plugin/blob/master/addons/resources_spreadsheet_view/import_export/property_list_item.gd
# Repo:    don-tnowe/godot-resources-as-sheets-plugin (star 1031) | License: MIT | Collected: 2026-10-29
# Commit:  3363e0d2136c
@tool
extends HBoxContainer


func display(name : String, type : int):
  $"LineEdit".text = name
  $"OptionButton".selected = type


func connect_all_signals(to : Object, index : int, prefix : String = "_on_list_item_"):
  $"LineEdit".text_changed.connect(Callable(to, prefix + "name_changed").bind(index))
  $"OptionButton".item_selected.connect(Callable(to, prefix + "type_selected").bind(index))
