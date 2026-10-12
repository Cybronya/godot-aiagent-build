#!/usr/bin/env python3
"""Asset Metadata —— Asset Registry 的核心元数据层。

职责（只做「事实抽取 + 确定性推导」，不做视觉识别、不做运行期管理）：

    - 从路径 / 文件名 / 目录结构 / 扩展名判断资源类型（type）与使用类别（category）
    - 解析 Godot 资源文本（.tres/.tscn）得到资源类型、依赖、动画名
    - 解析 .import 旁车得到 Godot 导入事实（hframes / vframes / loop）
    - 读取图片尺寸、音频时长（纯标准库，不依赖 Pillow）
    - animation 组聚合（同一动作目录的帧 -> 一条 animation 元数据）
    - 从 .ai/context/asset_manifest.json 的人工确认层合并 confirmed 语义
    - 计算 used_by / compatible_features / compatible_entities / compatible_scenes
    - asset_index.json 的读写（Generated Cache）

契约：.ai/context/asset_schema.yaml
复用：检测词表与人工确认流程沿用既有 `.ai/tools/godot-art-assets/`（不重复实现确认流程）。

不负责：查询排序（query_assets.py）、兼容性判定（check_compatibility.py）、
绑定（bind_assets.py）、校验（.ai/tools/validator/check_assets.py）。
"""

from __future__ import annotations

import json
import os
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # 可选依赖：仅人工确认层（yaml manifest）需要
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None

DOTAI_DIR = Path(__file__).resolve().parents[2]          # .ai
DEFAULT_PROJECT_ROOT = DOTAI_DIR.parent

INDEX_PATH_NAME = ".ai/context/asset_index.json"
MANIFEST_PATH_NAME = ".ai/context/asset_manifest.yaml"      # 人工确认层（受控格式）
MANIFEST_JSON_PATH_NAME = ".ai/context/asset_manifest.json"  # 既有 godot-art-assets 确认产物

# ---------- 支持的资源类型 ----------

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tga", ".svg"}
AUDIO_EXTS = {".wav", ".ogg", ".mp3", ".flac"}
FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2", ".fnt"}
SHADER_EXTS = {".gdshader", ".gdshaderinc", ".shader"}
TEXT_RESOURCE_EXTS = {".tres", ".tscn", ".escn"}
BINARY_RESOURCE_EXTS = {".res", ".scn"}
SCENE_EXT = {".tscn", ".scn", ".escn"}
ALL_ASSET_EXTS = (IMAGE_EXTS | AUDIO_EXTS | FONT_EXTS | SHADER_EXTS
                  | TEXT_RESOURCE_EXTS | BINARY_RESOURCE_EXTS)

# 默认扫描根（按存在性筛选；可用 --root 追加/覆盖）
DEFAULT_ASSET_ROOTS = ("assets", "Assets", "resources", "Resources",
                       "Audio", "Textures", "Sprites", "Animations", "Tilesets")

IGNORED_DIR_NAMES = {".git", ".godot", ".import", "__pycache__", "addons",
                     "node_modules", ".freebuff"}

# 路径类型别名（沿用 godot-art-assets 的分类词表）
TYPE_ALIASES = {
    "characters": "character", "character": "character",
    "environments": "environment", "environment": "environment",
    "tilesets": "tileset", "tileset": "tileset",
    "backgrounds": "background", "background": "background",
    "props": "prop", "prop": "prop",
    "items": "item", "item": "item",
    "weapons": "weapon", "weapon": "weapon",
    "vfx": "effect", "effects": "effect", "effect": "effect",
    "ui": "ui", "portraits": "portrait", "portrait": "portrait",
    "fonts": "font", "font": "font",
}

# 类别（category）词表：
#   路径段 -> 使用类别；enemy/player 优先于泛化的 character
CATEGORY_ALIASES = {
    "enemies": "enemy", "enemy": "enemy", "monster": "enemy", "monsters": "enemy",
    "boss": "enemy", "bosses": "enemy",
    "player": "player", "players": "player",
    "ui": "ui", "hud": "ui", "menu": "ui",
    "audio": "audio", "sfx": "audio", "sound": "audio", "sounds": "audio",
    "music": "audio", "voice": "audio",
    "environments": "environment", "environment": "environment",
    "backgrounds": "background", "background": "background",
    "tilesets": "environment", "tileset": "environment",
    "props": "environment", "prop": "environment",
    "items": "item", "item": "item",
    "weapons": "weapon", "weapon": "weapon",
    "vfx": "effect", "effects": "effect", "effect": "effect",
}

