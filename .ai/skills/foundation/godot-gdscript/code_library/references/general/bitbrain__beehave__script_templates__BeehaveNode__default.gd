# Source:  https://github.com/bitbrain/beehave/blob/godot-4.x/script_templates/BeehaveNode/default.gd
# Repo:    bitbrain/beehave (star 3312) | License: MIT | Collected: 2026-10-26
# Commit:  fe589153fa78
# meta-name: Default
# meta-default: true
@tool
extends _BASE_


func tick(actor: Node, blackboard: Blackboard) -> int:
	return SUCCESS
