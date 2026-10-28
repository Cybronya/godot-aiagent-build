# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/addons/aimg_io/frame.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  master
@tool
class_name AImgIOFrame
extends RefCounted
# Represents a variable-timed frame of an animation.
# Typically stuffed into an array.

# Content of the frame.
# WARNING: Exporters expect this to be FORMAT_RGBA8.
# This is because otherwise they'd have to copy it or convert it in place.
# Both of those are bad ideas, so thus this.
var content: Image

# Time in seconds this frame lasts for.
var duration: float = 0.1
