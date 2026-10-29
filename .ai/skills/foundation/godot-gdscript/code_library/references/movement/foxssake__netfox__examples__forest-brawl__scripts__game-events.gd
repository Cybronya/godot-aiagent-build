# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/game-events.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Node
# Only used for Forest Brawl example

signal on_brawler_spawn(brawler: BrawlerController)
signal on_own_brawler_spawn(brawler: BrawlerController)
signal on_brawler_fall(brawler: BrawlerController)
signal on_brawler_respawn(brawler: BrawlerController)
signal on_brawler_despawn(brawler: BrawlerController)

signal on_scores_updated(scores: Dictionary)
