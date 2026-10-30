# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/items/weapons/gun.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
class_name Gun extends Weapon

## Gun base class, any guns should be an inherited scene from Gun.tscn

@onready var muzzle_smoke = $MuzzleSmoke
@onready var muzzle_flash = $MuzzleFlash

func attack():
	muzzle_flash.flash()
	muzzle_smoke.start_smoke()
	super()