# 动作词（role 候选）；沿用 godot-art-assets 的 ACTION_TOKENS 并补充用途词
ACTION_TOKENS = {
    "idle", "walk", "run", "move", "attack", "hit", "hurt", "damage", "death",
    "die", "jump", "fall", "dash", "cast", "shoot", "thrust", "open", "close",
    "use", "equip", "unequip", "block", "roll", "climb", "swim", "interact",
    "spawn", "land", "stun", "heal", "pickup", "collect", "victory", "defeat",
}

DIRECTION_TOKENS = {"up", "down", "left", "right", "up_left", "up_right",
                    "down_left", "down_right", "north", "south", "east", "west"}

# 主体名词（subject）：角色 / 生物 / 载具等；不含动作词
SUBJECT_KEYWORDS = {
    "player", "slime", "bat", "goblin", "orc", "skeleton", "zombie", "wolf",
    "spider", "snake", "ghost", "knight", "mage", "archer", "guard", "npc",
    "merchant", "boss", "enemy", "monster", "turret", "drone", "spike", "trap",
    "coin", "gem", "potion", "key", "chest", "door", "platform", "crate",
}

# 兼容性推导：role -> 需要该资源的能力标签（用于过滤 compatible_features）
ROLE_CAPABILITY_HINTS = {
    "move": {"character_movement", "input_driven_movement", "chase_behavior",
             "platform_transport"},
    "run": {"input_driven_movement", "character_movement"},
    "walk": {"character_movement", "input_driven_movement"},
    "idle": set(),
    "attack": {"damage_source", "attack_action", "projectile_source"},
    "cast": {"damage_source", "projectile_source"},
    "shoot": {"projectile_source", "damage_source"},
    "hurt": {"damage_receiver", "health_state"},
    "hit": {"damage_receiver", "health_state"},
    "death": {"death_event"},
    "die": {"death_event"},
    "heal": {"heal_receiver", "heal_source"},
    "pickup": {"collect_event"},
    "collect": {"collect_event"},
    "sfx": set(),
}

# category -> entity role（entity_roles 词表）；character 同时属于 player/enemy
CATEGORY_TO_ENTITY_ROLE = {
    "player": "player",
    "enemy": "enemy",
    "character": None,      # 泛化角色资源：不限定主体角色
    "environment": None,
    "background": None,
    "ui": None,
    "audio": None,
    "effect": None,
    "item": None,
    "weapon": None,
    "unknown": None,
}

# 资源内部类型 -> Asset type
RESOURCE_TYPE_MAP = {
    "spriteframes": "sprite_frames",
    "animation": "animation",
    "animationlibrary": "animation",
    "tileset": "tileset",
    "shadermaterial": "material",
    "standardmaterial3d": "material",
    "canvasitemmaterial": "material",
    "material": "material",
    "fontfile": "font",
    "fontvariation": "font",
    "audiоstream": "audio",
    "audiostreamwav": "audio",
    "audiostreamoggvorbis": "audio",
    "audiostreammp3": "audio",
    "texture2d": "texture",
    "compressedtexture2d": "texture",
    "atlastexture": "spritesheet",
    "packedscene": "scene",
}

