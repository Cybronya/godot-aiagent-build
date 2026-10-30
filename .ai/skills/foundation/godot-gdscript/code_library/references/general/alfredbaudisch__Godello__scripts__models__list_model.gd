# Source:  https://github.com/alfredbaudisch/Godello/blob/master/scripts/models/list_model.gd
# Repo:    alfredbaudisch/Godello (star 890) | License: MIT | Collected: 2026-10-29
# Commit:  4458a143644f
class_name ListModel extends Model


var title : String = ""
var cards : Array = []
var cards_by_id : Dictionary = {}
var board_id : String = ""


func _init(_id : String, _board_id : String, _title : String, _cards : Array = []).(ModelTypes.LIST, _id):
	title = _title
	board_id = _board_id
	cards = _cards
	_map_cards_by_id()


func set_title(_title : String):
	title = _title
	_notify_updated()


func add_card(card):
	if not cards_by_id.get(card.id):
		card.list_id = id
		cards.append(card)
		cards_by_id[card.id] = card


func remove_cards():
	cards_by_id.clear()
	cards.clear()


func remove_card(card):
	var card_idx = cards.find(card)
	if card_idx != -1:
		cards.remove(card_idx)

	if !cards_by_id.erase(card.id):
		print("list_model.gd:39 : card with id %d not found" % card.id)


func _map_cards_by_id():
	for card in cards:
		cards_by_id[card.id] = card


func _notify_updated():
	DataRepository.update_list(self)
