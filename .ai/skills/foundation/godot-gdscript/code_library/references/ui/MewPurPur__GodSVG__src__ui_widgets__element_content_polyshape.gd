# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/ui_widgets/element_content_polyshape.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
extends VBoxContainer

@onready var attribute_container: HFlowContainer = $AttributeContainer
@onready var points_field: VBoxContainer = $PointsField

var element: Element

func _ready() -> void:
	points_field.element = element
	points_field.setup()
	points_field.focused.connect(State.normal_select.bind(element.xid))
	
	for attribute in DB.get_recognized_attributes(element.name):
		if attribute == "points":
			continue
		var input_field := AttributeFieldBuilder.create(attribute, element)
		# Focused signal for pathdata attribute.
		input_field.focus_entered.connect(State.normal_select.bind(element.xid))
		attribute_container.add_child(input_field)
