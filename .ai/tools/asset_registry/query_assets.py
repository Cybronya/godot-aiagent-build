#!/usr/bin/env python3
"""Asset Query —— 用关键词 / 标签 / 路径 / 类型在 Asset Index 中检索资源。

    # 旧 CLI（不变）
    python query_assets.py "player idle animation"
    python query_assets.py "enemy attack animation" --limit 5
    python query_assets.py "hurt" --type audio --category audio
    python query_assets.py "slime" --json

    # Agent API（Phase 1.7.9）
    python query_assets.py --json --query "player attack animation"
    python query_assets.py --json --query "enemy attack" --type animation --limit 10

机器可读 JSON 契约：.ai/context/asset_query_schema.yaml（query/count/results）。\n排序完全确定性（无 LLM）：token 命中 id / tags / path / type / category / subject / role
加权求和；仅在已有命中时，再对「已人工确认」与「已被场景引用」的资源给小幅加成。

不做：扫描（scan_assets.py）、索引构建（build_asset_index.py）、绑定（bind_assets.py）。

退出码: 0 = 有结果；1 = 无结果；2 = 输入错误。

schema_version: 2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_metadata import (          # noqa: E402
    DEFAULT_PROJECT_ROOT,
    index_assets,
    load_index,
)

# 打分权重（确定性）
WEIGHT_ID = 2.0
WEIGHT_TAG = 2.0
WEIGHT_ROLE = 2.5
WEIGHT_SUBJECT = 2.5
WEIGHT_PATH = 1.0
WEIGHT_TYPE = 1.0
WEIGHT_CATEGORY = 1.0
PHRASE_BONUS = 3.0
CONFIRMED_BONUS = 1.0
REFERENCED_BONUS = 0.5


def tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(text).lower()) if token]


def score_asset(asset: dict, tokens: list[str], phrase: str, explain: bool = False) -> tuple:
    """返回 (score, reasons)。"""
    asset_id = str(asset.get("id") or "")
    tags = [str(tag).lower() for tag in asset.get("tags") or []]
    path = str(asset.get("path") or "").lower()
    role = str(asset.get("role") or "").lower()
    subject = str(asset.get("subject") or "").lower()
    asset_type = str(asset.get("type") or "").lower()
    category = str(asset.get("category") or "").lower()

    score = 0.0
    reasons: list[str] = []
    id_tokens = set(tokenize(asset_id))
    for token in tokens:
        if token in id_tokens or token in asset_id:
            score += WEIGHT_ID
            reasons.append("id~%s(+%.1f)" % (token, WEIGHT_ID))
        if token in tags:
            score += WEIGHT_TAG
            reasons.append("tag=%s(+%.1f)" % (token, WEIGHT_TAG))
        if token == role:
            score += WEIGHT_ROLE
            reasons.append("role=%s(+%.1f)" % (token, WEIGHT_ROLE))
        if token == subject:
            score += WEIGHT_SUBJECT
            reasons.append("subject=%s(+%.1f)" % (token, WEIGHT_SUBJECT))
        if token in path:
            score += WEIGHT_PATH
            reasons.append("path~%s(+%.1f)" % (token, WEIGHT_PATH))
        if token == asset_type:
            score += WEIGHT_TYPE
            reasons.append("type=%s(+%.1f)" % (token, WEIGHT_TYPE))
        if token == category:
            score += WEIGHT_CATEGORY
            reasons.append("category=%s(+%.1f)" % (token, WEIGHT_CATEGORY))

    if phrase and (phrase in asset_id or phrase in " ".join(tags)):
        score += PHRASE_BONUS
        reasons.append("phrase(+%.1f)" % PHRASE_BONUS)
    # 加成只在「已经命中查询词」时生效；否则任何被引用过的资源都会命中任意查询。
    if score > 0:
        if asset.get("confirmed"):
            score += CONFIRMED_BONUS
            reasons.append("confirmed(+%.1f)" % CONFIRMED_BONUS)
        if asset.get("used_by"):
            score += REFERENCED_BONUS
            reasons.append("referenced(+%.1f)" % REFERENCED_BONUS)
    return score, reasons


def query(index: dict, text: str, limit: int = 10, types: list[str] | None = None,
          category: str = "", role: str = "", subject: str = "",
          confirmed_only: bool = False, explain: bool = False) -> list[dict]:
    """检索资产，返回按分数降序的结果列表。"""
    tokens = tokenize(text)
    phrase = "_".join(tokens)
    results = []
    for asset in index_assets(index):
        if types and asset.get("type") not in types:
            continue
        if category and str(asset.get("category")) != category:
            continue
        if role and str(asset.get("role")) != role:
            continue
        if subject and str(asset.get("subject")) != subject:
            continue
        if confirmed_only and not asset.get("confirmed"):
            continue
        score, reasons = score_asset(asset, tokens, phrase)
        if score <= 0:
            continue
        entry = {
            "id": asset.get("id"),
            "path": asset.get("path"),
            "type": asset.get("type"),
            "category": asset.get("category"),
            "role": asset.get("role"),
            "subject": asset.get("subject"),
            "tags": asset.get("tags"),
            "confirmed": asset.get("confirmed"),
            "score": round(score, 2),
        }
        if explain:
            entry["reasons"] = reasons
        results.append(entry)
    results.sort(key=lambda item: (-item["score"], str(item["id"])))
    return results[:limit] if limit else results


def print_results(results: list[dict], text: str) -> None:
    print("Asset Query: %s" % text)
    if not results:
        print()
        print("No matching asset.")
        return
    print()
    for position, entry in enumerate(results, 1):
        print("%d. %s" % (position, entry["id"]))
        print("   path: %s" % entry["path"])
        print("   type: %s" % entry["type"])
        print("   tags: %s" % ",".join(entry.get("tags") or []))
        print("   score: %.2f%s" % (entry["score"],
                                    "" if not entry.get("confirmed") else " (confirmed)"))
        if entry.get("reasons"):
            print("   why: %s" % " ".join(entry["reasons"]))
        print()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Query the generated asset index.")
    parser.add_argument("query", nargs="*", help="Query text (positional, e.g. 'player idle animation')")
    parser.add_argument("--query", "-q", dest="named_query", default="",
                        help="Query text (named form; Agent API)")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--index", default="")
    parser.add_argument("--type", action="append", default=None, help="Filter by asset type")
    parser.add_argument("--category", default="")
    parser.add_argument("--role", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--confirmed-only", action="store_true")
    parser.add_argument("--explain", action="store_true", help="Show the score breakdown")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    index = load_index(args.index or None, project_root=project)
    if not index_assets(index):
        print("FAIL: asset index is empty or missing: %s" % (args.index or project))
        print("Run: python .ai/tools/asset_registry/build_asset_index.py")
        return 2

    text = " ".join(args.query).strip() or str(args.named_query or "").strip()
    if not text:
        parser.error("provide a query (positional or --query)")
    results = query(index, text, limit=args.limit, types=args.type, category=args.category,
                    role=args.role, subject=args.subject, confirmed_only=args.confirmed_only,
                    explain=args.explain)
    if args.json:
        print(json.dumps({"query": text, "count": len(results), "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print_results(results, text)
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
