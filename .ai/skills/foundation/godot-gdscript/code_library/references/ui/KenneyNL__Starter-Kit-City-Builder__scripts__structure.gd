# Source:  https://github.com/KenneyNL/Starter-Kit-City-Builder/blob/main/scripts/structure.gd
# Repo:    KenneyNL/Starter-Kit-City-Builder (star 1495) | License: MIT | Collected: 2026-10-26
# Commit:  4535092b740b
extends Resource
class_name Structure

@export_subgroup("Model")
@export var model:PackedScene # Model of the structure

@export_subgroup("Gameplay")
@export var price:int # Price of the structure when building
