# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/src/UI/Buttons/PatternButton.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  fae9327992f1
extends BaseButton

var pattern = Global.patterns_popup.Pattern.new()


func _on_PatternButton_pressed() -> void:
	Global.patterns_popup.select_pattern(pattern)
