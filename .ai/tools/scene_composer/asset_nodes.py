#!/usr/bin/env python3
"""Asset Nodes —— Asset Binding -> 场景资源节点（Scene Composer 的资源侧接口）。

    Entity Blueprint + Asset Binding
        ↓
    resource_nodes（{name, type, property, path, ext_type, hframes?, vframes?}）
        ↓
    scene_builder.build_tscn  ->  AnimatedSprite2D / Sprite2D / AudioStreamPlayer 节点

职责边界（架构约束）：
    - Scene Composer 负责「实例化与连接资源」，不创造新的 Gameplay State；
    - 资源发现与绑定由 Asset Registry 负责（.ai/tools/asset_registry/bind_assets.py），
      本模块只读绑定计划，不扫描目录、不推断资产、不修改资源文件；
    - 绑定缺失只降级为 warning（并记录在 info 中），不阻断场景生成。

契约：.ai/context/asset_binding_schema.yaml
"""

import json
import os
import re
import sys

_TOOL_DOTAI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .ai
PROJECT_ROOT = os.path.dirname(_TOOL_DOTAI)
ASSET_REGISTRY_DIR = os.path.join(_TOOL_DOTAI, "tools", "asset_registry")
DEFAULT_BINDING_DIR = os.path.join(_TOOL_DOTAI, "context", "asset_bindings")

# 扩展名 -> Godot ext_resource 类型（.tres 由资源头解析）
EXT_RESOURCE_TYPES = {
    ".png": "Texture2D",
    ".jpg": "Texture2D",
    ".jpeg": "Texture2D",
    ".webp": "Texture2D",
    ".bmp": "Texture2D",
    ".svg": "Texture2D",
    ".wav": "AudioStreamWAV",
    ".ogg": "AudioStreamOggVorbis",
    ".mp3": "AudioStreamMP3",
    ".flac": "AudioStreamFLAC",
    ".ttf": "FontFile",
    ".otf": "FontFile",
    ".gdshader": "Shader",
}

ASSET_NODE_TYPES = {"AnimatedSprite2D", "Sprite2D", "AudioStreamPlayer",
                    "AudioStreamPlayer2D", "TextureRect", "Sprite3D", "TileMapLayer"}

# Godot 4.3+ TileMap 已 deprecated；本项目 4.7 一律使用 TileMapLayer + tile_set。
# （Phase 1.7-H 任务 3：只连接 TileSet 资源，不生成关卡数据 tile_map_data。）
TILEMAP_LAYER_NODE_TYPE = "TileMapLayer"

# Godot 4.3+ TileMap 已 deprecated，本项目 4.7 一律使用 TileMapLayer + tile_set。
# （契约：Phase 1.7-H 任务 3——只连接 TileSet 资源，不生成关卡数据。）
TILEMAP_LAYER_NODE_TYPE = "TileMapLayer"

_TEXT_RESOURCE_TYPE_RE = re.compile(r'^\[gd_resource[^\]]*type="([^"]+)"', re.M)


def resource_ext_type(res_path: str) -> str:
    """res:// 资源路径 -> ext_resource 的 type 字段。

    .tres/.res 读资源头声明的类型（SpriteFrames / TileSet / ...）；
    导入型资源（png/wav...）用扩展名映射（Godot 导入后的实际资源类型）。
    """
    path = str(res_path or "")
    ext = os.path.splitext(path.rstrip("/"))[1].lower()
    if ext in (".tres", ".tscn", ".escn"):
        disk = disk_path(path)
        if disk and os.path.isfile(disk):
            try:
                text = open(disk, encoding="utf-8", errors="replace").read(4096)
            except OSError:
                text = ""
            match = _TEXT_RESOURCE_TYPE_RE.search(text)
            if match:
                return match.group(1)
        return "Resource"
    return EXT_RESOURCE_TYPES.get(ext, "Resource")


def disk_path(res_path: str):
    """res:// 路径 -> 磁盘绝对路径（非 res:// 返回 None）。"""
    path = str(res_path or "")
    if not path.startswith("res://"):
        return None
    return os.path.join(PROJECT_ROOT, path[len("res://"):].replace("/", os.sep))


def load_binding_doc(path: str) -> dict:
    """读取 Asset Binding 文档（.ai/context/asset_binding_schema.yaml）。"""
    import yaml

    if not os.path.isfile(path):
        raise SystemExit("FAIL: Asset binding file not found: %s" % path)
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("binding"), dict):
        raise SystemExit("FAIL: Invalid asset binding document (missing 'binding:'): %s" % path)
    return data


def binding_entities(doc: dict) -> list:
    """绑定文档 -> 实体绑定列表（单实体 / gameplay 双形态统一）。"""
    binding = (doc or {}).get("binding") or {}
    if isinstance(binding.get("entities"), list):
        return [entry for entry in binding["entities"] if isinstance(entry, dict)]
    if binding.get("bindings") is not None:
        return [binding]
    return []


def entity_for(entities: list, entity_id: str) -> dict:
    """按 entity id（或 scene/roots 名）挑选实体绑定；找不到时退回第一个。"""
    wanted = (entity_id or "").strip().lower()
    for entry in entities:
        if str(entry.get("entity") or "").strip().lower() == wanted:
            return entry
    return entities[0] if entities else {}


