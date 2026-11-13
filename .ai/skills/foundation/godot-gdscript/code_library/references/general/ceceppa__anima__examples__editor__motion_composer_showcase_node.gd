# Source:  https://github.com/ceceppa/anima/blob/main/examples/editor/motion_composer_showcase_node.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
## A plain node exposing an [AnimaMotion] field so the Motion Composer's
## Inspector entry point can open it directly (`tech-spec.md` §Motion Composer
## entry point) — used by the Motion Composer showcase scene
## (`project-rules.md` §Example Scenes). Not a shared example component: each
## showcase node only demonstrates one Motion Composer state.
extends Node

## The motion this showcase node demonstrates. Leave empty to demonstrate the
## Motion Composer's top-level empty state instead.
@export var motion: AnimaMotion
