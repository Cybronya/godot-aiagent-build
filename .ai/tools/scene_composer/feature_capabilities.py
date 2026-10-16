#!/usr/bin/env python3
"""Feature Capability Reader (Phase 1.8.11) —— Feature 能力声明的统一读取接口。

定位（Capability Producer 的第一环）：

    Features/<id>/feature.yaml          （capabilities.required —— 声明）
        ↓  feature_capabilities（本模块：只读取，不判断）
    Scene Blueprint.capabilities        （template_loader.normalize_scene_blueprint 汇总）
        ↓  SceneIntentBuilder
    Scene Intent.capabilities.required  （materialize）
        ↓
    compatibility_gate                  （能不能做 —— 与本模块无关）

职责边界（严格隔离，见契约 capability_pipeline）：
    - 只读 Feature definition（`Features/<id>/feature.yaml`）中的 capabilities.required。
    - **禁止**读取 Blueprint / Scene Intent / Compatibility Gate / 能力词汇表
      （capability_registry 属于 Gate 侧；本模块不知道哪些能力“被支持”）。
    - **禁止**自动推断能力：不按 Feature 名 / 类别 / provides 标签猜测（禁止
      “名字像 EnemyAttack 就加 Script”）。没有声明 → `[]`。
    - 本模块不写文件、不修改 registry、不做校验判定。
"""

import os

import yaml

# 目录定位：本文件位于 <root>/.ai/tools/scene_composer/ 下（与 template_loader 同层，
# 因此不 import template_loader，避免循环依赖）。
_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
METADATA_NAME = "feature.yaml"


def normalize_required(raw) -> list:
    """能力声明 -> 去空、去重（保序）的字符串列表。

    接受 None / list[str] / str / `{"required": [...]}`；其它形态 → ValueError（不猜测）。
    与 scene_intent 的声明规范化语义一致（两处独立实现，测试锁定一致性）。
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        if "required" in raw:
            raw = raw["required"]
        elif not raw:
            return []
        else:
            raise ValueError("capabilities mapping must contain 'required', got keys %s"
                             % sorted(str(key) for key in raw))
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise ValueError("capabilities.required must be a list of names, got %s"
                         % type(raw).__name__)
    required = []
    for entry in raw:
        name = str(entry or "").strip()
        if name and name not in required:
            required.append(name)
    return required


def feature_capabilities(feature_definition) -> dict:
    """Feature definition（已解析的 feature.yaml mapping）-> `{"required": [...]}`。

    缺声明 → `{"required": []}`（旧 Feature 继续合法）。非 mapping → ValueError。
    """
    if isinstance(feature_definition, dict):
        return {"required": normalize_required(feature_definition.get("capabilities"))}
    raise ValueError("feature_capabilities expects a Feature definition mapping, got %s"
                     % type(feature_definition).__name__)


def load_feature_definition(feature_id: str, features_dir: str = FEATURES_DIR):
    """读取 Features/<id>/feature.yaml；缺失 / 不可解析时返回 None（不抛异常）。"""
    path = os.path.join(features_dir, str(feature_id), METADATA_NAME)
    if not os.path.isfile(path):
        return None
    try:
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def capabilities_for_feature(feature_id: str, features_dir: str = FEATURES_DIR) -> list:
    """Feature id -> 该 Feature 声明的能力列表（无声明 / 无 metadata → []）。"""
    definition = load_feature_definition(feature_id, features_dir)
    if definition is None:
        return []
    return feature_capabilities(definition)["required"]


def capabilities_for_features(feature_ids, features_dir: str = FEATURES_DIR) -> list:
    """多个 Feature id -> 汇总去重（保序）的能力需求列表。

    顺序 = 成员声明顺序（同一能力只保留首次出现）；缺失 metadata 的成员被跳过
    （Feature 存在性与元数据完整性由 check_feature_metadata.py 负责，不在此重复）。
    """
    merged = []
    for feature_id in feature_ids or []:
        for name in capabilities_for_feature(feature_id, features_dir):
            if name not in merged:
                merged.append(name)
    return merged


def main(argv=None) -> int:  # pragma: no cover - 诊断入口（只读，无副作用）
    """打印各 Feature 的能力声明（只读 Feature metadata）。"""
    if not os.path.isdir(FEATURES_DIR):
        print("FAIL: Features directory not found: %s" % FEATURES_DIR)
        return 1
    print("Feature capability declarations")
    found = False
    for name in sorted(os.listdir(FEATURES_DIR)):
        if not os.path.isdir(os.path.join(FEATURES_DIR, name)):
            continue
        required = capabilities_for_feature(name)
        print("  %-20s %s" % (name, required if required else "[]"))
        found = found or bool(required)
    if not found:
        print("(no Feature declares capabilities yet → Scene Intent.capabilities.required = [])")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
