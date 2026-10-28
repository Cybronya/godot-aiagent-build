# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/ui_widgets/element_content_radial_gradient.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
extends VBoxContainer

@onready var attribute_container: HFlowContainer = $AttributeContainer

var element: Element

func _ready() -> void:
	for attribute in DB.get_recognized_attributes("radialGradient"):
		var input_field := AttributeFieldBuilder.create(attribute, element)
		input_field.focus_entered.connect(State.normal_select.bind(element.xid))
		attribute_container.add_child(input_field)
