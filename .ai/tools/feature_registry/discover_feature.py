#!/usr/bin/env python3
"""Feature Discovery Tool (v2)

根据需求文本在 feature_index.json 中推荐可复用 Feature。

用法:
    python discover_feature.py "enemy can receive damage"
    python discover_feature.py --list

匹配逻辑（无 LLM）:
    需求文本 -> 关键词提取 -> feature metadata 搜索 -> 评分 -> 排序

评分:
    score = provides_match * 5 + interface_match * 3 + category_match * 1

数据来源（只查询，不生成）:
    .ai/context/feature_index.json（由 build_feature_index.py 从
    Features/*/feature.yaml 生成；feature.yaml 是 Source of Truth）。
"""

import io
import json
import os
import re
import sys

# 目录定位：本文件位于 <root>/.ai/tools/feature_registry/ 下
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
INDEX_PATH = os.path.join(_TOOL_DOTAI, "context", "feature_index.json")

# 权重（规范见 README.md）
W_PROVIDES = 5
W_INTERFACE = 3
W_CATEGORY = 1

# 同义词表：需求词 -> 索引中的能力标签。命中左侧任意词时按右侧标签匹配 provides。
SYNONYMS = {
    "hp": ["health_state", "damage_receiver"],
    "health": ["health_state"],
    "life": ["health_state"],
    "damage": ["damage_receiver", "damage_source", "contact_damage_dealing"],
    "heal": ["heal_receiver", "heal_source"],
    "healing": ["heal_receiver"],
    "death": ["death_event"],
    "die": ["death_event"],
    "dies": ["death_event"],
    "move": ["character_movement"],
    "movement": ["character_movement"],
    "chase": ["chase_behavior", "target_following"],
    "follow": ["target_following"],
    "touch": ["contact_damage_dealing"],
    "touching": ["contact_damage_dealing"],
    "input": ["input_driven_movement", "player_control"],
    "player": ["player_control"],
    "attack": ["damage_source", "contact_damage_dealing"],
    "attacker": ["damage_source"],
    "stun": ["stun_state"],
    "hit": ["hit_reaction"],
    "display": ["health_display"],
    "bar": ["health_display"],
    "collect": ["collect_event", "consumable_pickup"],
    "pickup": ["consumable_pickup", "collect_event", "heal_source"],
    "coin": ["collect_event"],
    "key": ["collect_event"],
    "door": ["passage_control", "door_state"],
    "gate": ["passage_control", "condition_aggregation"],
    "open": ["passage_control"],
    "switch": ["trigger_event", "toggle_source"],
    "trigger": ["trigger_event", "condition_input"],
    "button": ["trigger_event"],
    "platform": ["platform_transport", "moving_ground"],
    "ride": ["ride_carrying"],
    "carry": ["ride_carrying"],
    "and": ["and_logic"],
    "condition": ["condition_aggregation", "condition_input"],
    "lock": ["action_lock"],
    "interrupt": ["action_lock", "stun_state"],
}

# 停用词：提取关键词时忽略
STOPWORDS = {
    "a", "an", "the", "can", "when", "while", "is", "are", "be", "been", "was",
    "to", "of", "in", "on", "at", "by", "with", "and", "or", "for", "from",
    "that", "this", "it", "its", "as", "into", "should", "must", "will",
    "enemy", "enemies", "player", "players", "game", "object", "objects",
    "entity", "entities", "node", "nodes", "get", "gets", "got", "has",
    "have", "do", "does", "not", "no", "lose", "loses", "lost", "add",
    "adds", "make", "makes", "want", "need", "needs", "receive", "receives",
}

TOKEN_RE = re.compile(r"[a-z_]+")


def load_index() -> list:
    if not os.path.isfile(INDEX_PATH):
        raise SystemExit(
            "FAIL: Feature index not found: %s\n"
            "Please run: python .ai/tools/feature_registry/build_feature_index.py" % INDEX_PATH
        )
    with io.open(INDEX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def extract_terms(query: str) -> set:
    """关键词提取：小写分词 + 去停用词，并展开同义词到能力标签。"""
    tokens = set(TOKEN_RE.findall(query.lower()))
    keywords = tokens - STOPWORDS
    terms = set(keywords)
    for word in keywords | tokens:
        if word in SYNONYMS:
            terms.update(SYNONYMS[word])
    return terms


def match_feature(feature: dict, terms: set) -> tuple:
    """返回 (score, reasons)。评分规则: provides*5 + interfaces*3 + category*1。"""
    score = 0
    reasons = []

    provides_hits = sorted(set(feature.get("provides", [])) & terms)
    if provides_hits:
        score += W_PROVIDES * len(provides_hits)
        reasons.extend("provides: " + p for p in provides_hits)

    iface_names = {re.sub(r"\W+", "_", i).lower(): i
                   for i in feature.get("interfaces", [])}
    iface_hits = sorted(name for name in iface_names if name in terms)
    if iface_hits:
        score += W_INTERFACE * len(iface_hits)
        reasons.extend("interface: " + iface_names[name] for name in iface_hits)

    category = feature.get("category", "")
    if category and category in terms:
        score += W_CATEGORY
        reasons.append("category: " + category)

    return score, reasons


def format_interfaces(feature: dict) -> list:
    lines = []
    signals = set(feature.get("signals", []))
    for iface in feature.get("interfaces", []):
        if iface in signals:
            lines.append("- %s signal" % iface)
        else:
            lines.append("- %s()" % iface)
    return lines


def discover(query: str, index: list) -> list:
    terms = extract_terms(query)
    results = []
    for feature in index:
        score, reasons = match_feature(feature, terms)
        if score > 0:
            results.append({"feature": feature, "score": score, "reasons": reasons})
    results.sort(key=lambda r: (-r["score"], r["feature"]["id"]))
    return results


def print_result(query: str, results: list) -> None:
    print("Feature Discovery Result")
    print()
    print('Query: "%s"' % query)
    print()
    if not results:
        print("Matched Features: (none)")
        print()
        print("Reason: no Feature metadata matches the query terms.")
        print("Hint: this does not mean the need cannot be met;")
        print("check Features/ directory and feature-development.md Build branch.")
        return
    print("Matched Features:")
    for rank, r in enumerate(results, 1):
        f = r["feature"]
        print()
        print("%d." % rank)
        print("id: %s" % f["id"])
        print()
        print("Reason:")
        print("matched:")
        for reason in r["reasons"]:
            print("- " + reason)
        print()
        print("Interfaces:")
        for line in format_interfaces(f):
            print(line)
    print()


def main(argv: list) -> int:
    if "--list" in argv[1:]:
        index = load_index()
        print("Feature Discovery Result")
        print()
        print("Indexed features: %d" % len(index))
        print()
        for f in index:
            print("- %s [%s] v%s" % (f["id"], f.get("category", ""), f.get("version", "")))
            print("  provides: " + ", ".join(f.get("provides", [])))
        return 0
    args = [a for a in argv[1:] if a != "--list"]
    if not args:
        print(__doc__.strip())
        return 1
    query = " ".join(args)
    results = discover(query, load_index())
    print_result(query, results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
