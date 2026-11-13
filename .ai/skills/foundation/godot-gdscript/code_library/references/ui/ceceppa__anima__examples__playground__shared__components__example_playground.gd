# Source:  https://github.com/ceceppa/anima/blob/main/examples/playground/shared/components/example_playground.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
class_name ExamplePlayground
extends Control

## Shared root for runnable Anima playground scenes.
##
## It makes a running example use the same readable content scale as the
## operating system display, via the standalone [HiDPIScale] add-on, and
## wires any [ExampleHeader] descendant's back button to the Demo Selector.
## Playground-specific scripts should call [method _ready] on this base
## class instead of copying display setup.

const DEMO_SELECTOR_SCENE := "res://examples/demo_selector.tscn"

func _ready() -> void:
	HiDPIScale.apply_to(self)

	for header in find_children("*", "ExampleHeader", true, false):
		header.back_pressed.connect(_on_header_back_pressed)

func _on_header_back_pressed() -> void:
	get_tree().change_scene_to_file(DEMO_SELECTOR_SCENE)
