# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/esc/compiler/esc_grammar_stmt.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## Base class that statements must inherit from as part of the "Visitor" pattern.
##
## All inheriting classes must implement an `accept` method to invoke the visitor.
## For more information on the "Visitor" pattern, see:
## (Visitor Pattern)[https://en.wikipedia.org/wiki/Visitor_pattern]
class_name ESCGrammarStmt
extends RefCounted


## Method that invokes another method in the visitor against this, the implementing class.[br]
## [br]
## #### Parameters[br]
## [br]
## | Name | Type | Description | Required? |[br]
## |:-----|:-----|:------------|:----------|[br]
## |visitor|`Variant`|Visitor instance invoked to process this statement.|yes|[br]
## [br]
## #### Returns[br]
## [br]
## Returns nothing.
func accept(_visitor):
	pass