def nodes_from_entity(entity: dict) -> tuple:
    """单个实体绑定 -> (resource_nodes, warnings)。

    多个角色指向同一资源时只生成一个节点（合并，见 bind_assets.consolidate_nodes）；
    节点记下 roles 与主 animation，具体播放哪一段由 Gameplay 决定。
    """
    nodes, warnings = [], []
    seen: dict[str, dict] = {}
    for entry in entity.get("bindings") or []:
        node = entry.get("node") if isinstance(entry.get("node"), dict) else {}
        name = str(node.get("name") or "").strip()
        ntype = str(node.get("type") or "").strip()
        path = str(node.get("path") or "").strip()
        property_name = str(node.get("property") or "").strip()
        if not (name and ntype and path and property_name):
            continue
        if ntype not in ASSET_NODE_TYPES:
            warnings.append("Unsupported asset node type %r for binding %r" % (ntype, entry.get("role")))
            continue
        if name in seen:
            existing = seen[name]
            roles = list(existing.get("roles") or [])
            role = entry.get("role") or ""
            if role and role not in roles:
                roles.append(role)
            existing["roles"] = roles
            continue
        if not path.startswith("res://"):
            warnings.append("Binding %r path is not res://: %s" % (entry.get("role"), path))
            continue
        disk = disk_path(path)
        if disk is None or not os.path.exists(disk):
            warnings.append("Binding %r resource missing on disk: %s" % (entry.get("role"), path))
            continue
        node_entry = {
            "name": name,
            "type": ntype,
            "property": property_name,
            "path": path,
            "ext_type": resource_ext_type(path),
            "role": entry.get("role") or "",
            "roles": list(node.get("roles") or [entry.get("role") or ""]),
            "asset": entry.get("asset") or "",
        }
        for key in ("animation",):
            if node.get(key):
                node_entry[key] = str(node[key])
        if node.get("hframes"):
            node_entry["hframes"] = int(node["hframes"])
        if node.get("vframes"):
            node_entry["vframes"] = int(node["vframes"])
        seen[name] = node_entry
        nodes.append(node_entry)
    return nodes, warnings


def nodes_from_doc(doc: dict, entity_id: str = "") -> tuple:
    """绑定文档 -> (resource_nodes, warnings)（多实体时按 entity id 选择）。"""
    entities = binding_entities(doc)
    if not entities:
        return [], ["Asset binding document has no entity bindings"]
    entity = entity_for(entities, entity_id)
    return nodes_from_entity(entity)


def resolve_binding_doc(blueprint_raw: dict, out_path: str = "") -> dict:
    """调用 Asset Registry 解析绑定（Entity / Gameplay Blueprint 都支持）。

    返回绑定文档；同时写入 out_path（默认 .ai/context/asset_bindings/<id>.yaml），
    以保持「绑定计划可复现、可人工审阅」。
    """
    if ASSET_REGISTRY_DIR not in sys.path:
        sys.path.insert(0, ASSET_REGISTRY_DIR)
    import yaml                                     # noqa: E402
    import bind_assets                              # noqa: E402
    from asset_metadata import load_index           # noqa: E402

    index = load_index(project_root=PROJECT_ROOT)
    if not bind_assets.index_assets(index):
        raise SystemExit("FAIL: asset index is empty: run "
                         "python .ai/tools/asset_registry/build_asset_index.py")

    features = [str(f) for f in (blueprint_raw.get("features") or [])]
    declared = blueprint_raw.get("assets") if isinstance(blueprint_raw.get("assets"), dict) else {}
    entity = blueprint_raw.get("entity") or {}
    entity_id = str(entity.get("id") or blueprint_raw.get("id") or "entity")
    entity_role = str(entity.get("role") or declared.get("role") or "entity")

    from pathlib import Path                         # noqa: E402
    entity_block = bind_assets.bind_entity(entity_id, entity_role, features, index,
                                           Path(PROJECT_ROOT), declared=declared)
    doc = {"schema_version": bind_assets.BINDING_SCHEMA_VERSION,
           "binding": dict(entity_block, source="entity_blueprint")}

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=4096))
    return doc


def blueprint_index(blueprint_raw: dict) -> str:
    """从蓝图推导请求实体 id（用于多实体绑定文档中选择条目）。"""
    entity = blueprint_raw.get("entity") or {}
    scene = blueprint_raw.get("scene") or {}
    root = blueprint_raw.get("root") or {}
    return str(entity.get("id") or scene.get("id") or root.get("name")
               or blueprint_raw.get("id") or "")


def nodes_for_blueprint(blueprint_raw: dict, bindings_path: str = "",
                        bind_assets: bool = False,
                        out_path: str = "") -> tuple:
    """便捷入口：绑定文档 -> resource_nodes。返回 (nodes, info)。

    info = {bindings_path, resolved, warnings, missing}
    """
    info = {"bindings_path": "", "resolved": False, "warnings": [], "missing": []}
    resource_nodes = []

    doc = None
    if bindings_path:
        doc = load_binding_doc(bindings_path)
        info["bindings_path"] = bindings_path
    elif bind_assets:
        target = out_path or os.path.join(DEFAULT_BINDING_DIR,
                                          "%s.yaml" % (blueprint_index(blueprint_raw) or "entity"))
        doc = resolve_binding_doc(blueprint_raw, target)
        info["bindings_path"] = target
        info["resolved"] = True
    if doc is None:
        return resource_nodes, info

    entities = binding_entities(doc)
    entity = entity_for(entities, blueprint_index(blueprint_raw))
    nodes, warnings = nodes_from_entity(entity)
    info["warnings"] = warnings
    info["missing"] = [item.get("reason", "") for item in (entity.get("missing") or [])]
    return nodes, info
