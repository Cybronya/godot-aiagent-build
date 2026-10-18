#!/usr/bin/env python3
"""Asset Binding —— Entity Blueprint 的资源角色 -> 具体 Asset。

    python bind_assets.py --entity blueprint.yaml --out bindings.yaml
    python bind_assets.py --gameplay survival_game.yaml --out bindings.yaml
    python bind_assets.py --entity blueprint.yaml --binding manual_bindings.yaml

    Feature -> Entity -> Asset 的组合由本工具表达，Feature 内部不硬编码 Asset 路径。

解析规则（确定性，无 LLM）：
    1. 显式绑定（blueprint 的 assets.bindings 或 --binding 文件）优先，且必须能在索引中找到；
       显式条目可携带可选 entity 字段做实体作用域（Phase 1.15，I1）：
         - {entity: <entity_id>, role, asset} —— 只作用于该实体；
         - {role, asset}                      —— 角色级（历史格式），作用于全部实体；
       作用域指向不存在实体的绑定 → binding_scope_errors（可定位，CLI exit 1）；
       多实体文档中角色级绑定按既有规则作用于全部实体，并在条目 note 标注作用域来源；
    2. 否则按 required role 在索引里选候选：
       SpriteFrames（动画名含该 role）> animation 组 > texture > audio（*_sfx role）
       同分时优先主体一致（asset.subject == entity subject）与已人工确认的资源；
    3. 找不到就记入 missing（禁止编造资产）。
    4. 低兼容性不是错误：绑定记录 compatibility 等级，由 Validator 决定 WARNING/ERROR。
    5. 显式绑定的类型门禁（Phase 1.15，I1-E）：sfx 角色要求 audio 资源、视觉角色要求
       可实例化的视觉资源；类型不匹配 → 记入 missing（带可定位原因），且**不回退**到
       索引推断（不得静默降级成默认资源）。

契约：.ai/context/asset_binding_schema.yaml
不做：写场景（Scene Composer）、校验（validator/check_assets.py）、扫描（scan_assets.py）。

退出码: 0 = 绑定产出；1 = --strict 且必填角色缺失；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_metadata import (          # noqa: E402
    DEFAULT_PROJECT_ROOT,
    ROLE_CAPABILITY_HINTS,
    find_asset,
    index_assets,
    load_index,
    read_json,
)
from check_compatibility import LEVELS as COMPAT_LEVELS                              # noqa: E402

# 角色别名：绑定请求 role -> 可接受的资源 role
ROLE_EQUIVALENTS = {
    "idle": ["idle", "stand"],
    "move": ["move", "walk", "run"],
    "run": ["run", "move", "walk"],
    "walk": ["walk", "move", "run"],
    "attack": ["attack", "cast", "shoot"],
    "hurt": ["hurt", "hit", "damage"],
    "death": ["death", "die", "defeat"],
    "jump": ["jump", "fall"],
    "cast": ["cast", "attack"],
    "shoot": ["shoot", "attack"],
    "sfx": ["sfx"],
    "environment_tileset": ["environment_tileset", "tileset", "environment"],
    "tileset": ["environment_tileset", "tileset", "environment"],
}

# 节点类型 -> 共享节点名后缀（多个角色指向同一资源时合并为一个节点）
NODE_SUFFIX = {
    "AnimatedSprite2D": "Anim",
    "Sprite2D": "Sprite",
    "AudioStreamPlayer": "Sfx",
    "AudioStreamPlayer2D": "Sfx",
    "TextureRect": "Sprite",
}

# 资源类型 -> 可用于场景的节点（Scene Composer 依此实例化资源节点）
# Godot 4.3+ TileMap 已 deprecated，本项目 4.7 用 TileMapLayer 承载 tileset。
NODE_MAPPING = {
    "sprite_frames": ("AnimatedSprite2D", "sprite_frames", "Anim"),
    "animation": ("Sprite2D", "texture", "Sprite"),   # 无 SpriteFrames 时退化为首帧静态贴图
    "sprite": ("Sprite2D", "texture", "Sprite"),
    "texture": ("Sprite2D", "texture", "Sprite"),
    "spritesheet": ("Sprite2D", "texture", "Sprite"),
    "audio": ("AudioStreamPlayer", "stream", "Sfx"),
    "tileset": ("TileMapLayer", "tile_set", "Tiles"),
}

# 实体角色 -> 必填资源角色（视觉/动画槽位）
# Phase 1.8.1：单一事实来源迁移到 .ai/context/entity_asset_slots.yaml；
# 本常量改为启动时从配置读出（legacy 内存结构不变，行为一致）。配置缺失时
# 退回 SLOTS_FILE_PATH 默认值指向项目下；结构错误抛 RuntimeError 带路径。
SLOTS_PATH = Path(os.environ.get("ENTITY_ASSET_SLOTS",
                                 str(Path(__file__).resolve().parents[3] / ".ai" / "context" / "entity_asset_slots.yaml")))


def load_entity_slots(path: Path = SLOTS_PATH) -> dict:
    """读取实体槽位配置，返回 {role: {"required": [...], "optional": [...]}}。

    输出同时包含配置级 default_required 偷绑到 "*default*" 键上，供
    entity_required_roles 等 legacy 调用方使用。
    校验 schema.id / schema.version（Phase 1.8.1 一致性补丁）与各节结构；
    未知版本明确报错，不得静默接受。
    """
    if not path.is_file():
        print("FAIL: entity asset slots config not found: %s" % path, file=sys.stderr)
        raise SystemExit(2)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:   # Phase 1.8.1 收尾：解析错误带路径与原因
        raise RuntimeError("entity asset slots config is not valid YAML: %s (%s)"
                           % (path, str(exc).splitlines()[0][:120])) from exc
    if not isinstance(data, dict):
        raise RuntimeError("entity asset slots config must be a mapping: %s" % path)
    schema = data.get("schema") or {}
    if not isinstance(schema, dict) or schema.get("id") != "entity_asset_slots":
        raise RuntimeError("entity asset slots config missing schema.id == entity_asset_slots: %s" % path)
    # Phase 1.8.1 一致性补丁：schema.version 必须显式存在且受支持。
    _SUPPORTED_VERSION = 1
    version = schema.get("version")
    if version is None:
        raise RuntimeError("entity asset slots config missing schema.version: %s" % path)
    try:
        version_ok = int(version) == _SUPPORTED_VERSION
    except (TypeError, ValueError):
        version_ok = False
    if not version_ok:
        raise RuntimeError("entity asset slots config unsupported schema.version %r (supported: %d): %s"
                           % (version, _SUPPORTED_VERSION, path))
    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise RuntimeError("entity asset slots config missing 'roles:' mapping: %s" % path)
    parsed = {}
    for role, block in roles.items():
        if not isinstance(block, dict):
            raise RuntimeError("entity asset slots roles.%s must be a mapping" % role)
        required = block.get("required")
        optional = block.get("optional") or []
        if not isinstance(required, list) or not required \
                or not all(isinstance(r, str) and r.strip() for r in required):
            raise RuntimeError("entity asset slots roles.%s.required must be a non-empty list of strings" % role)
        if not isinstance(optional, list) or not all(isinstance(r, str) and r.strip() for r in optional):
            raise RuntimeError("entity asset slots roles.%s.optional must be a list of strings" % role)
        parsed[str(role)] = {"required": [str(r) for r in required],
                             "optional": [str(r) for r in optional]}
    default = data.get("default_required")
    if default is None:
        default = ["idle"]
    if not isinstance(default, list) or not default \
            or not all(isinstance(r, str) and r.strip() for r in default):
        raise RuntimeError("entity asset slots config default_required must be a non-empty list of strings")
    parsed["*default*"] = {"required": [str(r) for r in default], "optional": []}
    _slots_optional = data.get("optional")
    if _slots_optional is None:
        _slots_optional = []
    if not isinstance(_slots_optional, list) or not all(isinstance(r, str) and r.strip() for r in _slots_optional):
        raise RuntimeError("entity asset slots config optional must be a list of strings")
    parsed["*global_optional*"] = {"required": [], "optional": [str(r) for r in _slots_optional]}
    return parsed


# 完整槽位配置表（含 "*default*"/"*global_optional*" 哨兵键）。
# Phase 1.8.1 一致性补丁：私有名 _ENTITY_SLOTS_TABLE；德国旧名
# REQUIRED_ROLES_BY_ENTITY_ROLE 保留为兼容别名（历史上曾有外部读取风险，
# audit 确认当前无引用，但重命名由别名层吸收，不做行为改动）。
_ENTITY_SLOTS_TABLE = load_entity_slots()
REQUIRED_ROLES_BY_ENTITY_ROLE = _ENTITY_SLOTS_TABLE   # 兼容别名（勿新增依赖）

# 可选资源角色（有则绑定，无则不算缺失）。Phase 1.8.1：从槽位配置读出。
OPTIONAL_ROLES = list(_ENTITY_SLOTS_TABLE.get("*global_optional*", {}).get("optional") or [])


def entity_required_roles(entity_role: str) -> list:
    """实体角色 -> 默认必填槽位（未知角色退配置 default_required，legacy [idle]）。"""
    block = _ENTITY_SLOTS_TABLE.get(entity_role) \
        or _ENTITY_SLOTS_TABLE.get("*default*")
    return list(block["required"])



def _pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in str(name).replace("-", "_").split("_") if part)


# ---------- 显式绑定解析（Phase 1.15，I1：entity 作用域） ----------

def parse_explicit_bindings(entries, source: str = "<binding>",
                            owner_entity: str = "") -> tuple[dict, dict, list]:
    """解析显式绑定条目（--binding 文件或 blueprint 的 assets.bindings）。

    条目格式（asset_binding_schema.yaml「显式绑定覆盖」节）：
        {role, asset}                  —— 角色级（历史格式，作用于全部/所属实体）
        {entity, role, asset}          —— 实体作用域（Phase 1.15）；owner_entity 非空时
                                          entity 必须等于所属实体，否则记为作用域错误

    返回 (global_explicit, scoped_explicit, binding_errors)：
        global_explicit: {role: asset_id}
        scoped_explicit: {entity_id: {role: asset_id}}
        binding_errors:  [{location, entity, role, reason}]（结构非法 / 作用域非法，
                         一律可定位；绝不静默跳过）
    """
    global_explicit: dict[str, str] = {}
    scoped_explicit: dict[str, dict[str, str]] = {}
    errors: list[dict] = []

    def _error(location: str, entity: str, role: str, reason: str) -> None:
        errors.append({"location": location, "entity": entity, "role": role, "reason": reason})

    for index, entry in enumerate(entries or []):
        location = "%s:bindings[%d]" % (source, index)
        if not isinstance(entry, dict):
            _error(location, "", "", "explicit binding entry must be a mapping, got %s"
                   % type(entry).__name__)
            continue
        role = str(entry.get("role") or "").strip()
        asset_id = str(entry.get("asset") or "").strip()
        entity = str(entry.get("entity") or "").strip()
        if not role or not asset_id:
            _error(location, entity, role,
                   "explicit binding entry requires non-empty 'role' and 'asset'")
            continue
        if entity and owner_entity and entity != owner_entity:
            _error(location, entity, role,
                   "explicit binding scoped to entity %r inside entity %r's assets block"
                   % (entity, owner_entity))
            continue
        if entity:
            scoped_explicit.setdefault(entity, {})
            if role in scoped_explicit[entity]:
                _error(location, entity, role,
                       "duplicate explicit binding for entity %r role %r" % (entity, role))
                continue
            scoped_explicit[entity][role] = asset_id
        else:
            if role in global_explicit:
                _error(location, entity, role,
                       "duplicate role-level explicit binding for role %r" % role)
                continue
            global_explicit[role] = asset_id
    return global_explicit, scoped_explicit, errors


# 可实例化的视觉资源类型（audio 只服务 sfx 角色；推导自 NODE_MAPPING，单一来源）
VISUAL_ASSET_TYPES = {t for t in NODE_MAPPING if t != "audio"}


def explicit_type_mismatch(role: str, asset: dict) -> str:
    """显式绑定类型门禁（Phase 1.15，I1-E）：返回不匹配原因（空串 = 通过）。

    sfx 角色（*_sfx / sfx）要求 audio 资源；其余角色要求 Scene Composer 可实例化的
    视觉资源（VISUAL_ASSET_TYPES）。类型不匹配必须明确失败，
    不得静默降级成默认资源（调用方记入 missing 且不回退到索引推断）。
    """
    asset_type = str((asset or {}).get("type") or "")
    if _is_sfx_role(role):
        if asset_type == "audio":
            return ""
        return ("explicit binding type mismatch: role %r requires an audio asset, got type %r"
                % (role, asset_type or "<none>"))
    if asset_type in VISUAL_ASSET_TYPES:
        return ""
    return ("explicit binding type mismatch: role %r requires an instanceable visual "
            "asset (one of %s), got type %r"
            % (role, ", ".join(sorted(VISUAL_ASSET_TYPES)), asset_type or "<none>"))


def _aliases(role: str) -> list[str]:
    return ROLE_EQUIVALENTS.get(role, [role])


def _is_sfx_role(role: str) -> bool:
    return role.endswith("_sfx") or role == "sfx"


def _base_role(role: str) -> str:
    return role[:-4] if role.endswith("_sfx") else role


# 主体化资源类别：主体不匹配时不得强行绑定（避免「要 bat 却给 slime」）
CHARACTER_CATEGORIES = {"player", "enemy", "character"}


# 方向词表（4 / 8 方向都支持；directionless 时不进入本表）。
BINDING_DIRECTIONS = ("up_left", "up_right", "down_left", "down_right", "up", "down", "left", "right")


def split_direction_role(role: str) -> tuple[str, str]:
    """方向性 role -> (base, direction)。

    idle_down -> ("idle", "down")；move_up_right -> ("move", "up_right")；
    move -> ("move", "")。8 方向 token 长度优先于 4 方向 token。
    """
    name = str(role or "").strip().lower()
    for direction in sorted(BINDING_DIRECTIONS, key=len, reverse=True):
        if name.endswith("_" + direction):
            return name[: -(len(direction) + 1)], direction
    return name, ""


def candidate_score(asset: dict, role: str, subject: str, entity_role: str,
                    features) -> tuple[float, list[str], str]:
    """给候选资源打分（确定性规则）。

    返回 (score, reasons, match_kind)，match_kind ∈ {exact, alias, unspecific}：
        exact     —— 角色与动画名“精确”命中（SpriteFrames 动画名 / 资源 role 同名）
        alias     —— 通过角色别名命中（move<->walk<->run 等）
        unspecific —— 未使用角色语义也能命中（仅音频等通用资源）
    """
    score = 0.0
    reasons: list[str] = []
    match_kind = "unspecific"
    base = _base_role(role)
    aliases = _aliases(base)
    asset_type = str(asset.get("type") or "")
    asset_role = str(asset.get("role") or "")
    sfx = _is_sfx_role(role)

    if sfx:
        if asset_type != "audio":
            return 0.0, ["not audio"], match_kind
        if asset_role == base:
            score += 6.0
            match_kind = "exact"
            reasons.append("audio role=%s" % base)
        elif asset_role in aliases:
            score += 4.0
            match_kind = "alias"
            reasons.append("audio role alias=%s" % asset_role)
        else:
            return 0.0, ["audio role mismatch"], match_kind
    else:
        if asset_type == "sprite_frames":
            animations = [str(name).lower() for name in asset.get("animations") or []]
            if base in animations:
                score += 7.0
                match_kind = "exact"
                reasons.append("sprite_frames has animation %s" % base)
            elif set(animations) & set(aliases):
                score += 5.0
                match_kind = "alias"
                reasons.append("sprite_frames has animation alias %s"
                               % sorted(set(animations) & set(aliases)))
            else:
                return 0.0, ["sprite_frames lacks animation %s" % base], match_kind
        elif asset_type == "tileset":
            # tileset 是环境资源：角色须匹配（environment_tileset / tileset 等），
            # 或 role 本身语义为环境资源；主体语义（slime/player）永远是 mismatch。
            tile_roles = {"environment_tileset", "tileset", "environment"}
            if base in tile_roles or asset_role in tile_roles:
                score += 6.0
                match_kind = "exact" if base == asset_role else "alias"
                reasons.append("tileset role=%s (requested %s)" % (asset_role or "<none>", base))
            else:
                return 0.0, ["tileset does not satisfy role %r" % base], match_kind
        elif asset_type in ("animation", "texture", "sprite", "spritesheet"):
            if asset_role == base:
                score += 5.0
                match_kind = "exact"
                reasons.append("%s role=%s" % (asset_type, base))
            elif asset_role in aliases:
                score += 3.5
                match_kind = "alias"
                reasons.append("%s role alias=%s" % (asset_type, asset_role))
            else:
                return 0.0, ["role mismatch"], match_kind
        else:
            return 0.0, ["type %s is not visual" % asset_type], match_kind

    if subject and str(asset.get("subject") or "") == subject:
        score += 2.0
        reasons.append("subject=%s" % subject)
    if entity_role and entity_role in (asset.get("compatible_entities") or []):
        score += 1.5
        reasons.append("entity role=%s" % entity_role)
    if features and set(asset.get("compatible_features") or []) & set(features):
        score += 1.0
        reasons.append("feature overlap")
    if asset.get("confirmed"):
        score += 0.5
        reasons.append("human-confirmed")
    return score, reasons, match_kind


def resolve_role(role: str, index: dict, subject: str, entity_role: str,
                 features: set) -> dict:
    """为一个 role 解析绑定。"""
    candidates = []
    for asset in index_assets(index):
        score, reasons, match_kind = candidate_score(asset, role, subject, entity_role, features)
        if score > 0:
            candidates.append({"asset": asset, "score": score, "reasons": reasons,
                               "match_kind": match_kind})
    if not candidates:
        return {"role": role, "asset": None,
                "reason": "no asset matched role %r (aliases: %s)" % (role, _aliases(_base_role(role)))}
    candidates.sort(key=lambda item: (-item["score"], str(item["asset"].get("id"))))
    best = candidates[0]
    asset = best["asset"]

    # 主体保护：声明了主体、但最佳候选是另一个主体化资源（player/enemy/character）
    # 时拒绝绑定——宁可报缺失，也不把「别人的角色资源」当成本实体的资源。
    asset_subject = str(asset.get("subject") or "")
    if (subject and asset_subject and asset_subject != subject
            and str(asset.get("category") or "") in CHARACTER_CATEGORIES):
        return {"role": role, "asset": None,
                "reason": ("no asset for subject %r and role %r (best candidate %s belongs to %r)"
                           % (subject, role, asset.get("id"), asset_subject))}

    # 置信度：精确命中 + 主体一致 = high；别名或主体无关 = medium；主体不一致 = low
    subject_match = (not subject) or asset_subject == subject
    if best["match_kind"] == "exact" and subject_match:
        confidence = "high"
    elif subject_match or not subject:
        confidence = "medium"
    else:
        confidence = "low"

    note = ""
    asset_type = str(asset.get("type") or "")
    if asset_type == "animation":
        frames = asset.get("frames") or []
        if not frames:
            note = "animation group has no frames; node cannot be created"
        else:
            note = ("animation frames have no SpriteFrames resource for role %r; "
                    "binding uses the first frame as a static texture" % role)
    elif asset_type == "spritesheet":
        note = "spritesheet bound as Sprite2D; hframes/vframes come from the .import sidecar"

    return {
        "role": role,
        "asset": asset,
        "score": round(best["score"], 2),
        "confidence": confidence,
        "reasons": best["reasons"],
        "runners_up": [c["asset"].get("id") for c in candidates[1:4]],
        "note": note,
    }


def node_for(role: str, asset: dict) -> dict:
    """资源 -> 场景节点描述（name / type / property / path）。"""
    asset_type = str(asset.get("type") or "")
    mapping = NODE_MAPPING.get(asset_type)
    if mapping is None:
        return {}
    node_type, prop, suffix = mapping
    res = str(asset.get("path") or "")
    if asset_type == "animation":
        frames = asset.get("frames") or []
        res = frames[0] if frames else ""
    if not res:
        return {}
    name = _pascal(asset.get("subject") or _base_role(role)) + _pascal(_base_role(role)) + suffix
    node = {"name": name, "type": node_type, "property": prop, "path": res}
    if asset_type == "spritesheet":
        sidecar = asset.get("import_sidecar") or {}
        if sidecar.get("hframes"):
            node["hframes"] = int(sidecar["hframes"])
        if sidecar.get("vframes"):
            node["vframes"] = int(sidecar["vframes"])
    return node


def consolidate_nodes(bindings: list[dict], index: dict | None = None) -> None:
    """合并指向同一资源的节点。

    一个 SpriteFrames 常常同时提供 idle/move/attack/hurt：若每个角色都生成一个
    AnimatedSprite2D，场景里会出现多个完全相同的节点。因此按 (节点类型, 资源路径)
    合并：
        - 单角色：保持角色化节点名，并记录 roles/animation；
        - 多角色：合并为一个共享节点（如 SlimeAnim），记录 roles 与主 animation；
        - 播放哪一段由 Gameplay 决定（Scene 只连接资源，不写行为）。
    """
    groups: dict[tuple, list[dict]] = {}
    for entry in bindings:
        node = entry.get("node") or {}
        if not node.get("type") or not node.get("path"):
            continue
        groups.setdefault((node["type"], node["path"]), []).append(entry)

    for (node_type, _path), entries in groups.items():
        roles = [str(entry.get("role") or "") for entry in entries]
        for entry in entries:
            node = entry["node"]
            node["roles"] = list(roles)
            if node_type == "AnimatedSprite2D":
                node["animation"] = roles[0]
        if len(entries) < 2:
            continue
        first = entries[0]["node"]
        subject = ""
        for entry in entries:
            asset = find_asset(index or {}, str(entry.get("asset") or "")) or {}
            subject = str(asset.get("subject") or "")
            if subject:
                break
        shared = dict(first)
        shared.update({
            "name": _pascal(subject or _base_role(roles[0])) + NODE_SUFFIX.get(node_type, "Node"),
            "roles": list(roles),
            "merged_from": [entry.get("asset") for entry in entries],
        })
        for entry in entries:
            # 每个绑定一份独立副本：避免 YAML 输出共享引用（anchor/alias 噪声）
            entry["node"] = dict(shared)
            entry["node"]["roles"] = list(shared.get("roles") or [])
            entry["node"]["merged_from"] = list(shared.get("merged_from") or [])


def feature_provides(project_root: Path, feature_id: str, feature_records: list[dict]) -> set:
    """成员 Feature 的能力标签：优先 feature_index.json，其次 Features/<id>/feature.yaml。"""
    for feature in feature_records:
        if feature.get("id") == feature_id:
            return set(feature.get("provides") or [])
    feature_file = project_root / "Features" / feature_id / "feature.yaml"
    if feature_file.is_file():
        try:
            data = yaml.safe_load(feature_file.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        if isinstance(data, dict):
            return set(data.get("provides") or [])
    return set()


def feature_for_role(role: str, entity_features: list, feature_index: list[dict],
                     project_root: Path | None = None) -> str:
    """由能力提示推断该 role 属于哪个成员 Feature（推不出则空串）。"""
    hints = ROLE_CAPABILITY_HINTS.get(_base_role(role), set())
    if not hints:
        return ""
    for feature_id in sorted(entity_features):
        provides = feature_provides(project_root or DEFAULT_PROJECT_ROOT, feature_id, feature_index)
        if provides & hints:
            return feature_id
    return ""


def bind_entity(entity_id: str, entity_role: str, features: list, index: dict,
                project_root: Path, declared: dict | None = None,
                explicit: dict | None = None, scoped: dict | None = None,
                multi_entity: bool = False) -> dict:
    """为单个实体解析绑定。declared 为 blueprint 的 assets 节。

    explicit —— 角色级显式绑定（历史格式，作用于全部实体）；
    scoped   —— 本实体的实体作用域显式绑定（Phase 1.15，I1）：
                实体作用域 > 角色级 > 索引推断。
    blueprint 的 assets.bindings 经同一严格解析（非法条目进 binding_errors，不静默跳过）。
    """
    declared = declared if isinstance(declared, dict) else {}
    global_explicit = dict(explicit or {})
    declared_global, declared_scoped, declared_errors = parse_explicit_bindings(
        declared.get("bindings") or [], source="assets.bindings", owner_entity=entity_id)
    for role, asset_id in declared_global.items():
        global_explicit.setdefault(role, asset_id)
    scoped = dict(scoped or {})
    for role, asset_id in (declared_scoped.get(entity_id) or {}).items():
        scoped.setdefault(role, asset_id)
    binding_errors: list[dict] = list(declared_errors)

    subject = str(declared.get("subject") or "").strip().lower()
    explicit_roles = bool(declared.get("required"))
    required_roles = [str(r) for r in (declared.get("required") or [])] or entity_required_roles(entity_role)
    optional_roles = [str(r) for r in (declared.get("optional") or [])]
    if not optional_roles and not explicit_roles:
        # 蓝图显式声明了 required 时，角色集合完全由蓝图决定；否则用实体角色的默认槽位。
        optional_roles = list(OPTIONAL_ROLES)

    feature_index = read_json(project_root / ".ai/context/feature_index.json", {})
    feature_records = (feature_index or {}).get("features", []) if isinstance(feature_index, dict) else []

    bindings: list[dict] = []
    missing: list[dict] = []
    optional_missing: list[dict] = []

    def record_missing(role: str, reason: str) -> None:
        if any(item["role"] == role for item in missing) \
                or any(item["role"] == role for item in optional_missing):
            return
        kind = "required" if role in required_roles else "optional"
        item = {"role": role, "kind": kind, "reason": reason}
        (missing if kind == "required" else optional_missing).append(item)

    def resolve_explicit(role: str):
        """显式绑定查找（Phase 1.15，I1）：实体作用域 > 角色级。

        返回 (asset_id, scope_note, is_scoped) 或 None。
        """
        if role in scoped:
            return scoped[role], "entity-scoped explicit binding", True
        if role in global_explicit:
            note = "role-level explicit binding (no entity scope)"
            if multi_entity:
                note += " applied to entity %s" % entity_id
            return global_explicit[role], note, False
        return None

    def resolved_explicit(role: str, hit) -> dict | None:
        """显式命中 -> 绑定候选。未知资产 / 类型不匹配记入 missing（不回退推断）。"""
        asset_id, scope_note, is_scoped = hit
        asset = find_asset(index, asset_id)
        if asset is None:
            record_missing(role, "explicit binding references unknown asset: %s" % asset_id)
            return None
        mismatch = explicit_type_mismatch(role, asset)
        if mismatch:
            record_missing(role, mismatch)
            return None
        return {"role": role, "asset": asset, "score": None, "confidence": "high",
                "reasons": ["explicit binding" + (" (entity-scoped)" if is_scoped else "")],
                "runners_up": [], "note": "",
                "scope_note": scope_note,
                "resolved_from": "binding"}

    def resolve(role: str) -> dict | None:
        # 显式绑定优先于一切推断（Phase 1.7-H 十五节：优先级链头）。
        hit = resolve_explicit(role)
        if hit is not None:
            return resolved_explicit(role, hit)

        # 方向解析：role 可能带方向语义（idle_down / move_left / run_up_right 等）。
        # 优先级（十七节任务 4）：
        #   direction-specific asset（move_left）> generic（move）> texture 退化。
        # fallback 必须写进 note（禁止静默降级）。
        base, direction = split_direction_role(role)
        if direction:
            for role_prefix in ("%s_%s" % (base, direction), base):
                hit = resolve_explicit(role_prefix)
                if hit is not None:
                    resolved = resolved_explicit(role, hit)
                    if resolved is not None and role_prefix != role:
                        resolved["note"] = ("explicit binding %r used for directional role %r"
                                            % (role_prefix, role))
                    return resolved
            # direction-specific 索引优先；generic（无方向）作为 fallback。
            specific = resolve_role(role, index, subject, entity_role, set(features))
            if specific.get("asset") is not None:
                specific["resolved_from"] = "index"
                if specific.get("direction") != direction:
                    specific["note"] = " ".join(filter(None, [
                        specific.get("note") or "",
                        "direction-aware binding for %r" % role]))
                return specific
            generic = resolve_role(base, index, subject, entity_role, set(features))
            if generic.get("asset") is not None:
                generic["role"] = role
                generic["resolved_from"] = "index"
                generic["note"] = " ".join(filter(None, [
                    generic.get("note") or "",
                    "directional role %r falls back to generic asset %r (no %s asset)"
                    % (role, generic["asset"].get("id"), role)]))
                generic["fallback_from"] = base
                return generic
            record_missing(role, str(specific.get("reason") or
                                     "no asset matched directional role %r" % role))
            return None

        result = resolve_role(role, index, subject, entity_role, set(features))
        if result.get("asset") is None:
            record_missing(role, str(result.get("reason") or "no asset matched role %r" % role))
            return None
        result["resolved_from"] = "index"
        return result

    for role in required_roles:
        resolved = resolve(role)
        if resolved is None:
            record_missing(role, "no asset matched role %r" % role)
            continue
        bindings.append(_binding_entry(resolved, role, features, feature_records, entity_role,
                                       project_root, index))

    for role in optional_roles:
        resolved = resolve(role)
        if resolved is None:
            record_missing(role, "no optional asset for role %r" % role)
            continue
        bindings.append(_binding_entry(resolved, role, features, feature_records, entity_role,
                                       project_root, index))

    consolidate_nodes(bindings, index)

    return {
        "entity": entity_id,
        "role": entity_role,
        "subject": subject,
        "features": sorted(features),
        "required_declared": explicit_roles,
        "bindings": bindings,
        "missing": missing,
        "optional_missing": optional_missing,
        "binding_errors": binding_errors,
    }


def _binding_entry(resolved: dict, role: str, features: list[str],
                   feature_records: list[dict], entity_role: str,
                   project_root: Path | None = None, index: dict | None = None) -> dict:
    asset = resolved["asset"]
    node = node_for(role, asset)
    feature_id = feature_for_role(role, features, feature_records, project_root)
    entry = {
        "feature": feature_id,
        "role": role,
        "asset": asset.get("id"),
        "path": asset.get("path"),
        "type": asset.get("type"),
        "node": node,
        "compatibility": _compat_level(asset, entity_role, feature_id, feature_records,
                                       project_root, index, role),
        "resolved_from": resolved.get("resolved_from", "index"),
        "confidence": resolved.get("confidence", "medium"),
    }
    if resolved.get("note"):
        entry["note"] = resolved["note"]
    if resolved.get("scope_note"):
        entry["note"] = " ".join(filter(None, [entry.get("note") or "", resolved["scope_note"]]))
    if resolved.get("runners_up"):
        entry["runners_up"] = resolved["runners_up"]
    return entry


def _compat_level(asset: dict, entity_role: str, feature_id: str,
                  feature_records: list[dict], project_root: Path | None,
                  index: dict | None, role: str = "") -> str:
    """兼容性等级复用 check_compatibility 的判定（单一事实来源，避免两套规则）。"""
    from check_compatibility import UNKNOWN, compatibility, load_feature

    if not asset:
        return UNKNOWN
    feature = None
    if feature_id:
        for record in feature_records:
            if record.get("id") == feature_id:
                feature = record
                break
        if feature is None and project_root is not None:
            feature = load_feature(project_root, feature_id)
    return compatibility(index or {}, asset, feature, entity_role, role)["level"]


# 绑定文档实例版本（随 asset_binding_schema.yaml 版本走；Phase 1.7.9 起写入产物）
BINDING_SCHEMA_VERSION = 2


def bind_gameplay(blueprint: dict, index: dict, project_root: Path,
                  explicit: dict | None = None, scoped_bindings: dict | None = None,
                  binding_errors: list | None = None,
                  binding_source: str = "<binding>") -> dict:
    """Gameplay Blueprint -> 每实体绑定集合（含 entity 作用域解析，Phase 1.15 I1）。

    scoped_bindings: {entity_id: {role: asset_id}} —— 实体作用域显式绑定；
    作用域指向不存在实体的条目记入 binding.binding_scope_errors（可定位，
    location 携带 binding_source），绝不静默应用到其他实体。
    binding_errors 为解析层（结构非法）错误的预收集。
    """
    entities = blueprint.get("entities") or {}
    entity_ids = {entity_id for entity_id, entry in entities.items() if isinstance(entry, dict)}
    multi = sum(1 for entry in entities.values() if isinstance(entry, dict)) > 1
    results = []
    scope_errors: list[dict] = list(binding_errors or [])
    scoped_bindings = dict(scoped_bindings or {})
    for entity_id in sorted(set(scoped_bindings) - entity_ids):
        for role, asset_id in sorted(scoped_bindings[entity_id].items()):
            scope_errors.append({
                "location": "%s:entity=%s" % (binding_source, entity_id),
                "entity": entity_id, "role": role,
                "reason": ("explicit binding scoped to unknown entity %r "
                           "(blueprint entities: %s)" % (entity_id, ", ".join(sorted(entity_ids)) or "<none>")),
            })
    for entity_id, entry in entities.items():
        if not isinstance(entry, dict):
            continue
        declared = entry.get("assets") if isinstance(entry.get("assets"), dict) else {}
        block = bind_entity(
            entity_id,
            str(entry.get("role") or "entity"),
            [str(f) for f in entry.get("features") or []],
            index, project_root, declared=declared, explicit=explicit,
            scoped=scoped_bindings.get(entity_id) or {}, multi_entity=multi,
        )
        scope_errors.extend(block.pop("binding_errors") or [])
        results.append(block)
    return {
        "schema_version": BINDING_SCHEMA_VERSION,
        "binding": {
            "source": "gameplay_blueprint",
            "gameplay": (blueprint.get("gameplay") or {}).get("id", ""),
            "entities": results,
            "binding_scope_errors": scope_errors,
        }
    }


def load_blueprint(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit("FAIL: blueprint must be a YAML mapping: %s" % path)
    return data


def print_report(doc: dict) -> None:
    block = doc["binding"]
    print("Asset Binding")
    print("Source: %s" % block.get("source"))
    print()
    entities = block.get("entities") or []

    def show(entity: dict) -> None:
        print("Entity: %s (role=%s, subject=%s)" % (entity["entity"], entity["role"],
                                                    entity.get("subject") or "-"))
        for entry in entity["bindings"]:
            print("  %-10s -> %-22s %-14s %s" % (
                entry["role"], entry["asset"], entry["type"],
                (entry.get("node") or {}).get("name") or "<no node>"))
            print("             feature=%s confidence=%s compatibility=%s"
                  % (entry.get("feature") or "-", entry["confidence"], entry["compatibility"]))
            if entry.get("note"):
                print("             note: %s" % entry["note"])
        for item in entity.get("missing") or []:
            print("  MISSING   %-10s %s" % (item["role"], item["reason"]))
        for item in entity.get("optional_missing") or []:
            print("  optional  %-10s %s" % (item["role"], item["reason"]))

    if "entity" in block:
        show(block)
    else:
        for entity in entities:
            show(entity)
            print()
    for item in block.get("binding_scope_errors") or []:
        print("  SCOPE ERROR %-12s %-10s %s"
              % (item.get("entity") or "-", item.get("role") or "-", item["reason"]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bind entity asset roles to concrete assets.")
    parser.add_argument("--entity", default="", help="Entity Blueprint yaml path")
    parser.add_argument("--gameplay", default="", help="Gameplay Blueprint yaml path")
    parser.add_argument("--binding", default="", help="Explicit binding override yaml path")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--index", default="")
    parser.add_argument("--out", default="", help="Write the binding document to this path")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when a required role is missing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.entity and not args.gameplay:
        print("FAIL: provide --entity or --gameplay")
        return 2

    project = Path(args.project).resolve()
    index = load_index(args.index or None, project_root=project)
    if not index_assets(index):
        print("FAIL: asset index is empty or missing for %s" % project)
        print("Run: python .ai/tools/asset_registry/build_asset_index.py --project .")
        return 2

    explicit: dict[str, str] = {}
    scoped_bindings: dict[str, dict[str, str]] = {}
    binding_errors: list[dict] = []
    if args.binding:
        data = load_blueprint(Path(args.binding))
        explicit, scoped_bindings, binding_errors = parse_explicit_bindings(
            data.get("bindings") or data.get("asset_bindings") or [],
            source=str(args.binding))

    if args.gameplay:
        doc = bind_gameplay(load_blueprint(Path(args.gameplay)), index, project, explicit,
                            scoped_bindings=scoped_bindings, binding_errors=binding_errors,
                            binding_source=str(args.binding))
        entities = doc["binding"]["entities"]
    else:
        raw = load_blueprint(Path(args.entity))
        entity = raw.get("entity") or {}
        declared = raw.get("assets") if isinstance(raw.get("assets"), dict) else {}
        entity_id = str(entity.get("id") or raw.get("id") or Path(args.entity).stem)
        entity_role = str(entity.get("role") or declared.get("role") or "entity")
        # 单实体模式：作用域必须指向本实体，指向其他实体的条目记为作用域错误（I1-D）
        own_scoped = scoped_bindings.get(entity_id) or {}
        for other_entity in sorted(set(scoped_bindings) - {entity_id}):
            for role in sorted(scoped_bindings[other_entity]):
                binding_errors.append({
                    "location": str(args.binding), "entity": other_entity, "role": role,
                    "reason": ("explicit binding scoped to entity %r in a single-entity run "
                               "for %r" % (other_entity, entity_id))})
        entity_block = bind_entity(entity_id, entity_role,
                                   [str(f) for f in raw.get("features") or []],
                                   index, project, declared=declared, explicit=explicit,
                                   scoped=own_scoped)
        doc = {"schema_version": BINDING_SCHEMA_VERSION,
               "binding": dict(entity_block, source="entity_blueprint",
                               binding_scope_errors=binding_errors)}
        entities = [entity_block]

    if args.out:
        Path(args.out).write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096), encoding="utf-8")
        print("Binding written: %s" % args.out)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(doc)

    missing_required = [item for entity in entities for item in entity.get("missing") or []]
    if missing_required:
        print()
        print("Missing required asset roles: %d" % len(missing_required))
        for item in missing_required:
            print("  - %s" % item["reason"])
    # 实体作用域错误（Phase 1.15，I1）：显式无效的绑定必须明确失败（exit 1），
    # 但仍写出带 binding_scope_errors 的文档供定位（不静默吞掉）。
    scope_errors = doc["binding"].get("binding_scope_errors") or []
    if scope_errors:
        print()
        print("Binding scope errors: %d" % len(scope_errors))
        for item in scope_errors:
            print("  - [%s] entity=%s role=%s: %s"
                  % (item.get("location") or "<binding>", item.get("entity") or "-",
                     item.get("role") or "-", item["reason"]))
        return 1
    return 1 if (missing_required and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
