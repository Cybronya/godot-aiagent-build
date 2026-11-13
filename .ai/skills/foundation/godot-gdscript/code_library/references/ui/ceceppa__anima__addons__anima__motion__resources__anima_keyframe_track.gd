# Source:  https://github.com/ceceppa/anima/blob/main/addons/anima/motion/resources/anima_keyframe_track.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
## One animated property's canonical, offset-sorted list of keyframe stops.
##
## Never constructed by hand in ordinary authoring; [AnimaKeyframeMotion]
## builds and owns these while parsing an authored keyframe declaration.
class_name AnimaKeyframeTrack
extends Resource

## The property this track animates, already resolved to its canonical path —
## a semantic declaration like `opacity` resolves to `modulate:a` here.
@export var property_path: NodePath = NodePath()
## This track's stops. Always kept sorted by [member AnimaKeyframeStop.offset]
## after every merge, regardless of the order they were declared in.
@export var stops: Array[AnimaKeyframeStop] = []
