"""Phase 1.65 学习引擎共享入口：项目根、正式契约、源代码文件定位。

所有定位都走真实磁盘与真实契约；**禁止**按 Behavior 名字猜测源码路径。
"""

from __future__ import annotations

import glob
import json
import os
import sys

import yaml

LEARNING_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(LEARNING_DIR)


def project_root() -> str:
    """向上找含 project.godot 的目录（不靠层数硬算）。"""
    current = LEARNING_DIR
    while True:
        if os.path.isfile(os.path.join(current, "project.godot")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.getcwd()
        current = parent


ROOT = project_root()
FEATURES_DIR = os.path.join(ROOT, "Features")
TAXONOMY_PATH = os.path.join(ROOT, ".ai", "context", "phase_1_64_behavior_taxonomy.json")
LEARNING_STATE = os.path.join(ROOT, ".ai", "learning")

_TAXONOMY = None


def _sys_path(path: str) -> None:
    if path not in sys.path:
        sys.path.insert(0, path)


def taxonomy() -> dict:
    global _TAXONOMY
    if _TAXONOMY is None:
        with open(TAXONOMY_PATH, encoding="utf-8") as handle:
            _TAXONOMY = json.load(handle)
    return _TAXONOMY


def category_of(feature_id: str, behavior_id: str) -> str:
    """主类（A..F）来自 1.64 已审计的分类表；缺失即报错，不猜默认值。"""
    entries = taxonomy().get("entries") or []
    for entry in entries:
        if entry.get("f") == feature_id and entry.get("b") == behavior_id:
            value = entry.get("p")
            if value:
                return str(value)
    raise KeyError("no taxonomy entry for %s/%s" % (feature_id, behavior_id))


def risk_of(feature_id: str, behavior_id: str) -> int:
    """1.64 审计过的风险分（同一条公式，不在本阶段重新加权）。"""
    for entry in taxonomy().get("entries") or []:
        if entry.get("f") == feature_id and entry.get("b") == behavior_id:
            return 2 * int(entry.get("i", 1)) + 2 * int(entry.get("st", 1)) \
                + 3 * int(entry.get("dl", 0)) + int(entry.get("ev", 1)) \
                + 2 * int(entry.get("lk", 0))
    return 0


def supported_behaviors() -> list[dict]:
    """动态读取正式支持集合：Features/*/template.yaml#behavior。"""
    items = []
    for template in sorted(glob.glob(os.path.join(FEATURES_DIR, "*", "template.yaml"))):
        feature_id = os.path.basename(os.path.dirname(template))
        with open(template, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        for behavior in data.get("behavior") or []:
            if not isinstance(behavior, dict) or "id" not in behavior:
                continue
            items.append({"feature_id": feature_id,
                          "behavior_id": str(behavior["id"]),
                          "behavior": behavior,
                          "contract_path": os.path.relpath(template, ROOT).replace(os.sep, "/")})
    return items


def contract_version(feature_id: str, behavior_id: str) -> str:
    """复用 1.60/1.63 的契约版本规则（与矩阵/绑定一致），不另造哈希。"""
    _sys_path(os.path.join(TOOLS_DIR, "validator"))
    import binding_candidates  # noqa: PLC0415  (延迟导入，避免循环)

    version, _expected, _core = binding_candidates.contract_digest(feature_id, behavior_id)
    return version


def implementation_files(feature_id: str) -> list[str]:
    """Feature 的真实实现文件（排除 `test_*.gd`）。不猜、不跨 Feature 借。"""
    directory = os.path.join(FEATURES_DIR, feature_id)
    if not os.path.isdir(directory):
        return []
    files = []
    for path in sorted(glob.glob(os.path.join(directory, "*.gd"))):
        name = os.path.basename(path)
        if name.startswith("test_") or name.endswith("_test.gd"):
            continue
        if "fixture" in name:
            # 证据夹具不是被测实现；把它们混进实现集合会让入口解析歧义。
            continue
        files.append(path)
    return files


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def feature_meta(feature_id: str) -> dict:
    path = os.path.join(FEATURES_DIR, feature_id, "feature.yaml")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def behavior_of_method(feature_id: str, method: str) -> str | None:
    """契约 action/expected 里出现某方法的 Behavior（用于跨 Feature 调用归属）。"""
    for item in supported_behaviors():
        if item["feature_id"] != feature_id:
            continue
        text = json.dumps(item["behavior"], ensure_ascii=False)
        if '"%s"' % method in text or ".%s" % method in text or " %s(" % method in text:
            return item["behavior_id"]
    return None
