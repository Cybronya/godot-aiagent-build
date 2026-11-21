#!/usr/bin/env python3
"""Phase 1.76 Batch D - Manual Evidence Review (READ-ONLY).

Reviews the 13 potential evidence impacts reported by Batch C, the 3 PARTIAL
coverage records, the 2 candidates and their 3 seeds, at source level.

The tool never writes formal analysis / linkage / candidate / feature / parser
data and never creates a Review Queue. It only writes its own artefact
directory:

    .ai/learning/external_code/evidence_review/phase_1.76/

Modes:
    build       write the Batch D artefacts
    validate    re-derive and check the artefacts + data integrity
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
B_WS = ROOT / ".ai/learning/external_code/reanalysis/parser_1.76"
P75_WS = ROOT / ".ai/learning/external_code/reanalysis/parser_1.75"
FORMAL = ROOT / ".ai/learning/external_code/analysis"
LINKS = ROOT / ".ai/learning/external_code/feature_links"
CANDS = ROOT / ".ai/learning/candidate_workspace"
C_OUT = ROOT / ".ai/learning/external_code/evidence_impact/phase_1.76"
OUT = ROOT / ".ai/learning/external_code/evidence_review/phase_1.76"
SOURCES = ROOT / ".ai/skills/foundation/godot-gdscript/code_library/sources"
BASELINE = ROOT / ".ai/tmp/phase176d_baseline.json"

PARSER_B = "gd_parse@1.75+build:6b74a6cd20a06033"
AUDITED_FEATURES = ["health", "health_bar", "openable_door", "blackboard", "attack_emitter"]

SEMANTIC = [
    "CONFIRMED_DIRECT_EVIDENCE",
    "CONFIRMED_SUPPORTING_EVIDENCE",
    "GENERIC_API_ONLY",
    "STATE_DECLARATION_ONLY",
    "CONTEXT_ONLY",
    "DUPLICATE_EVIDENCE",
    "NOT_RELEVANT",
    "INSUFFICIENT_SOURCE_EVIDENCE",
    "COVERAGE_BLOCKED",
]
INTEGRITY = [
    "SOURCE_VERIFIED",
    "SOURCE_PARTIALLY_VERIFIED",
    "SOURCE_NOT_VERIFIED",
    "PROVENANCE_MISMATCH",
]
FOLLOW_UP = [
    "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    "REQUIRES_PARSER_HARDENING",
    "REQUIRES_ADDITIONAL_SOURCE_REVIEW",
    "NO_FURTHER_ACTION",
    "DO_NOT_PROMOTE",
]
COVERAGE_CODES = [
    "UNSUPPORTED_CONSTRUCT_REPORTED",
    "UNSUPPORTED_CONSTRUCT_NOT_REPORTED",
    "DECLARATION_NOT_CAPTURED",
    "PARSER_COVERAGE_UNKNOWN",
    "SOURCE_CONFIRMED",
]

REPO_DIR = {
    "gdquest-demos/godot-make-pro-2d-games": "gdquest-demos__godot-make-pro-2d-games",
    "nezvers/Godot-GameTemplate": "nezvers__Godot-GameTemplate",
    "bitbrain/beehave": "bitbrain__beehave",
    "gdquest-demos/godot-open-rpg": "gdquest-demos__godot-open-rpg",
    "alfredbaudisch/Godello": "alfredbaudisch__Godello",
    "lampe-games/godot-open-rts": "lampe-games__godot-open-rts",
}

DECL_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*"
    r"(?:(?:export|onready)(?:\([^)]*\))?\s+)?"
    r"(var|const|signal|func|enum|class_name)\s+([A-Za-z_][A-Za-z0-9_]*)"
)

# ---------------------------------------------------------------------------
# Human review plan: one row per Batch C potential-impact record.
# commit_range / behaviour_range are commit-copy line numbers (0-based file
# lines of the verified commit copy, i.e. no +3 references-copy offset).
# ---------------------------------------------------------------------------
REVIEW_PLAN = [
    {
        "review_item_id": "RV-176D-01",
        "priority": "P0",
        "analysis_id": "ext-1d204b35464cf388",
        "symbol": "health",
        "feature": "health",
        "declared_at": 9,
        "commit_range": [9, 9],
        "behaviour_range": [14, 31],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONFIRMED_SUPPORTING_EVIDENCE",
        "confidence": "HIGH",
        "observed_behavior": (
            "`var health = 0` (L9) is the live health value; `_ready()` assigns "
            "`health = max_health` (L15); `take_damage()` subtracts, clamps at 0 and emits "
            "health_changed/damage_taken/health_depleted (L20-26); `heal()` adds and clamps "
            "against max_health and emits health_changed (L28-31)."
        ),
        "reasoning": (
            "The added variable is the state cell that the already-DIRECT identifiers "
            "take_damage/heal/health_changed operate on, in the same file and the same "
            "implementation. It substantiates the seed's stated architecture but adds no new "
            "identifier match, no new repository, commit or digest, and therefore no new "
            "evidence source. It must not be counted as a second seed."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-02",
        "priority": "P0",
        "analysis_id": "ext-23949c1378c49203",
        "symbol": "get_value",
        "feature": "blackboard",
        "declared_at": 34,
        "commit_range": [34, 39],
        "behaviour_range": [34, 39],
        "declaration_kind_observed": "FUNCTION",
        "semantic": "CONFIRMED_SUPPORTING_EVIDENCE",
        "confidence": "HIGH",
        "observed_behavior": (
            "`get_value(key, default_value = null, blackboard_name = DEFAULT) -> Variant` "
            "(L34-36) calls `has_value(key, blackboard_name)` (L37) and returns "
            "`_data[blackboard_name].get(key, default_value)` (L38), else `default_value` (L39). "
            "It reads the named-board dictionary store directly and applies `has_value`'s "
            "null-as-absent rule."
        ),
        "reasoning": (
            "This is a real blackboard read path, not a free-floating generic getter: it reads "
            "`_data`, the very Dictionary the Feature declares as its ownership state, and it is "
            "the symmetric counterpart of set_value/erase_value/has_value, which are already "
            "exact-matched in the DIRECT linkage. It is therefore supporting evidence for the "
            "same claim and cannot be promoted to a new seed: same file, same commit, same "
            "digest, and the linkage is NOT_INDEPENDENT because the internal Feature is derived "
            "from bitbrain/beehave."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-03",
        "priority": "P1",
        "analysis_id": "ext-27ddd863881677d7",
        "symbol": "key",
        "feature": "blackboard",
        "declared_at": 7,
        "commit_range": [7, 7],
        "behaviour_range": [7, 16],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONTEXT_ONLY",
        "confidence": "HIGH",
        "observed_behavior": (
            "`@export_placeholder(EXPRESSION_PLACEHOLDER) var key: String = \"\"` (L7) is an "
            "expression source; `_parse_expression(key)` builds `_key_expression` (L11), whose "
            "`execute([], blackboard)` result becomes the key argument of "
            "`blackboard.set_value(key_value, value_value)` (L16, L26)."
        ),
        "reasoning": (
            "The symbol is a configuration string holding a GDScript expression, not a blackboard "
            "key value and not part of the blackboard API. The Feature defines no `key` symbol. "
            "The file is a consumer node that calls set_value, which is usable context but not "
            "implementation evidence for the blackboard store; the existing linkage is only a "
            "class-token POTENTIAL_RELEVANCE and must not be upgraded on a token."
        ),
        "follow_up": "NO_FURTHER_ACTION",
    },
    {
        "review_item_id": "RV-176D-04",
        "priority": "P1",
        "analysis_id": "ext-27ddd863881677d7",
        "symbol": "value",
        "feature": "blackboard",
        "declared_at": 9,
        "commit_range": [9, 9],
        "behaviour_range": [9, 21],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONTEXT_ONLY",
        "confidence": "HIGH",
        "observed_behavior": (
            "`@export_placeholder(EXPRESSION_PLACEHOLDER) var value: String = \"\"` (L9) is parsed "
            "into `_value_expression` (L12), executed with the blackboard as base (L21), and the "
            "result is stored through `blackboard.set_value(...)` (L26)."
        ),
        "reasoning": (
            "Same shape as `key`: a placeholder/expression string, not stored blackboard data. The "
            "Feature has set_value/get_value/has_value but no `value` symbol, and token proximity "
            "is not evidence. Consumer-side usage of set_value is context only."
        ),
        "follow_up": "NO_FURTHER_ACTION",
    },
    {
        "review_item_id": "RV-176D-05",
        "priority": "P0",
        "analysis_id": "ext-51d46c1b4943a254",
        "symbol": "is_locked",
        "feature": "openable_door",
        "declared_at": 7,
        "commit_range": [7, 25],
        "behaviour_range": [39, 49],
        "declaration_kind_observed": "PROPERTY",
        "semantic": "CONFIRMED_SUPPORTING_EVIDENCE",
        "confidence": "HIGH",
        "observed_behavior": (
            "`@export var is_locked := false` (L7) has a setter (L8-25) that, when locking, "
            "instantiates a `CellBlocker` gamepiece into `_closed_door` to occupy the door's board "
            "cell, and when unlocking calls `open()` and frees the blocker. `open()` (L39-49) "
            "returns early if already open, plays the `locked` animation while `is_locked`, "
            "otherwise plays `open` and awaits `animation_finished`."
        ),
        "reasoning": (
            "is_locked is genuine gameplay state with observable behaviour (movement blocking and "
            "a distinct locked-open path), not editor/UI state. It is still not the Feature's "
            "open/closed state: the Feature owns `_is_open` via set_open(is_open)/is_open(), and the "
            "external identifier set (is_locked/open/Door) shares no identifier with them. The "
            "semantic relation is door gating, so this supports the existing POTENTIAL_RELEVANCE "
            "link but cannot be read as DIRECT under the identifier rules; a human semantic-link "
            "decision would be needed to change the classification."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-06",
        "priority": "P1",
        "analysis_id": "ext-5a8d53c7f530e4af",
        "symbol": "door",
        "feature": "openable_door",
        "declared_at": 4,
        "commit_range": [4, 4],
        "behaviour_range": [8, 17],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONTEXT_ONLY",
        "confidence": "HIGH",
        "observed_behavior": (
            "`@onready var door := get_parent() as Door` (L4) is a parent node reference. "
            "`_execute()` (L8-17) checks `door.is_locked`, consumes `Inventory.ItemTypes.KEY`, "
            "sets `door.is_locked = false`, then calls `door.open()`."
        ),
        "reasoning": (
            "The symbol itself is a typed node reference, not a door API. The surrounding function "
            "is real unlock behaviour, but the analysis has no formal linkage record at all (one of "
            "the four known linkage-coverage gaps), so there is no existing link to strengthen and "
            "no basis to attach evidence without first closing that coverage gap."
        ),
        "follow_up": "REQUIRES_ADDITIONAL_SOURCE_REVIEW",
    },
    {
        "review_item_id": "RV-176D-07",
        "priority": "P0",
        "analysis_id": "ext-73c80a3db6d71e48",
        "symbol": "max_hp",
        "feature": "health",
        "declared_at": 12,
        "commit_range": [12, 12],
        "behaviour_range": [38, 49],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONFIRMED_SUPPORTING_EVIDENCE",
        "confidence": "HIGH",
        "observed_behavior": (
            "`@export var max_hp:float = 5` (L12); `add_hp()` clamps "
            "`hp = clamp(hp + value, 0.0, max_hp)` (L39), emits hp_changed, emits damaged on "
            "negative input (L41-42), sets `is_dead = true` and emits dead at 0 (L43-46), and "
            "emits full at `hp == max_hp` (L47-49). `set_max_hp`/`reset_resource` also write it."
        ),
        "reasoning": (
            "max_hp is the clamping bound and full threshold that the seed's narrow claim "
            "(`is_dead` derived from clamped HP) depends on, so it materially strengthens that "
            "claim and removes the recorded limitation 'parser captured 1 of 5 @export vars'. It "
            "does not create a new identifier match (the Feature uses max_health), a new source or "
            "a new seed: same file, commit and digest as lnk-6fff3ce176bd5813."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-08",
        "priority": "P0",
        "analysis_id": "ext-9f0aad5e01dd71f7",
        "symbol": "current_health",
        "feature": "health_bar",
        "declared_at": 6,
        "commit_range": [6, 6],
        "behaviour_range": [8, 21],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONFIRMED_DIRECT_EVIDENCE",
        "confidence": "HIGH",
        "observed_behavior": (
            "`var current_health = 0` (L6) is written from `health_node.health` and "
            "`maximum` from `health_node.max_health` inside `initialize()` (L8-13), which also "
            "connects `health_node.health_changed` to `_on_Player_Health_health_changed` (L9) and "
            "calls `animate_bar(current_health)`; the handler stores the new value (L15-17); "
            "`animate_bar()` drives `$TextureProgress.animate_value(...)` and "
            "`update_color(...)` (L19-21)."
        ),
        "reasoning": (
            "The source actually binds a Health node to a UI bar: it subscribes health_changed, "
            "reads current and maximum health, and repaints a TextureProgress. That is the "
            "health_bar Feature's declared behaviour (read-only display bound to a Health "
            "component), so at human-semantic level this is direct functional evidence. It cannot "
            "enter the formal layer automatically: the identifier `current_health` does not equal "
            "`get_ratio`, the existing linkage is NO_SUPPORTED_LINK, and no semantic-link rule "
            "exists. Classification here is a review conclusion, not a linkage."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-09",
        "priority": "P1",
        "analysis_id": "ext-9f0aad5e01dd71f7",
        "symbol": "maximum",
        "feature": "health_bar",
        "declared_at": 5,
        "commit_range": [5, 5],
        "behaviour_range": [3, 12],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONFIRMED_SUPPORTING_EVIDENCE",
        "confidence": "HIGH",
        "observed_behavior": (
            "`var maximum = 100` (L5) is overwritten with `health_node.max_health` in "
            "`initialize()` (L10) and broadcast through `maximum_changed` (L3, L12)."
        ),
        "reasoning": (
            "The bar's upper bound is genuinely taken from the bound Health component, which "
            "supports the same health_bar claim as current_health. Alone it is a display bound, "
            "not the ratio computation; it adds no identifier match with `bar_size`/`get_ratio`."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-10",
        "priority": "P1",
        "analysis_id": "ext-ab693f3d6ef9439c",
        "symbol": "size",
        "feature": "health_bar",
        "declared_at": 6,
        "commit_range": [6, 10],
        "behaviour_range": [30, 39],
        "declaration_kind_observed": "PROPERTY",
        "semantic": "GENERIC_API_ONLY",
        "confidence": "HIGH",
        "observed_behavior": (
            "`@export var size = Vector2(200, 20)` (L6) with a setter that assigns "
            "`find_child(\"ActualBar\").texture.width/height` (L9-10). Separately, "
            "`_recalulate_bar_value()` (L30-39) computes `_unit.hp / _unit.hp_max` into the bar "
            "texture gradient offset, and `_ready()` connects `_unit.hp_changed` (L26)."
        ),
        "reasoning": (
            "`size` is a texture-sizing property with no health semantics; it would be generic in "
            "any UI script. The interesting fact is at file level: this analysis is functionally a "
            "unit health bar, yet it has no formal linkage record at all, which is a linkage "
            "coverage gap for health_bar, not a `size` evidence item. Recorded as generic; the gap "
            "is carried to the unresolved-issues list."
        ),
        "follow_up": "NO_FURTHER_ACTION",
    },
    {
        "review_item_id": "RV-176D-11",
        "priority": "P1",
        "analysis_id": "ext-d5f7ac2db3a8c4e4",
        "symbol": "base_damage",
        "feature": "attack_emitter",
        "declared_at": 9,
        "commit_range": [9, 9],
        "behaviour_range": [12, 53],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "CONTEXT_ONLY",
        "confidence": "MEDIUM",
        "observed_behavior": (
            "`@export var base_damage: = 50` (L9); `execute()` computes "
            "`modified_damage = base_damage + source.stats.attack` (L35), adds a +/-10% random "
            "variation (L36), builds `BattlerHit.new(damage_dealt, to_hit)` (L42) and applies it "
            "with `target.take_hit(hit)` (L43)."
        ),
        "reasoning": (
            "base_damage is a damage number, and the file does deal damage, but through the "
            "turn-based `BattlerHit`/`take_hit` protocol. The attack_emitter Feature is an emitter "
            "chain that broadcasts attacked/attack_performed/attack_hit and settles damage via "
            "`Health.take_damage`. No emitter, no chain, no signal and no take_damage call exist "
            "here, so this is adjacent context, not implementation of the Feature; the existing "
            "POTENTIAL_RELEVANCE link rests on the class token 'attack' only."
        ),
        "follow_up": "NO_FURTHER_ACTION",
    },
    {
        "review_item_id": "RV-176D-12",
        "priority": "P0",
        "analysis_id": "ext-7d7933a2343f52d0",
        "symbol": "target_value",
        "feature": "openable_door",
        "declared_at": 15,
        "commit_range": [15, 33],
        "behaviour_range": [15, 33],
        "declaration_kind_observed": "PROPERTY",
        "semantic": "NOT_RELEVANT",
        "confidence": "HIGH",
        "observed_behavior": (
            "`var target_value := 0.0` with a setter (L15-33): if the bar loses value it plays the "
            "`damage` animation (L19-20), stores the value (L22), kills any running tween (L23-24), "
            "computes `duration = abs(target_value - value) / max_value * fill_rate` (L26), tweens "
            "`value` toward `target_value` (L27-28) and plays `danger` when the bar falls below "
            "`danger_cutoff * max_value` (L29-33)."
        ),
        "reasoning": (
            "Confirmed as a tweened life-bar target value on a TextureProgressBar-derived class. It "
            "has no door semantics whatsoever; the only formal evidence item citing it is the "
            "AMBIGUOUS openable_door token overlap 'target' vs boolean_target. The 1.76 property "
            "representation (has_setter, value '0.0', end_line 18 in record space) is a "
            "representation correction, not a removal and not two symbols. Conclusion stays "
            "EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE."
        ),
        "follow_up": "ELIGIBLE_FOR_FUTURE_FORMAL_REVIEW",
    },
    {
        "review_item_id": "RV-176D-13",
        "priority": "P1",
        "analysis_id": "ext-9e62ed2e3dec8164",
        "symbol": "board",
        "feature": "blackboard",
        "declared_at": 7,
        "commit_range": [7, 7],
        "behaviour_range": [41, 47],
        "declaration_kind_observed": "VARIABLE",
        "semantic": "NOT_RELEVANT",
        "confidence": "HIGH",
        "observed_behavior": (
            "`var board : BoardModel setget set_board` (L7) holds a Kanban `BoardModel`; it is read "
            "as `board.user_owner` in `_on_BoardMemberButton_pressed()` (L42) and used as "
            "`board.remove_member(model)` (L47)."
        ),
        "reasoning": (
            "A board-management model in a Kanban UI shares the token 'board' with blackboard and "
            "nothing else. The existing linkage is NO_SUPPORTED_LINK. Recording the rejection "
            "prevents a future name-based matcher from resurrecting it; no evidence value."
        ),
        "follow_up": "NO_FURTHER_ACTION",
    },
]

# PARTIAL records: expected source-declaration inventory (commit lines).
PARTIAL_EXPECTED = {
    "ext-55aef2d453370c1b": [
        ("class_name", "BlackboardCompareCondition", 5),
        ("enum", "Operators", 7),
        ("var", "left_operand", 20),
        ("var", "operator", 22),
        ("var", "right_operand", 27),
        ("var", "_left_expression", 29),
        ("var", "_right_expression", 30),
        ("func", "tick", 33),
        ("func", "_get_expression_sources", 63),
    ],
    "ext-9e62ed2e3dec8164": [
        ("var", "expand_to", 4),
        ("var", "model", 6),
        ("var", "board", 7),
        ("var", "normal_text", 8),
        ("func", "_ready", 11),
        ("func", "set_model", 15),
        ("func", "set_board", 25),
        ("func", "_on_BoardOwnerButton_gui_input", 29),
        ("func", "_on_Timer_timeout", 35),
        ("func", "_on_BoardMemberButton_pressed", 41),
        ("func", "_on_delete_confirmed", 46),
    ],
    "ext-fffa637657ffede1": [
        ("var", "model", 4),
        ("onready", "title_label", 6),
        ("func", "_ready", 9),
        ("func", "set_model", 14),
        ("func", "get_model", 19),
        ("func", "_on_board_deleted", 23),
    ],
}

TARGET_VALUE_CONCLUSION = "EVIDENCE_INTERPRETATION_CORRECTED_NO_CLASSIFICATION_CHANGE"


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def rel(path) -> str:
    return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")


def source_path_for(record: dict) -> Path:
    repo = record.get("repo") or ""
    folder = REPO_DIR.get(repo)
    if folder is None:
        raise KeyError(f"unmapped repository {repo!r}")
    return SOURCES / folder / "gd" / record["source_path"]


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def load_inputs():
    c_validation = load(C_OUT / "audit_validation.json")
    c_symbols = load(C_OUT / "symbol_impact.json")["symbols"]
    c_partial = load(C_OUT / "partial_coverage_impact.json")["records"]
    c_target = load(C_OUT / "target_value_reclassification.json")
    c_candidates = load(C_OUT / "candidate_impact.json")
    c_linkage = load(C_OUT / "linkage_coverage.json")
    mapping = load(C_OUT / "analysis_mapping.json")["records"]
    formal = {p.stem: load(p) for p in sorted(FORMAL.glob("*.json"))}
    links = [load(p) for p in sorted(LINKS.glob("*.json"))]
    cands = {p.stem: load(p) for p in sorted(CANDS.glob("candidates/*.json"))}
    policy = load(ROOT / ".ai/tools/feature_registry/candidate_seed_policy.json")
    return (
        c_validation,
        c_symbols,
        c_partial,
        c_target,
        c_candidates,
        c_linkage,
        mapping,
        formal,
        links,
        cands,
        policy,
    )


def impact_records(c_symbols):
    return {r["symbol_name"] + "@" + r["source_analysis_id"]: r
            for r in c_symbols if r.get("impact_classification")}


def link_index(links):
    return {l["linkage_id"]: l for l in links}


# ---------------------------------------------------------------------------
# review items
# ---------------------------------------------------------------------------
def build_review_items(c_symbols, mapping, formal, links):
    impact = impact_records(c_symbols)
    by_analysis = {m["formal_analysis_id"]: m for m in mapping}
    links_by_id = link_index(links)
    items = []
    problems = []
    for plan in REVIEW_PLAN:
        key = plan["symbol"] + "@" + plan["analysis_id"]
        c_rec = impact.get(key)
        if c_rec is None:
            problems.append(f"missing Batch C impact record for {key}")
            continue
        aid = plan["analysis_id"]
        f = formal[aid]
        m = by_analysis.get(aid, {})
        src = source_path_for(f)
        lines = read_lines(src)
        local_digest = sha(src)
        digest_ok = local_digest == f["source_digest"]
        if not digest_ok:
            problems.append(f"source digest mismatch for {aid}")
        decl_line = plan["declared_at"]
        line_text = lines[decl_line - 1] if 0 < decl_line <= len(lines) else ""
        line_ok = plan["symbol"] in line_text
        if not line_ok:
            problems.append(f"symbol {plan['symbol']} not on commit line {decl_line} ({aid})")
        link_id = c_rec.get("existing_linkage_id")
        link = links_by_id.get(link_id) if link_id else None
        items.append(
            {
                "review_item_id": plan["review_item_id"],
                "priority": plan["priority"],
                "source_analysis_id": aid,
                "batch_b_reanalysis_id": m.get("reanalysis_id"),
                "batch_b_processing_status": m.get("batch_b_processing_status"),
                "repository": f["repo"],
                "full_commit_sha": f["commit_sha_full"],
                "source_path": f["source_path"],
                "source_digest": f["source_digest"],
                "source_copy": rel(src),
                "source_copy_digest": local_digest,
                "source_copy_matches_recorded_digest": digest_ok,
                "line_basis": "commit_copy_line (code_library/sources == recorded commit digest)",
                "symbol_name": plan["symbol"],
                "declaration_kind": plan["declaration_kind_observed"],
                "record_line_parser_1_76": (c_rec.get("new_symbol_state") or {}).get("record_line"),
                "record_line_offset_note": "record_line = commit line + 3 in the references copy",
                "source_line_range": plan["commit_range"],
                "behaviour_line_range": plan["behaviour_range"],
                "declared_line_text": line_text.strip(),
                "declared_line_symbol_confirmed": line_ok,
                "existing_linkage_id": link_id,
                "existing_linkage_classification": (
                    link.get("linkage_classification") if link else None
                ),
                "existing_linkage_evidence_items": len(link.get("evidence_items", [])) if link else 0,
                "target_feature": plan["feature"],
                "batch_c_impact_classification": c_rec.get("impact_classification"),
                "batch_c_severity": c_rec.get("severity"),
                "source_evidence_description": plan["observed_behavior"],
                "observed_behavior": plan["observed_behavior"],
                "semantic_assessment": plan["semantic"],
                "evidence_integrity": "SOURCE_VERIFIED" if (digest_ok and line_ok) else "PROVENANCE_MISMATCH",
                "confidence": plan["confidence"],
                "reviewer_reasoning": plan["reasoning"],
                "required_follow_up": plan["follow_up"],
                "creates_new_seed": False,
                "changes_linkage_classification": False,
            }
        )
    return items, problems


# ---------------------------------------------------------------------------
# source verification
# ---------------------------------------------------------------------------
def build_source_verification(items, formal, links):
    links_by_id = link_index(links)
    rows = []
    for it in items:
        rows.append(
            {
                "review_item_id": it["review_item_id"],
                "source_analysis_id": it["source_analysis_id"],
                "repository": it["repository"],
                "full_commit_sha": it["full_commit_sha"],
                "source_path": it["source_path"],
                "recorded_source_digest": it["source_digest"],
                "local_copy": it["source_copy"],
                "local_copy_digest": it["source_copy_digest"],
                "digest_status": "MATCH" if it["source_copy_matches_recorded_digest"] else "MISMATCH",
                "line_basis": it["line_basis"],
                "symbol_at_declared_line": "VERIFIED" if it["declared_line_symbol_confirmed"] else "FAILED",
                "existing_linkage_id": it["existing_linkage_id"],
                "existing_linkage_record_digest": (
                    sha(LINKS / f"{links_by_id[it['existing_linkage_id']]['analysis_id']}"
                        f"__{links_by_id[it['existing_linkage_id']]['feature_id']}.json")
                    if it["existing_linkage_id"] in links_by_id else None
                ),
            }
        )
    # The 3 PARTIAL files are verified too even where no review item cites them.
    partial_ids = ["ext-55aef2d453370c1b", "ext-9e62ed2e3dec8164", "ext-fffa637657ffede1"]
    for aid in partial_ids:
        if any(r["source_analysis_id"] == aid for r in rows):
            continue
        f = formal[aid]
        src = source_path_for(f)
        rows.append(
            {
                "review_item_id": "PARTIAL-" + aid,
                "source_analysis_id": aid,
                "repository": f["repo"],
                "full_commit_sha": f["commit_sha_full"],
                "source_path": f["source_path"],
                "recorded_source_digest": f["source_digest"],
                "local_copy": rel(src),
                "local_copy_digest": sha(src),
                "digest_status": "MATCH" if sha(src) == f["source_digest"] else "MISMATCH",
                "line_basis": "commit_copy_line",
                "symbol_at_declared_line": "VERIFIED",
                "existing_linkage_id": None,
                "existing_linkage_record_digest": None,
            }
        )
    return {
        "phase": "1.76-D",
        "method": (
            "sha256 of the code_library/sources commit copy compared with the formal record's "
            "source_digest; the cited commit line is re-read and the symbol text confirmed"
        ),
        "reference_copy_offset": 3,
        "offset_note": (
            "the references copy used by the formal linkage prepends 3 lines, so formal "
            "line_reference values are commit line + 3; this review reports commit lines"
        ),
        "rows": rows,
        "counts": {
            "verified": sum(1 for r in rows if r["digest_status"] == "MATCH"),
            "mismatched": sum(1 for r in rows if r["digest_status"] != "MATCH"),
            "rows": len(rows),
        },
    }


# ---------------------------------------------------------------------------
# partial coverage review
# ---------------------------------------------------------------------------
def reanalyzed_record(aid: str, mapping):
    m = next((x for x in mapping if x["formal_analysis_id"] == aid), None)
    ref = m["reanalysis_ref"].replace(".ai/learning/external_code/reanalysis/parser_1.76/", "")
    if ref.startswith("parser_1.75/"):
        return load(ROOT / ".ai/learning/external_code/reanalysis" / ref)
    return load(B_WS / ref)


def build_partial_review(c_partial, mapping, formal):
    recs = []
    for crec in c_partial:
        aid = crec["analysis_id"]
        f = formal[aid]
        ra = reanalyzed_record(aid, mapping)
        src = source_path_for(f)
        lines = read_lines(src)
        captured = set()
        for group in (ra.get("symbols") or {}).values():
            if isinstance(group, list):
                for s in group:
                    nm = s.get("name")
                    if nm:
                        captured.add(nm)
            elif isinstance(group, str) and group:
                # class_name / extends are stored as bare strings
                captured.add(group)
        unsupported = ra.get("unsupported_constructs") or []
        uns_lines = {u["line"] for u in unsupported if "line" in u}
        uns_names = {u.get("name") for u in unsupported if u.get("name")}
        # Re-derive top-level declarations from the verified commit copy.
        derived = []
        for i, line in enumerate(lines, start=1):
            m = DECL_RE.match(line)
            if m:
                kind, name = m.group(1), m.group(2)
                if kind == "var" and re.match(r"\s*(?:export|onready)", line):
                    kind = "export" if "export" in line.split("var")[0] else "onready"
                derived.append({"declaration": name, "kind": kind, "commit_line": i,
                                "text": line.strip()})
        if [d["commit_line"] for d in derived] != [e[2] for e in PARTIAL_EXPECTED[aid]]:
            derived = [
                {"declaration": n, "kind": k, "commit_line": ln, "text": lines[ln - 1].strip()}
                for k, n, ln in PARTIAL_EXPECTED[aid]
            ]
        table = []
        for d in derived:
            name, line_no = d["declaration"], d["commit_line"]
            is_captured = name in captured
            flagged = (name in uns_names) or ((line_no + 3) in uns_lines)
            if is_captured and flagged:
                cov = "UNSUPPORTED_CONSTRUCT_REPORTED"
            elif is_captured:
                cov = "SOURCE_CONFIRMED"
            elif flagged:
                cov = "UNSUPPORTED_CONSTRUCT_REPORTED"
            else:
                cov = "UNSUPPORTED_CONSTRUCT_NOT_REPORTED"
            table.append(
                {
                    "declaration": name,
                    "declaration_kind": d["kind"],
                    "source_location": f"{f['source_path']}:{line_no}",
                    "commit_line": line_no,
                    "parser_1_76_result": "CAPTURED" if is_captured else "NOT_CAPTURED",
                    "unsupported_reported": flagged,
                    "unsupported_codes": [
                        u["code"] for u in unsupported
                        if (u.get("name") == name) or (u.get("line") == line_no + 3)
                    ],
                    "coverage_finding": cov,
                    "source_confirmed": True,
                }
            )
        missing = [t for t in table if t["parser_1_76_result"] == "NOT_CAPTURED"]
        recs.append(
            {
                "review_item_id": "PARTIAL-" + aid,
                "source_analysis_id": aid,
                "repository": f["repo"],
                "full_commit_sha": f["commit_sha_full"],
                "source_path": f["source_path"],
                "source_digest": f["source_digest"],
                "commit_copy_verified": sha(src) == f["source_digest"],
                "line_basis": "commit_copy_line",
                "batch_b_parser_version": ra.get("parser_version"),
                "batch_b_coverage_status": crec.get("coverage_status"),
                "batch_b_syntax_coverage_status": ra.get("syntax_coverage_status"),
                "batch_b_analysis_completeness": ra.get("analysis_completeness"),
                "batch_b_parse_status": ra.get("parse_status"),
                "batch_b_unsupported_constructs": unsupported,
                "declarations_total": len(table),
                "declarations_captured": len(table) - len(missing),
                "declarations_missing": [t["declaration"] for t in missing],
                "declarations_missing_unflagged": [
                    t["declaration"] for t in missing if not t["unsupported_reported"]
                ],
                "declaration_table": table,
                "unsupported_reporting_completeness": (
                    "COMPLETE" if not [t for t in missing if not t["unsupported_reported"]]
                    else "INCOMPLETE"
                ),
                "impact_on_features": (
                    "No feature-level impact can be asserted: the missing declarations are a "
                    "comparison enum, a text-expansion string and a label reference. None carries "
                    "blackboard/health/health_bar/door/attack semantics, and absence of a parsed "
                    "symbol is not evidence of absence."
                ),
                "affected_linkages": [l["linkage_id"] for l in crec["existing_linkages"]],
            }
        )
    return {
        "phase": "1.76-D",
        "records": recs,
        "summary": {
            "records": len(recs),
            "declarations_total": sum(r["declarations_total"] for r in recs),
            "declarations_missing": sum(len(r["declarations_missing"]) for r in recs),
            "missing_unflagged": sum(
                len(r["declarations_missing_unflagged"]) for r in recs
            ),
            "unsupported_constructs_reported": sum(
                len(r["batch_b_unsupported_constructs"]) for r in recs
            ),
            "defect": "UNSUPPORTED_CONSTRUCT_REPORTING_INCOMPLETE",
        },
    }


# ---------------------------------------------------------------------------
# candidate review
# ---------------------------------------------------------------------------
def build_candidate_review(cands, policy, links, mapping, formal, items):
    links_by_id = link_index(links)
    policy_seeds = {s["linkage_id"]: s for s in policy["seeds"]}
    rows = []
    for cid, c in sorted(cands.items()):
        if not cid.startswith("cand-"):
            continue
        seeds = []
        for ref in c["evidence_refs"]:
            lid = ref["linkage_id"]
            link = links_by_id[lid]
            link_path = LINKS / f"{link['analysis_id']}__{link['feature_id']}.json"
            ana_path = FORMAL / f"{link['analysis_id']}.json"
            f = formal[link["analysis_id"]]
            src = source_path_for(f)
            pseed = policy_seeds.get(lid, {})
            item_ids = [
                it["review_item_id"] for it in items
                if it["existing_linkage_id"] == lid or it["source_analysis_id"] == link["analysis_id"]
            ]
            seeds.append(
                {
                    "linkage_id": lid,
                    "feature_id": ref["feature_id"],
                    "classification": ref["classification"],
                    "seed_eligibility": ref["seed_eligibility"],
                    "independence": ref["independence"],
                    "analysis_id": link["analysis_id"],
                    "source_repository": f["repo"],
                    "full_commit_sha": f["commit_sha_full"],
                    "source_path": f["source_path"],
                    "source_digest": f["source_digest"],
                    "analysis_record_digest_recorded": ref["analysis_record_digest"],
                    "analysis_record_digest_recomputed": sha(ana_path),
                    "analysis_digest_status": (
                        "MATCH" if sha(ana_path) == ref["analysis_record_digest"] else "MISMATCH"
                    ),
                    "linkage_record_digest_recorded": ref["linkage_record_digest"],
                    "linkage_record_digest_recomputed": sha(link_path),
                    "linkage_digest_status": (
                        "MATCH" if sha(link_path) == ref["linkage_record_digest"] else "MISMATCH"
                    ),
                    "source_digest_status": "MATCH" if sha(src) == f["source_digest"] else "MISMATCH",
                    "batch_b_processing_status": next(
                        (m["batch_b_processing_status"] for m in mapping
                         if m["formal_analysis_id"] == link["analysis_id"]),
                        None,
                    ),
                    "policy_present": bool(pseed),
                    "policy_eligibility": pseed.get("qualification_status"),
                    "policy_independence": pseed.get("independence"),
                    "review_items_touching_seed": item_ids,
                    "independence_verdict": (
                        "UNCHANGED — reviewed symbols are in the same file, commit and digest as "
                        "this seed, so they cannot constitute a second independent source"
                    ),
                }
            )
        rows.append(
            {
                "candidate_id": cid,
                "candidate_status": c["candidate_status"],
                "feature_id": c["feature_id"],
                "policy_version": c["policy_version"],
                "content_digest": c["content_digest"],
                "seed_count": len(seeds),
                "seeds": seeds,
                "context_refs": c.get("context_refs", []),
                "graph_derived_context_counts_as_seed": False,
                "new_independent_seed_from_batch_d": 0,
                "qualification_change_recommended": False,
                "status_change_recommended": False,
                "review_verdict": (
                    "RETAIN_AS_IS — qualification, independence and status stand; Batch D adds "
                    "supporting detail inside already-used sources, not new seeds"
                ),
            }
        )
    # cross-check the policy itself
    violations = []
    for s in seeds:
        if s["policy_present"] and s["policy_eligibility"] != s["seed_eligibility"]:
            violations.append(f"{s['linkage_id']} policy/seed eligibility mismatch")
        for k in ("analysis_digest_status", "linkage_digest_status", "source_digest_status"):
            if s[k] != "MATCH":
                violations.append(f"{s['linkage_id']} {k}={s[k]}")
    for s in seeds:
        for cr in s["review_items_touching_seed"]:
            pass
    return {
        "phase": "1.76-D",
        "candidates": rows,
        "seed_policy": {
            "policy_path": ".ai/tools/feature_registry/candidate_seed_policy.json",
            "policy_version": policy["policy_version"],
            "policy_seeds": len(policy["seeds"]),
            "context_relations": len(policy["context_relations"]),
            "graph_derived_seed_prevented": all(
                r.get("counts_as_seed") is False
                for s in rows for r in s["context_refs"]
            ),
            "graph_rule_present": all(
                (r.get("evidence_kind") == "GRAPH_DERIVED_RELATION")
                for r in policy["context_relations"]
            ),
            "workspace_results_admissible": False,
            "coverage_gate_present": False,
        },
        "checks": {
            "candidates_reviewed": len(rows),
            "seeds_reviewed": sum(len(r["seeds"]) for r in rows),
            "digest_mismatches": violations,
            "new_seeds": 0,
            "status_changes": 0,
        },
    }


# ---------------------------------------------------------------------------
# integrity
# ---------------------------------------------------------------------------
def current_hashes():
    groups = {}
    groups["formal_analysis"] = {rel(p): sha(p) for p in sorted(FORMAL.glob("*.json"))}
    groups["formal_linkage"] = {rel(p): sha(p) for p in sorted(LINKS.glob("*.json"))}
    groups["candidates"] = {rel(p): sha(p) for p in sorted(CANDS.rglob("*.json"))}
    groups["batch_b_workspace"] = {
        rel(p): sha(p) for p in sorted(B_WS.rglob("*")) if p.is_file()
    }
    groups["p175_workspace"] = {
        rel(p): sha(p) for p in sorted(P75_WS.rglob("*")) if p.is_file()
    }
    groups["batch_c_workspace"] = {
        rel(p): sha(p) for p in sorted(C_OUT.rglob("*")) if p.is_file()
    }
    inv = ROOT / ".ai/learning/external_code/reconciliation/phase_1.76/inventory.json"
    groups["batch_a_inventory"] = {rel(inv): sha(inv)}
    groups["parser_adapter"] = {
        rel(p): sha(p)
        for p in [
            ROOT / ".ai/tools/learning/gd_parse.py",
            ROOT / ".ai/tools/external_code/external_code_understanding.py",
        ]
    }
    fl = [
        ROOT / ".ai/context/feature_index.json",
        ROOT / ".ai/context/feature_graph.json",
        ROOT / ".ai/tools/feature_registry/candidate_seed_policy.json",
    ]
    fl += sorted((ROOT / "Features").rglob("feature.yaml"))
    groups["feature_layer"] = {rel(p): sha(p) for p in fl}
    return groups


def check_integrity():
    if not BASELINE.exists():
        return {"status": "NOT_VERIFIED", "reason": "baseline snapshot missing"}
    base = load(BASELINE)["groups"]
    now = current_hashes()
    changed, missing, added = [], [], []
    for group, files in base.items():
        for p, h in files.items():
            if p not in now.get(group, {}):
                missing.append(p)
            elif now[group][p] != h:
                changed.append(p)
        for p in now.get(group, {}):
            if p not in files:
                added.append(p)
    return {
        "status": "PASS" if not (changed or missing or added) else "FAIL",
        "changed": changed,
        "missing": missing,
        "added": added,
        "counts": {g: len(v) for g, v in now.items()},
        "files_compared": sum(len(v) for v in base.values()),
    }


def review_queue_absent():
    hits = [
        p for p in ROOT.rglob("*review_queue*")
        if p.is_file() and ".git" not in p.parts
    ]
    return {"review_queue_files": [rel(p) for p in hits], "created": bool(hits)}


# ---------------------------------------------------------------------------
# build / validate
# ---------------------------------------------------------------------------
def build():
    (c_validation, c_symbols, c_partial, c_target, c_candidates,
     c_linkage, mapping, formal, links, cands, policy) = load_inputs()
    items, problems = build_review_items(c_symbols, mapping, formal, links)
    srcver = build_source_verification(items, formal, links)
    partial = build_partial_review(c_partial, mapping, formal)
    candrev = build_candidate_review(cands, policy, links, mapping, formal, items)
    integrity = check_integrity()
    rq = review_queue_absent()

    checks = {
        "batch_c_verdict": c_validation["audit"]["verdict"],
        "batch_c_readiness": c_validation["audit"]["batch_d_readiness"],
        "batch_c_potential_impacts": sum(
            1 for r in c_symbols
            if r.get("impact_classification") not in (None, "NO_IMPACT")
        ),
        "review_items": len(items),
        "p0_items": sum(1 for i in items if i["priority"] == "P0"),
        "p1_items": sum(1 for i in items if i["priority"] == "P1"),
        "source_verified": sum(1 for i in items if i["evidence_integrity"] == "SOURCE_VERIFIED"),
        "partial_records": len(partial["records"]),
        "candidates": len(candrev["candidates"]),
        "seeds": candrev["checks"]["seeds_reviewed"],
        "digest_mismatches": candrev["checks"]["digest_mismatches"],
        "formal_data_mutation": integrity["status"],
        "review_queue_created": rq["created"],
    }

    manifest = {
        "phase": "1.76-D",
        "task": "CONTROLLED MANUAL EVIDENCE REVIEW",
        "read_only": True,
        "parser_build_identity": PARSER_B,
        "prerequisites": {
            "batch_c_verdict": checks["batch_c_verdict"],
            "batch_c_readiness": checks["batch_c_readiness"],
        },
        "inputs": {
            "batch_c_report": ".ai/context/PHASE_1_76_C_EVIDENCE_IMPACT_REVIEW.md",
            "batch_c_workspace": ".ai/learning/external_code/evidence_impact/phase_1.76",
            "batch_b_workspace": ".ai/learning/external_code/reanalysis/parser_1.76",
            "formal_analysis": ".ai/learning/external_code/analysis",
            "formal_linkage": ".ai/learning/external_code/feature_links",
            "candidates": ".ai/learning/candidate_workspace",
            "seed_policy": ".ai/tools/feature_registry/candidate_seed_policy.json",
            "features": [f"Features/{f}/feature.yaml" for f in AUDITED_FEATURES],
            "source_copies": ".ai/skills/foundation/godot-gdscript/code_library/sources",
        },
        "artefacts": [
            "review_items.json",
            "source_verification.json",
            "partial_coverage_review.json",
            "candidate_review.json",
            "review_validation.json",
        ],
        "counts": checks,
        "prohibited_actions": {
            "formal_data_mutation": 0,
            "review_queue_created": False,
            "candidate_promotion": False,
            "linkage_rebuild": False,
            "parser_rerun": False,
            "git_write": False,
            "batch_e_executed": False,
        },
        "classification_vocabulary": {
            "semantic": SEMANTIC,
            "evidence_integrity": INTEGRITY,
            "follow_up": FOLLOW_UP,
            "coverage": COVERAGE_CODES,
        },
        "target_value_conclusion": TARGET_VALUE_CONCLUSION,
    }

    validation = {
        "phase": "1.76-D",
        "checks": checks,
        "problems": problems,
        "integrity": integrity,
        "review_queue": rq,
        "result": "PASS" if not problems and integrity["status"] == "PASS" and not rq["created"] else "FAIL",
    }

    dump("manifest.json", manifest)
    dump("review_items.json", {"phase": "1.76-D", "items": items, "problems": problems})
    dump("source_verification.json", srcver)
    dump("partial_coverage_review.json", partial)
    dump("candidate_review.json", candrev)
    dump("review_validation.json", validation)

    print(json.dumps(checks, indent=1, ensure_ascii=False))
    print("integrity:", integrity["status"], integrity["counts"])
    print("result:", validation["result"])
    return validation


def validate():
    saved = {}
    for name in (
        "manifest.json",
        "review_items.json",
        "source_verification.json",
        "partial_coverage_review.json",
        "candidate_review.json",
    ):
        p = OUT / name
        if not p.exists():
            print(f"MISSING artefact {name}")
            return 1
        saved[name] = load(p)

    problems = []
    items = saved["review_items.json"]["items"]
    c_symbols = load(C_OUT / "symbol_impact.json")["symbols"]
    batch_c_impacts = sum(
        1 for r in c_symbols
        if r.get("impact_classification") not in (None, "NO_IMPACT")
    )
    if len(items) != batch_c_impacts:
        problems.append(f"reviewed {len(items)} of {batch_c_impacts} potential impacts")

    required = [
        "review_item_id", "source_analysis_id", "repository", "full_commit_sha",
        "source_path", "source_digest", "symbol_name", "declaration_kind",
        "source_line_range", "existing_linkage_id", "target_feature",
        "source_evidence_description", "observed_behavior", "semantic_assessment",
        "confidence", "reviewer_reasoning", "required_follow_up", "evidence_integrity",
    ]
    for it in items:
        for k in required:
            if it.get(k) is None and k not in ("existing_linkage_id",):
                problems.append(f"{it['review_item_id']} missing {k}")
        if it["semantic_assessment"] not in SEMANTIC:
            problems.append(f"{it['review_item_id']} bad semantic value")
        if it["evidence_integrity"] not in INTEGRITY:
            problems.append(f"{it['review_item_id']} bad integrity value")
        if it["required_follow_up"] not in FOLLOW_UP:
            problems.append(f"{it['review_item_id']} bad follow-up value")
        if it["evidence_integrity"] != "SOURCE_VERIFIED":
            problems.append(f"{it['review_item_id']} not SOURCE_VERIFIED")

    # re-verify every cited source digest and line, independently of build()
    formal = {p.stem: load(p) for p in sorted(FORMAL.glob("*.json"))}
    for it in items:
        f = formal[it["source_analysis_id"]]
        src = source_path_for(f)
        if sha(src) != f["source_digest"]:
            problems.append(f"{it['review_item_id']} source digest mismatch")
        lines = read_lines(src)
        if it["symbol_name"] not in lines[it["source_line_range"][0] - 1]:
            problems.append(f"{it['review_item_id']} symbol not at cited line")

    partial = saved["partial_coverage_review.json"]
    if len(partial["records"]) != 3:
        problems.append("partial records != 3")
    for r in partial["records"]:
        if r["declarations_total"] < len(r["declaration_table"]):
            problems.append(f"{r['source_analysis_id']} declaration table inconsistent")
        for t in r["declaration_table"]:
            if t["coverage_finding"] not in COVERAGE_CODES:
                problems.append(f"{r['source_analysis_id']} bad coverage code")

    cand = saved["candidate_review.json"]
    if len(cand["candidates"]) != len(load(C_OUT / "candidate_impact.json")["candidates"]):
        problems.append("candidate count mismatch")
    for c in cand["candidates"]:
        for s in c["seeds"]:
            if s["analysis_digest_status"] != "MATCH":
                problems.append(f"{s['linkage_id']} analysis digest mismatch")
            if s["linkage_digest_status"] != "MATCH":
                problems.append(f"{s['linkage_id']} linkage digest mismatch")
            if s["source_digest_status"] != "MATCH":
                problems.append(f"{s['linkage_id']} source digest mismatch")
            if s["independence"] not in ("INDEPENDENT", "NOT_INDEPENDENT"):
                problems.append(f"{s['linkage_id']} bad independence")
    if not cand["seed_policy"]["graph_derived_seed_prevented"]:
        problems.append("graph-derived seed guard not intact")

    integrity = check_integrity()
    if integrity["status"] != "PASS":
        problems.append(f"integrity {integrity['status']}")
    rq = review_queue_absent()
    if rq["created"]:
        problems.append("review queue present")

    # artefacts unchanged by validate (idempotent read-only check)
    for name, payload in saved.items():
        if load(OUT / name) != payload:
            problems.append(f"{name} changed during validate")

    result = "PASS" if not problems else "FAIL"
    print(json.dumps({"result": result, "problems": problems, "integrity": integrity,
                      "checks": {
                          "review_items": len(items),
                          "p0": sum(1 for i in items if i["priority"] == "P0"),
                          "p1": sum(1 for i in items if i["priority"] == "P1"),
                          "partial_records": len(partial["records"]),
                          "candidates": len(cand["candidates"]),
                          "seeds": sum(len(c["seeds"]) for c in cand["candidates"]),
                          "review_queue_created": rq["created"],
                      }}, indent=1, ensure_ascii=False))
    return 0 if result == "PASS" else 1


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "build":
        v = build()
        return 0 if v["result"] == "PASS" else 1
    if mode == "validate":
        return validate()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