ROLE_ALIASES = {
    "walk": "move",
    "hit": "hurt",
    "damage": "hurt",
    "die": "death",
    "sfx": "sfx",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------- 基础 IO ----------


def read_json(path: str | os.PathLike, default: Any) -> Any:
    p = Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: str | os.PathLike, data: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def read_text(path: str | os.PathLike) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def res_path(project_root: Path, path: Path) -> str:
    try:
        return "res://" + path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def res_ref(path: Path) -> str:
    return "res://" + path.as_posix()


# ---------- 文件头解析（纯标准库） ----------


def image_dimensions(path: Path) -> tuple[int | None, int | None]:
    """读取图片宽高（PNG/GIF/BMP/JPEG/WebP）；不支持或失败返回 (None, None)。"""
    try:
        with open(path, "rb") as handle:
            head = handle.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                width, height = struct.unpack(">II", head[16:24])
                return int(width), int(height)
            if head[:6] in (b"GIF87a", b"GIF89a"):
                width, height = struct.unpack("<HH", head[6:10])
                return int(width), int(height)
            if head[:2] == b"BM":
                width, height = struct.unpack("<ii", head[18:26])
                return abs(int(width)), abs(int(height))
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                chunk = head[12:16]
                if chunk == b"VP8X":
                    width = int.from_bytes(head[24:27], "little") + 1
                    height = int.from_bytes(head[27:30], "little") + 1
                    return width, height
                if chunk == b"VP8 ":
                    width = int.from_bytes(head[26:28], "little") & 0x3FFF
                    height = int.from_bytes(head[28:30], "little") & 0x3FFF
                    return width, height
                return None, None
            if head[:2] == b"\xff\xd8":
                handle.seek(2)
                while True:
                    marker = handle.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        return None, None
                    if marker[1] in (0xC0, 0xC1, 0xC2, 0xC3):
                        data = handle.read(5)
                        if len(data) < 5:
                            return None, None
                        height, width = struct.unpack(">HH", data[1:5])
                        return int(width), int(height)
                    size = handle.read(2)
                    if len(size) < 2:
                        return None, None
                    handle.seek(int.from_bytes(size, "big") - 2, os.SEEK_CUR)
    except (OSError, struct.error, ValueError):
        return None, None
    return None, None


def wav_duration(path: Path) -> float | None:
    """WAV 时长（秒）；无法解析返回 None。"""
    try:
        with open(path, "rb") as handle:
            head = handle.read(64)
            if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                return None
            byte_rate = int.from_bytes(head[28:32], "little")
            size = path.stat().st_size
            if byte_rate <= 0:
                return None
            return round((size - 44) / byte_rate, 4)
    except (OSError, ValueError):
        return None


def parse_import_sidecar(path: Path) -> dict[str, Any]:
    """解析 Godot .import 旁车：把导入事实变成元数据（不做视觉推断）。"""
    sidecar = path.with_name(path.name + ".import")
    if not sidecar.is_file():
        return {}
    text = read_text(sidecar)
    facts: dict[str, Any] = {}
    for key in ("hframes", "vframes", "loop", "loop_mode", "detect_3d", "compress/mode"):
        match = re.search(r"^%s\s*=\s*(.+)$" % re.escape(key), text, re.M)
        if match:
            raw = match.group(1).strip().strip('"')
            if re.fullmatch(r"-?\d+", raw):
                facts[key.split("/")[-1]] = int(raw)
            elif raw in ("true", "false"):
                facts[key.split("/")[-1]] = raw == "true"
            else:
                facts[key.split("/")[-1]] = raw
    return facts


def parse_text_resource(path: Path) -> dict[str, Any]:
    """解析 .tres/.tscn 文本：资源类型、依赖、动画名、帧数、时长。"""
    text = read_text(path)
    info: dict[str, Any] = {"resource_type": "", "dependencies": [], "animations": [],
                            "frame_count": None, "duration": None, "sub_resources": 0}
    type_match = re.search(r'^\[(gd_resource|gd_scene)[^\]]*type="([^"]+)"', text, re.M)
    if type_match:
        info["resource_type"] = type_match.group(2)
    elif text.startswith("[gd_scene"):
        info["resource_type"] = "PackedScene"
    info["dependencies"] = sorted(set(re.findall(r'^\[ext_resource[^\]]*path="([^"]+)"', text, re.M)))
    info["sub_resources"] = len(re.findall(r"^\[sub_resource ", text, re.M))
    # SpriteFrames：动画名使用 `"name": &"idle"`；帧使用 `"texture": ExtResource(...)`
    info["animations"] = list(dict.fromkeys(re.findall(r'"name":\s*&?"([^"]+)"', text)))
    frames = len(re.findall(r'"texture":\s*ExtResource', text))
    if frames:
        info["frame_count"] = frames
    length = re.search(r'^length\s*=\s*([0-9.]+)', text, re.M)
    if length:
        info["duration"] = float(length.group(1))
    return info


# ---------- 类型与语义推导 ----------


def detect_format(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "unknown"


def detect_type(path: Path, resource_info: dict | None = None,
                import_info: dict | None = None) -> str:
    """由扩展名 + Godot 资源声明 + .import 事实判断资源类型。"""
    ext = path.suffix.lower()
    resource_info = resource_info or {}
    import_info = import_info or {}
    if ext in SCENE_EXT:
        return "scene"
    if ext in TEXT_RESOURCE_EXTS or ext in BINARY_RESOURCE_EXTS:
        declared = str(resource_info.get("resource_type") or "").lower()
        if declared in RESOURCE_TYPE_MAP:
            mapped = RESOURCE_TYPE_MAP[declared]
            return mapped
        if ext in (".tscn", ".escn", ".scn"):
            return "scene"
        return "resource"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in FONT_EXTS:
        return "font"
    if ext in SHADER_EXTS:
        return "shader"
    if ext in IMAGE_EXTS:
        if ext in {".svg"}:
            return "texture"
        hframes = import_info.get("hframes") or 1
        vframes = import_info.get("vframes") or 1
        stem = path.stem.lower()
        if int(hframes) > 1 or int(vframes) > 1 or "spritesheet" in stem or "sheet" in stem.split("_"):
            return "spritesheet"
        return "texture"
    return "unknown"


def split_tokens(name: str) -> list[str]:
    stem = re.sub(r"\.(png|jpg|jpeg|webp|bmp|gif|tga|svg|wav|ogg|mp3|flac|tres|res|tscn|ttf|otf|gdshader)$",
                  "", str(name).lower(), flags=re.I)
    stem = re.sub(r"^(\d+)[_\-\s]*", "", stem)
    stem = re.sub(r"[_\-\s]*(\d+)$", "", stem)
    return [token for token in re.split(r"[_\-\s.]+", stem) if token]


def res_to_role(token: str) -> str:
    return ROLE_ALIASES.get(token, token)


def derive_identity(rel_parts: list[str], path: Path) -> dict[str, Any]:
    """由路径与文件名推导 subject / role / direction / category（无视觉识别）。"""
    parts = [part.lower() for part in rel_parts]
    stem_tokens = split_tokens(path.stem)

    # category：优先角色类目录（enemy/player），其次用途目录，最后类型别名
    category = ""
    for part in parts:
        if part in CATEGORY_ALIASES:
            category = CATEGORY_ALIASES[part]
            if category in ("enemy", "player"):
                break
    if not category:
        for part in parts:
            if part in TYPE_ALIASES:
                category = TYPE_ALIASES[part]
                break
    if not category:
        ext = path.suffix.lower()
        if ext in AUDIO_EXTS:
            category = "audio"
        else:
            category = "unknown"

    # subject：目录或文件名中的主体名词（不取动作词）
    subject = ""
    for token in stem_tokens:
        if token in SUBJECT_KEYWORDS and token not in ACTION_TOKENS:
            subject = token
            break
    if not subject:
        for part in reversed(parts):
            if part in SUBJECT_KEYWORDS and part not in ACTION_TOKENS:
                subject = part
                break

    # role：动作/用途 token（文件名优先，其次目录）
    role = ""
    for token in stem_tokens:
        if token in ACTION_TOKENS:
            role = res_to_role(token)
            break
    if not role:
        for part in reversed(parts):
            if part in ACTION_TOKENS:
                role = res_to_role(part)
                break

    # direction：方向 token
    direction = ""
    joined = "_".join(stem_tokens)
    for token in sorted(DIRECTION_TOKENS, key=len, reverse=True):
        if token in stem_tokens or token in joined or token in parts:
            direction = token
            break

    frame = None
    frame_match = re.search(r"[_\-\s](\d{1,3})$", path.stem)
    if frame_match:
        frame = int(frame_match.group(1))

    return {"subject": subject, "role": role, "direction": direction,
            "category": category, "frame": frame, "tokens": stem_tokens}


def build_tags(identity: dict, asset_type: str, fmt: str, rel_parts: list[str]) -> list[str]:
    tags: list[str] = []

    def add(value: str) -> None:
        if value and value not in tags:
            tags.append(value)

    add(identity.get("category") or "")
    add(identity.get("subject") or "")
    add(identity.get("role") or "")
    add(identity.get("direction") or "")
    add(asset_type)
    add(fmt)
    for part in rel_parts:
        part = part.lower()
        if part in IGNORED_DIR_NAMES or part in ("assets", "resources", "res"):
            continue
        add(part)
    for token in identity.get("tokens") or []:
        add(token)
    return tags


# ---------- 扫描 ----------


def iter_root_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts[:-1]
        if any(part in IGNORED_DIR_NAMES or part.startswith(".") for part in rel_parts):
            continue
        yield path


def scan_file(project_root: Path, path: Path, root: Path) -> dict[str, Any] | None:
    """扫描单个文件 -> Asset Metadata（未确认原始事实）。"""
    ext = path.suffix.lower()
    if ext not in ALL_ASSET_EXTS:
        return None
    resource_info = parse_text_resource(path) if ext in TEXT_RESOURCE_EXTS else {}
    import_info = parse_import_sidecar(path) if ext in IMAGE_EXTS or ext in AUDIO_EXTS else {}
    asset_type = detect_type(path, resource_info, import_info)
    rel_parts = list(path.relative_to(root).parts[:-1])
    identity = derive_identity(rel_parts, path)
    width, height = image_dimensions(path) if ext in IMAGE_EXTS else (None, None)
    duration = wav_duration(path) if ext == ".wav" else None
    if duration is None and resource_info.get("duration") is not None:
        duration = resource_info["duration"]

    frames = resource_info.get("frame_count")
    return {
        "path": res_path(project_root, path),
        "_disk_path": str(path),
        "_tokens": list(identity["tokens"]),          # 内部用（id 推导）；写索引时剔除
        "type": asset_type,
        "format": detect_format(path),
        "category": identity["category"],
        "subject": identity["subject"],
        "role": identity["role"],
        "direction": identity["direction"],
        "frame": identity["frame"],
        "tags": build_tags(identity, asset_type, detect_format(path), rel_parts),
        "dimensions": {"width": width, "height": height},
        "frame_count": frames if frames is not None else (1 if ext in IMAGE_EXTS else None),
        "fps": None,
        "duration": duration,
        "animations": list(resource_info.get("animations") or []),
        "frames": [],
        "dependencies": list(resource_info.get("dependencies") or []),
        "used_by": [],
        "compatible_features": [],
        "compatible_entities": [],
        "compatible_scenes": [],
        "confirmed": False,
        "source": "scanner",
        "import_sidecar": import_info,
    }


def is_animation_dir(name: str) -> bool:
    return name.lower() in ACTION_TOKENS


def group_animations(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把同一动作目录（或同名动作组）的图片帧聚合为一条 animation 元数据。"""
    frames: dict[tuple, list[dict]] = {}
    others: list[dict] = []
    for asset in assets:
        role = asset.get("role") or ""
        # 注意：不能对 res:// 字符串用 os 相关 Path 语义（Windows 会反转分隔符），
        # 统一按 POSIX 文本处理。
        res = str(asset["path"]).rstrip("/")
        dir_name = res.rsplit("/", 1)[-1].lower()
        if asset["type"] in ("texture", "spritesheet") and role and (
                is_animation_dir(dir_name) or asset.get("frame") is not None):
            directory = res.rsplit("/", 1)[0] if "/" in res else ""
            key = (directory, role, asset.get("direction") or "")
            frames.setdefault(key, []).append(asset)
        else:
            others.append(asset)

    grouped: list[dict] = []
    for (directory, role, direction), members in frames.items():
        members.sort(key=lambda item: (item.get("frame") is None, item.get("frame") or 0, item["path"]))
        first = members[0]
        group = dict(first)
        directory_is_action = is_animation_dir(directory.rsplit("/", 1)[-1]) if directory else False
        tags = sorted(set(t for m in members for t in m["tags"]) | {"animation", role})
        group.update({
            "path": directory.rstrip("/") + ("/" if len(members) > 1 or directory_is_action else ""),
            "type": "animation",
            "role": role,
            "direction": direction,
            "frames": [m["path"] for m in members],
            "frame_count": len(members),
            "dimensions": first.get("dimensions"),
            "dependencies": [],
            "tags": tags,
            "import_sidecar": {},
        })
        if len(members) == 1 and not directory_is_action:
            # 单一松散文件且目录不是动作目录：仍作为帧资源保留，但路径指向文件本身
            group["path"] = first["path"]
            group["type"] = first["type"]
        grouped.append(group)
    return others + grouped


def assign_ids(assets: list[dict[str, Any]]) -> None:
    """分配稳定 id；同名冲突组统一追加类型后缀（顺序无关）。

    人工确认层（source=manifest）的 id 优先，不被推断结果覆盖。
    """
    for asset in assets:
        if asset.get("source") == "manifest" and asset.get("id"):
            continue
        subject = asset.get("subject") or ""
        role = asset.get("role") or ""
        direction = asset.get("direction") or ""
        base = "_".join([part for part in (subject, role, direction) if part])
        if not role:
            # 无动作语义的资源：用完整文件名 token（如 player_frames / health_icon），
            # 避免仅用主体名产生「player」这种歧义 id
            tokens = [str(token) for token in (asset.get("_tokens") or asset.get("tokens") or []) if token]
            if tokens:
                base = "_".join(tokens)
        if not base:
            # 无主体/动作语义的资源：退回路径末段名（目录资源取目录名）
            leaf = Path(asset["path"].rstrip("/"))
            stem = leaf.name if leaf.suffix else leaf.name
            base = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        if not base:
            base = "asset"
        if asset.get("frame") is not None and asset.get("type") in ("texture", "spritesheet"):
            base = "%s_f%02d" % (base, int(asset["frame"]))
        asset["id"] = base

    groups: dict[str, list[dict]] = {}
    for asset in assets:
        groups.setdefault(asset["id"], []).append(asset)
    for asset_id, members in groups.items():
        if len(members) < 2:
            continue
        for member in members:
            if member.get("source") == "manifest":
                continue                              # 人工 id 优先，保持原样
            member["id"] = "%s_%s" % (asset_id, member.get("type") or "asset")


# ---------- 引用 / 确认 / 兼容性标注 ----------

REFERENCE_EXTS = TEXT_RESOURCE_EXTS | {".gd"}


def build_reference_map(project_root: Path, extra_dirs: list[Path] | None = None) -> dict[str, list[str]]:
    """扫描项目内文本资源，得到 {被引用路径: [引用者 res:// 路径]}。"""
    references: dict[str, list[str]] = {}
    scan_dirs = [project_root / name for name in ("Scenes", "Features", "Systems", "Tests", "assets", "Assets")]
    scan_dirs.extend(extra_dirs or [])
    for directory in scan_dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in REFERENCE_EXTS:
                continue
            if any(part in IGNORED_DIR_NAMES for part in path.relative_to(directory).parts):
                continue
            text = read_text(path)
            owner = res_path(project_root, path)
            for ref in set(re.findall(r'path="(res://[^"]+)"', text)):
                references.setdefault(ref, [])
                if owner not in references[ref]:
                    references[ref].append(owner)
    return references


def read_yaml_file(path: Path) -> dict[str, Any]:
    if _yaml is None or not path.is_file():
        return {}
    try:
        data = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_manifest(project_root: Path) -> dict[str, Any]:
    """读取人工确认层，合并两种载体：
        - .ai/context/asset_manifest.yaml   受控格式（asset_manifest_schema.yaml）
        - .ai/context/asset_manifest.json   既有 godot-art-assets 确认产物（relative_key/auto/human）
    Source of Truth 永远是资源文件；manifest 只是「人工确认过的语义覆盖层」。
    """
    entries: list[dict[str, Any]] = []
    pending: list[Any] = []

    yaml_data = read_yaml_file(project_root / MANIFEST_PATH_NAME)
    for entry in yaml_data.get("assets") or []:
        if isinstance(entry, dict):
            entries.append(entry)
    pending.extend(yaml_data.get("pending") or [])

    json_data = read_json(project_root / MANIFEST_JSON_PATH_NAME, {})
    if isinstance(json_data, dict):
        for entry in json_data.get("assets") or []:
            if isinstance(entry, dict):
                entries.append(entry)
        pending.extend(json_data.get("pending") or [])

    return {"assets": entries, "pending": pending}


def manifest_human_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """relative_key / auto.path / path -> human 语义块（两种载体统一）。"""
    mapping: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("assets", []) or []:
        if not isinstance(entry, dict):
            continue
        human = entry.get("human") if isinstance(entry.get("human"), dict) else entry
        human = {key: value for key, value in human.items()
                 if key not in ("relative_key", "auto", "human")}
        auto = entry.get("auto") if isinstance(entry.get("auto"), dict) else {}
        for key in (entry.get("relative_key"), entry.get("path"), auto.get("path")):
            if not key:
                continue
            normalized = str(key).replace("\\", "/")
            for variant in (normalized, normalized.replace("res://", "").lstrip("/")):
                mapping[variant] = human
    return mapping


def _human_key(asset: dict[str, Any], project_root: Path) -> list[str]:
    """资产在 manifest 中的候选键（帧路径也参与匹配 animation 组）。"""
    keys = []
    paths = [asset.get("path")] + list(asset.get("frames") or [])
    for path in paths:
        if not path:
            continue
        rel = path.replace("res://", "").rstrip("/")
        keys.append(rel)
        keys.append(rel + "/" if path.endswith("/") else rel)
    return keys


def apply_human_layer(assets: list[dict[str, Any]], project_root: Path) -> int:
    """合并人工确认层：id / category / tags / type / confirmed。"""
    human_map = manifest_human_map(load_manifest(project_root))
    merged = 0
    for asset in assets:
        human = {}
        for key in _human_key(asset, project_root):
            if key in human_map and human_map[key]:
                human = human_map[key]
                break
        if not human:
            continue
        merged += 1
        if human.get("id"):
            asset["id"] = str(human["id"])
        if human.get("category"):
            asset["category"] = str(human["category"])
        if human.get("subject"):
            asset["subject"] = str(human["subject"])
        if human.get("role"):
            asset["role"] = res_to_role(str(human["role"]))
        if human.get("type"):
            asset["human_type"] = str(human["type"])
        tags = list(asset.get("tags") or [])
        for tag in human.get("tags") or []:
            if tag not in tags:
                tags.append(str(tag))
        asset["tags"] = tags
        if isinstance(human.get("confirmed"), bool):
            asset["confirmed"] = human["confirmed"]
        else:
            asset["confirmed"] = bool(human.get("id") and human.get("type")
                                      and human.get("category"))
        if isinstance(human.get("notes"), str) and human["notes"].strip():
            asset["notes"] = human["notes"].strip()
        asset["source"] = "manifest" if asset["confirmed"] else "scanner"
        asset["human_status"] = human.get("status") or ""
    return merged


def annotate_compatibility(assets: list[dict[str, Any]], project_root: Path,
                           feature_index: list[dict] | None = None,
                           references: dict[str, list[str]] | None = None) -> None:
    """计算 used_by / compatible_features / compatible_entities / compatible_scenes。"""
    references = references if references is not None else build_reference_map(project_root)
    if feature_index is None:
        index = read_json(project_root / ".ai/context/feature_index.json", {})
        feature_index = (index or {}).get("features", []) if isinstance(index, dict) else []

    for asset in assets:
        paths = [asset.get("path")] + list(asset.get("frames") or [])
        used_by: list[str] = []
        for path in paths:
            if not path:
                continue
            for owner in references.get(path, []):
                if owner not in used_by:
                    used_by.append(owner)
        asset["used_by"] = sorted(used_by)

        entity_role = CATEGORY_TO_ENTITY_ROLE.get(str(asset.get("category") or ""), None)
        compatible_features: list[str] = []
        if entity_role:
            hints = ROLE_CAPABILITY_HINTS.get(str(asset.get("role") or ""), set())
            for feature in feature_index:
                roles = ((feature.get("relations") or {}).get("entity_roles")
                         or feature.get("entity_roles") or [])
                if entity_role not in roles:
                    continue
                if hints:
                    provides = set(feature.get("provides") or [])
                    if not (provides & hints):
                        continue
                compatible_features.append(str(feature.get("id")))
        asset["compatible_features"] = compatible_features
        asset["compatible_entities"] = [entity_role] if entity_role else []
        asset["compatible_scenes"] = [ref for ref in used_by if ref.endswith(".tscn")]


def scan_project(project_root: str | os.PathLike | None = None,
                 roots: list[str] | None = None,
                 include: list[str] | None = None) -> dict[str, Any]:
    """扫描项目资源，返回 {assets, stats, roots, scanned_files}。"""
    project = Path(project_root).resolve() if project_root else DEFAULT_PROJECT_ROOT
    root_names = roots if roots else [name for name in DEFAULT_ASSET_ROOTS
                                      if (project / name).is_dir()]
    raw: list[dict[str, Any]] = []
    used_roots: list[str] = []
    seen_roots: set[str] = set()
    for name in root_names:
        root = (project / name).resolve() if not os.path.isabs(str(name)) else Path(name)
        if not root.is_dir():
            continue
        # 大小写不敏感文件系统（Windows/macOS）上 assets 与 Assets 是同一目录：
        # 去重，避免同一个资源被扫描两次（帧数翻倍、条目重复）。
        key = os.path.normcase(str(root))
        if key in seen_roots:
            continue
        seen_roots.add(key)
        used_roots.append(str(root))
        for path in iter_root_files(root):
            metadata = scan_file(project, path, root)
            if metadata:
                raw.append(metadata)

    added = 0
    for extra in include or []:
        path = Path(extra)
        if path.is_file():
            metadata = scan_file(project, path.resolve(), path.resolve().parent)
            if metadata:
                raw.append(metadata)
                added += 1

    assets = group_animations(raw)
    human_merged = apply_human_layer(assets, project)
    assign_ids(assets)
    annotate_compatibility(assets, project)

    stats: dict[str, int] = {}
    for asset in assets:
        stats[asset["type"]] = stats.get(asset["type"], 0) + 1
    return {
        "assets": sorted(assets, key=lambda item: item["id"]),
        "stats": stats,
        "total": len(assets),
        "scanned_files": len(raw),
        "roots": used_roots,
        "human_merged": human_merged,
        "project": str(project),
    }


# ---------- 索引 IO ----------


def index_path(project_root: str | os.PathLike | None = None) -> Path:
    project = Path(project_root).resolve() if project_root else DEFAULT_PROJECT_ROOT
    return project / INDEX_PATH_NAME


def build_index(scan_result: dict[str, Any]) -> dict[str, Any]:
    """扫描结果 -> asset_index.json（Generated Cache）。"""
    return {
        "_generated": True,
        "_note": "Generated Cache — 由 .ai/tools/asset_registry/build_asset_index.py 生成，请勿手工维护。",
        "schema_version": 1,
        "generated_at": now_iso(),
        "project": scan_result.get("project", ""),
        "roots": list(scan_result.get("roots") or []),
        "counts": dict(scan_result.get("stats") or {}),
        "total": int(scan_result.get("total") or 0),
        "assets": [_public_asset(asset) for asset in scan_result.get("assets") or []],
    }


def _public_asset(asset: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in asset.items() if not str(key).startswith("_")}


def load_index(path: str | os.PathLike | None = None,
               project_root: str | os.PathLike | None = None) -> dict[str, Any]:
    target = Path(path) if path else index_path(project_root)
    data = read_json(target, {})
    return data if isinstance(data, dict) else {}


def index_assets(index: dict[str, Any]) -> list[dict[str, Any]]:
    assets = index.get("assets") if isinstance(index, dict) else []
    return [asset for asset in (assets or []) if isinstance(asset, dict)]


def find_asset(index: dict[str, Any], key: str) -> dict[str, Any] | None:
    """按 id / res:// 路径 / 路径前缀查找资产。"""
    if not key:
        return None
    key = str(key)
    for asset in index_assets(index):
        if asset.get("id") == key:
            return asset
    normalized = key if key.startswith("res://") else "res://" + key.lstrip("/")
    for asset in index_assets(index):
        path = str(asset.get("path") or "")
        if path == normalized or path.rstrip("/") == normalized.rstrip("/"):
            return asset
        if normalized.rstrip("/") + "/" in path or normalized in (asset.get("frames") or []):
            return asset
    return None


def asset_exists_on_disk(project_root: Path, asset: dict[str, Any]) -> bool:
    path = str(asset.get("path") or "")
    if path.startswith("res://"):
        disk = project_root / path[len("res://"):].replace("/", os.sep).rstrip(os.sep)
        return disk.exists()
    return Path(path).exists()


TYPE_LABELS = {
    "texture": "textures", "spritesheet": "spritesheets", "animation": "animations",
    "sprite_frames": "sprite_frames", "tileset": "tilesets", "audio": "audio",
    "font": "fonts", "shader": "shaders", "material": "materials",
    "resource": "resources", "scene": "scenes", "unknown": "unknown",
}


def summarize_scan(scan_result: dict[str, Any], show_assets: bool = False) -> str:
    stats = scan_result.get("stats") or {}
    lines = ["Asset Scan Result", ""]
    order = list(TYPE_LABELS)
    lines.append("Found:")
    for key in order:
        if stats.get(key):
            lines.append("  %s: %d" % (TYPE_LABELS[key], stats[key]))
    for key in sorted(set(stats) - set(order)):
        lines.append("  %s: %d" % (key, stats[key]))
    lines.append("")
    lines.append("Total: %d" % int(scan_result.get("total") or 0))
    if show_assets:
        lines.append("")
        lines.append("Assets:")
        for asset in scan_result.get("assets") or []:
            lines.append("  %-24s %-14s %s" % (asset.get("id"), asset.get("type"), asset.get("path")))
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - 调试入口
    import pprint
    pprint.pprint(summarize_scan(scan_project()))
