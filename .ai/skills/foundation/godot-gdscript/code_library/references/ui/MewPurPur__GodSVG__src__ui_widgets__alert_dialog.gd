# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/ui_widgets/alert_dialog.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
extends PanelContainer

@onready var title: Label = $MainContainer/TextContainer/Title
@onready var label: RichTextLabel = $MainContainer/TextContainer/Label
@onready var ok_button: Button = $MainContainer/OKButton

func _ready() -> void:
	ok_button.pressed.connect(queue_free)
	HandlerGUI.register_focus_sequence(self, [ok_button])
	ok_button.grab_focus()

func setup(message: String) -> void:
	label.text = message
	title.text = Translator.translate("Alert!")
	ok_button.text = Translator.translate("OK")
	label.custom_minimum_size.x = 280.0
