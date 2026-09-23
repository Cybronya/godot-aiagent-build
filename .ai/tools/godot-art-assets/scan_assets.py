#!/usr/bin/env python3
"""
Godot Art Assets Skill v3 scanner/organizer.

Commands:
  init       Create standard asset folders.
  scan       Scan assets and update manifest facts.
  review     Generate human review forms.
  apply      Apply completed review forms.
  sync       scan + review.
  check      Validate project asset conventions.
  organize   Safely organize only high-confidence untracked files.

No visual recognition is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image
except Exception:
    Image = None

STANDARD_DIRS = [
    "characters",
    "environments",
    "tilesets",
    "backgrounds",
    "props",
    "items",
    "vfx",
    "ui",
    "portraits",
    "fonts",
]

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tga"}
ASSET_EXTS = IMAGE_EXTS | {".svg", ".ttf", ".otf", ".woff", ".woff2"}

IGNORED_DIRS = {".git", ".godot", ".import", "__pycache__"}

TYPE_ALIASES = {
    "characters": "character",
    "character": "character",
    "environments": "environment",
    "environment": "environment",
    "tilesets": "tileset",
    "tileset": "tileset",
    "backgrounds": "background",
    "background": "background",
    "props": "prop",
    "prop": "prop",
    "items": "item",
    "item": "item",
    "vfx": "vfx",
    "ui": "ui",
    "portraits": "portrait",
    "portrait": "portrait",
    "fonts": "font",
    "font": "font",
}

ACTION_TOKENS = {
    "idle", "walk", "run", "attack", "hit", "hurt", "death", "die",
    "jump", "fall", "dash", "cast", "shoot", "open", "close", "use",
    "equip", "unequip", "block", "roll", "climb", "swim", "interact",
}

DIRECTION_TOKENS = {
    "up", "down", "left", "right", "up_left", "up_right",
    "down_left", "down_right",
}

STATUS_VALUES = {"draft", "candidate", "approved", "deprecated", "archived"}
TYPE_VALUES = set(TYPE_ALIASES.values())

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def project_root() -> Path:
    return Path(__file__).resolve().parents[3]

def assets_root(root: Path) -> Path:
    return root / "assets"

def manifest_path(root: Path) -> Path:
    return root / ".ai" / "context" / "asset_manifest.json"

def reviews_dir(root: Path) -> Path:
    return root / ".ai" / "context" / "asset_reviews"

def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def image_size(path: Path) -> Tuple[Optional[int], Optional[int]]:
    if Image is None or path.suffix.lower() not in IMAGE_EXTS:
        return None, None
    try:
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return None, None

def split_tokens(stem: str) -> List[str]:
    stem = stem.lower()
    stem = re.sub(r"(\d+)$", "", stem)
    return [x for x in re.split(r"[_\-\s]+", stem) if x]

def derive_hints(relative_path: str, filename: str) -> Tuple[List[str], Dict[str, List[str]]]:
    parts = [p.lower() for p in Path(relative_path).parts[:-1]]
    path_hints = []
    for part in parts:
        if part in TYPE_ALIASES:
            value = TYPE_ALIASES[part]
            if value not in path_hints:
                path_hints.append(value)
        if part in {"player", "enemy", "enemies", "npc", "boss", "monster"}:
            if part not in path_hints:
                path_hints.append("enemy" if part in {"enemy", "enemies", "boss", "monster"} else part)

    tokens = split_tokens(Path(filename).stem)
    actions = [t for t in tokens if t in ACTION_TOKENS]
    directions = []
    joined = "_".join(tokens)
    for d in sorted(DIRECTION_TOKENS, key=len, reverse=True):
        if d in tokens or d in joined:
            directions.append(d)

    return path_hints, {
        "actions": list(dict.fromkeys(actions)),
        "directions": list(dict.fromkeys(directions)),
    }

def scan_files(root: Path) -> Dict[str, Dict[str, Any]]:
    ar = assets_root(root)
    result: Dict[str, Dict[str, Any]] = {}
    if not ar.exists():
        return result

    for p in ar.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(ar).parts
        if any(part in IGNORED_DIRS for part in rel_parts):
            continue
        if p.suffix.lower() not in ASSET_EXTS:
            continue

        rel = p.relative_to(ar).as_posix()
        stat = p.stat()
        width, height = image_size(p)
        path_hints, filename_hints = derive_hints(rel, p.name)

        result[rel] = {
            "path": f"assets/{rel}",
            "filename": p.name,
            "extension": p.suffix.lower(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            "sha256": sha256_file(p),
            "width": width,
            "height": height,
            "path_hints": path_hints,
            "filename_hints": filename_hints,
        }
    return result

def load_manifest(root: Path) -> Dict[str, Any]:
    data = read_json(manifest_path(root), {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema_version", 3)
    data.setdefault("project", None)
    data.setdefault("generated_at", None)
    data.setdefault("assets", [])
    data.setdefault("pending", [])
    return data

def asset_map(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        a.get("relative_key"): a
        for a in manifest.get("assets", [])
        if isinstance(a, dict) and a.get("relative_key")
    }

def facts_changed(old: Dict[str, Any], new_auto: Dict[str, Any]) -> bool:
    old_auto = old.get("auto", old)
    return old_auto.get("sha256") != new_auto.get("sha256")

def preserve_human(old: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not old:
        return {}
    human = old.get("human", {})
    return human if isinstance(human, dict) else {}

def scan(root: Path) -> Dict[str, Any]:
    manifest = load_manifest(root)
    old = asset_map(manifest)
    scanned = scan_files(root)

    new_assets = []
    changed = []
    unchanged = []

    new_manifest_assets = []
    pending_keys = set(manifest.get("pending", []))

    for rel, auto in scanned.items():
        previous = old.get(rel)
        human = preserve_human(previous)

        item = {
            "relative_key": rel,
            "auto": auto,
            "human": human,
        }
        new_manifest_assets.append(item)

        if previous is None:
            new_assets.append(rel)
            pending_keys.add(rel)
        elif facts_changed(previous, auto):
            changed.append(rel)
            pending_keys.add(rel)
        else:
            unchanged.append(rel)

    deleted = sorted(set(old) - set(scanned))
    pending_keys -= set(deleted)

    manifest["schema_version"] = 3
    manifest["project"] = root.name
    manifest["generated_at"] = now_iso()
    manifest["assets"] = sorted(new_manifest_assets, key=lambda x: x["relative_key"])
    manifest["pending"] = sorted(pending_keys)

    write_json(manifest_path(root), manifest)

    print(f"Scanned: {len(scanned)}")
    print(f"New: {len(new_assets)}")
    print(f"Changed: {len(changed)}")
    print(f"Deleted: {len(deleted)}")
    print(f"Unchanged: {len(unchanged)}")
    if new_assets:
        print("\nNEW")
        for x in new_assets:
            print(f"  + {x}")
    if changed:
        print("\nCHANGED")
        for x in changed:
            print(f"  * {x}")
    if deleted:
        print("\nDELETED")
        for x in deleted:
            print(f"  - {x}")

    return {
        "new": new_assets,
        "changed": changed,
        "deleted": deleted,
        "unchanged": unchanged,
    }

def init_dirs(root: Path) -> None:
    ar = assets_root(root)
    ar.mkdir(parents=True, exist_ok=True)
    created = []
    for name in STANDARD_DIRS:
        p = ar / name
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(name)
    if created:
        print("Created:")
        for name in created:
            print(f"  + assets/{name}/")
    else:
        print("All standard asset folders already exist.")

def default_human() -> Dict[str, Any]:
    return {
        "id": None,
        "type": None,
        "category": None,
        "tags": [],
        "status": "candidate",
        "subtype": None,
        "character": None,
        "action": None,
        "direction": None,
        "frame": None,
        "description": None,
        "source": None,
        "notes": None,
    }

def make_review(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "_instructions": {
            "description": "只编辑 asset.human；asset.auto 由 Scanner 管理。",
            "required_human_fields": ["id", "type", "category", "status"],
            "allowed_status": sorted(STATUS_VALUES),
            "allowed_type": sorted(TYPE_VALUES),
        },
        "asset": {
            "relative_key": item["relative_key"],
            "auto": item["auto"],
            "human": {
                **default_human(),
                **item.get("human", {}),
            },
        },
    }

def review(root: Path) -> None:
    manifest = load_manifest(root)
    amap = asset_map(manifest)
    rd = reviews_dir(root)
    rd.mkdir(parents=True, exist_ok=True)

    count = 0
    for rel in manifest.get("pending", []):
        item = amap.get(rel)
        if not item:
            continue
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "__", rel)
        out = rd / f"{safe}.review.json"
        if not out.exists():
            write_json(out, make_review(item))
            count += 1

    print(f"Review forms created: {count}")
    print(f"Review directory: {rd.relative_to(root).as_posix()}")

def validate_human(human: Dict[str, Any]) -> List[str]:
    errors = []
    for field in ["id", "type", "category", "status"]:
        if not human.get(field):
            errors.append(f"missing {field}")
    if human.get("status") and human["status"] not in STATUS_VALUES:
        errors.append(f"invalid status: {human['status']}")
    if human.get("type") and human["type"] not in TYPE_VALUES:
        errors.append(f"invalid type: {human['type']}")
    return errors

def apply_reviews(root: Path) -> None:
    manifest = load_manifest(root)
    amap = asset_map(manifest)
    rd = reviews_dir(root)
    applied = []
    errors = []

    for path in sorted(rd.glob("*.review.json")):
        data = read_json(path, None)
        if not isinstance(data, dict):
            errors.append(f"{path.name}: invalid JSON")
            continue
        asset = data.get("asset", {})
        rel = asset.get("relative_key")
        human = asset.get("human", {})
        if rel not in amap:
            errors.append(f"{path.name}: asset not found in manifest: {rel}")
            continue
        if not isinstance(human, dict):
            errors.append(f"{path.name}: human must be object")
            continue
        validation = validate_human(human)
        if validation:
            errors.append(f"{path.name}: " + ", ".join(validation))
            continue

        amap[rel]["human"] = human
        applied.append(rel)

    manifest["assets"] = sorted(amap.values(), key=lambda x: x["relative_key"])
    pending = set(manifest.get("pending", []))
    for rel in applied:
        pending.discard(rel)
    manifest["pending"] = sorted(pending)
    manifest["generated_at"] = now_iso()
    write_json(manifest_path(root), manifest)

    print(f"Applied reviews: {len(applied)}")
    if errors:
        print(f"Review errors: {len(errors)}")
        for e in errors:
            print(f"  ! {e}")

def check_naming(filename: str) -> List[str]:
    errors = []
    if filename.lower() != filename:
        errors.append("filename is not lowercase")
    if " " in filename:
        errors.append("filename contains spaces")
    if not re.fullmatch(r"[a-z0-9_./-]+", filename):
        errors.append("filename contains unsupported characters")
    stem = Path(filename).stem
    bad_words = {"final", "new", "old", "test"}
    tokens = set(split_tokens(stem))
    bad = sorted(tokens & bad_words)
    if bad:
        errors.append("contains discouraged token(s): " + ", ".join(bad))
    return errors

def animation_groups(items: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    groups: Dict[str, List[int]] = {}
    rx = re.compile(
        r"^(?P<prefix>.+)_(?P<frame>\d{2,})$"
    )
    for item in items:
        stem = Path(item["relative_key"]).stem
        m = rx.match(stem)
        if not m:
            continue
        key = m.group("prefix")
        groups.setdefault(key, []).append(int(m.group("frame")))
    return groups

def check(root: Path) -> bool:
    problems = 0
    ar = assets_root(root)
    if not ar.exists():
        print("FAIL: assets/ does not exist. Run init.")
        return False

    print("Folders")
    for d in STANDARD_DIRS:
        exists = (ar / d).exists()
        print(f"  {'PASS' if exists else 'FAIL'} assets/{d}/")
        if not exists:
            problems += 1

    manifest = load_manifest(root)
    items = manifest.get("assets", [])
    scanned = scan_files(root)
    amap = asset_map(manifest)

    print("\nFiles")
    for rel in sorted(scanned):
        errs = check_naming(Path(rel).name)
        if errs:
            problems += len(errs)
            print(f"  WARN {rel}")
            for e in errs:
                print(f"       - {e}")

    print("\nManifest")
    manifest_keys = set(amap)
    scanned_keys = set(scanned)
    missing = scanned_keys - manifest_keys
    stale = manifest_keys - scanned_keys
    if missing:
        problems += len(missing)
        print(f"  WARN {len(missing)} scanned files missing from manifest")
    else:
        print("  PASS scanned files are represented")
    if stale:
        problems += len(stale)
        print(f"  WARN {len(stale)} manifest entries are missing on disk")

    pending = manifest.get("pending", [])
    print(f"  {'WARN' if pending else 'PASS'} pending review: {len(pending)}")
    problems += len(pending)

    print("\nDuplicates")
    by_hash: Dict[str, List[str]] = {}
    for rel, auto in scanned.items():
        h = auto["sha256"]
        by_hash.setdefault(h, []).append(rel)
    dup_groups = [v for v in by_hash.values() if len(v) > 1]
    if dup_groups:
        print(f"  WARN duplicate content groups: {len(dup_groups)}")
        problems += len(dup_groups)
        for group in dup_groups:
            print("       " + " | ".join(group))
    else:
        print("  PASS no duplicate content")

    print("\nAnimations")
    groups = animation_groups(items)
    anim_problems = 0
    for key, frames in sorted(groups.items()):
        if len(frames) < 2:
            continue
        expected = list(range(min(frames), max(frames) + 1))
        if frames != expected or min(frames) != 0:
            anim_problems += 1
            print(f"  WARN {key}: frames={sorted(frames)}")
    if anim_problems:
        problems += anim_problems
    else:
        print("  PASS no obvious frame gaps")

    print(f"\nOverall: {'WARN/FAIL' if problems else 'PASS'} ({problems} issue(s))")
    return problems == 0

def classify_high_confidence(item: Dict[str, Any]) -> Optional[str]:
    auto = item["auto"]
    hints = auto.get("path_hints", [])
    # Only classify when there is exactly one explicit top-level type hint.
    types = [h for h in hints if h in TYPE_VALUES]
    if len(set(types)) != 1:
        return None
    return types[0]

def organize(root: Path) -> None:
    """
    Conservative organizer:
    - Only considers files currently in top-level assets/.
    - Only moves files when the path/name provides one unambiguous type hint.
    - Never overwrites existing files.
    - Never touches files already in a standard subfolder.
    - After moving, rescans.
    """
    ar = assets_root(root)
    if not ar.exists():
        print("assets/ does not exist. Run init first.")
        return

    manifest = load_manifest(root)
    amap = asset_map(manifest)
    moved = 0
    skipped = 0

    for p in sorted(ar.iterdir()):
        if not p.is_file() or p.suffix.lower() not in ASSET_EXTS:
            continue
        rel = p.relative_to(ar).as_posix()
        item = amap.get(rel)
        if not item:
            # Build a temporary fact record from current file.
            width, height = image_size(p)
            ph, fh = derive_hints(rel, p.name)
            item = {"relative_key": rel, "auto": {
                "path": f"assets/{rel}",
                "filename": p.name,
                "extension": p.suffix.lower(),
                "size_bytes": p.stat().st_size,
                "modified_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
                "sha256": sha256_file(p),
                "width": width, "height": height,
                "path_hints": ph, "filename_hints": fh,
            }, "human": {}}

        target_type = classify_high_confidence(item)
        if not target_type:
            skipped += 1
            continue

        target_dir = ar / (next(k for k, v in TYPE_ALIASES.items() if v == target_type))
        # Prefer canonical plural directory.
        canonical = {
            "character": "characters", "environment": "environments",
            "tileset": "tilesets", "background": "backgrounds",
            "prop": "props", "item": "items", "vfx": "vfx",
            "ui": "ui", "portrait": "portraits", "font": "fonts"
        }[target_type]
        target_dir = ar / canonical
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / p.name

        if dest.exists():
            print(f"SKIP existing destination: {dest.relative_to(root)}")
            skipped += 1
            continue

        shutil.move(str(p), str(dest))
        print(f"MOVED {p.relative_to(root)} -> {dest.relative_to(root)}")
        moved += 1

    if moved:
        scan(root)
    print(f"Organize complete. Moved: {moved}; Skipped: {skipped}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Godot Art Assets Skill v3")
    parser.add_argument("command", choices=[
        "init", "scan", "review", "apply", "sync", "check", "organize"
    ])
    args = parser.parse_args()

    root = project_root()

    if args.command == "init":
        init_dirs(root)
    elif args.command == "scan":
        scan(root)
    elif args.command == "review":
        review(root)
    elif args.command == "apply":
        apply_reviews(root)
    elif args.command == "sync":
        scan(root)
        review(root)
    elif args.command == "check":
        if not check(root):
            sys.exit(1)
    elif args.command == "organize":
        organize(root)

if __name__ == "__main__":
    main()
