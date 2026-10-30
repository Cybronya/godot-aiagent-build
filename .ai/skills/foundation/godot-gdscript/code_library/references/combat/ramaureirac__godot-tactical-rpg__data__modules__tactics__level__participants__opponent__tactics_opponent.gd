# Source:  https://github.com/ramaureirac/godot-tactical-rpg/blob/development/data/modules/tactics/level/participants/opponent/tactics_opponent.gd
# Repo:    ramaureirac/godot-tactical-rpg (star 978) | License: MIT | Collected: 2026-10-29
# Commit:  cfe785e5b6f8
class_name TacticsOpponent
extends TacticsParticipant
## Handles opponent AI actions and decision-making
## 
## Service: [TacticsOpponentService]

## Service handling opponent-specific logic and operations
var opponent_serv: TacticsOpponentService


## Initializes the TacticsOpponent node
func _ready() -> void:
	super._ready() # Call the parent's _ready function
	opponent_serv = TacticsOpponentService.new(res, camera, controls, arena) # Initialize the opponent service


## Checks if the opponent's pawn is properly configured
##
## @return: Whether the pawn is configured
func is_pawn_configured() -> bool:
	return opponent_serv.is_pawn_configured(self) # Delegate to the service


## Chooses a pawn for the opponent to act with
func choose_pawn() -> void:
	opponent_serv.choose_pawn(self) # Delegate to the service


## Initiates the action of chasing the nearest enemy
func chase_nearest_enemy() -> void:
	opponent_serv.chase_nearest_enemy(self, get_node("../TacticsPlayer")) # Delegate to the service


## Checks if the opponent's pawn has finished moving
func is_pawn_done_moving() -> void:
	opponent_serv.is_pawn_done_moving() # Delegate to the service


## Chooses a pawn for the opponent to attack
func choose_pawn_to_attack() -> void:
	opponent_serv.choose_pawn_to_attack() # Delegate to the service
