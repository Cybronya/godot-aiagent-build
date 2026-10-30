# Source:  https://github.com/V-Sekai/unidot_importer/blob/main/raw_parsed_asset.gd
# Repo:    V-Sekai/unidot_importer (star 979) | License: MIT | Collected: 2026-10-29
# Commit:  9719eaa2c5ac
# This file is part of Unidot Importer. See LICENSE.txt for full MIT license.
# Copyright (c) 2021-present Lyuma <xn.lyuma@gmail.com> and contributors
# SPDX-License-Identifier: MIT
@tool
extends Resource

@export var path: String = ""
@export var guid: String = ""
@export var objects: Dictionary = {}
@export var meta: Resource = null
