#!/usr/bin/env python3
"""Maintain the godot-official-docs Skill navigation layer.

Design
------
The Skill is a NAVIGATION layer, not a document mirror:

- Source of Truth (read-only, never modified):
    .ai/skills/godot-official-docs_sources/<version>/
- Skill (references/<version>/) holds only hand-authored routing/index
  files plus GENERATED class indexes. Doc bodies are read directly from
  the Source via relative paths.

File classes inside references/<version>/:
    Hand-authored (never deleted or overwritten by this tool):
        INDEX.md, routing/*.md, api/INDEX.md, api/categories.md,
        metadata/source-info.md
    Generated (safe to regenerate):
        api/classes.md, api/tutorials-index.md, api/members-index.md

Modes
-----
--from-sources  (default, offline)
    Verify the Source snapshot exists, regenerate api/classes.md from
    Source class reference files, and verify every class listed in
    api/categories.md and api/INDEX.md exists. No file is deleted.
--download <branch>
    Download the official godot-docs tarball into _sources/<branch>/
    (network only in this mode; never run implicitly), then build as
    above.

Usage:
    python tools/update_docs.py --from-sources --version 4.7
    python tools/update_docs.py --download 4.7

Exit codes: 0 on success; 1 on any failure.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

GODOC_TARBALL = "https://github.com/godotengine/godot-docs/archive/refs/heads/{branch}.tar.gz"

SKILL_ROOT = Path(__file__).resolve().parent.parent
SOURCES_ROOT = SKILL_ROOT.parent.parent / "godot-official-docs_sources"

VERSION_DIR_NAME = "4.7"
SOURCE_REL = "../../../../godot-official-docs_sources/{v}"

# Upstream godot-docs source dirs that back each documented topic.
TOPIC_SOURCES = {
    "getting_started": "getting_started",
    "tutorials": "tutorials",
    "engine": "engine_details",
    "migration": "tutorials/migrating",
    "api": "classes",
}


def clean_rst_refs(text: str) -> str:
    """:ref:`Name<class_X>` -> X; drop the **<** separators."""
    text = re.sub(r":ref:`([A-Za-z@_0-9]+)<class_([A-Za-z@_0-9]+)>`", r"\1", text)
    return text.replace("**<**", " < ")


def generate_classes_index(version: str, api_dir: Path, src_classes: Path) -> int:
    """Regenerate api/classes.md (Generated). Never touches other files."""
    entries = []
    for rst in sorted(src_classes.glob("class_*.rst")):
        name = rst.stem.removeprefix("class_")
        inherits = ""
        with rst.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*\*\*Inherits:\*\*\s+(.+)", line)
                if m:
                    inherits = clean_rst_refs(m.group(1))
                    break
        entries.append((name, inherits))

    base = SOURCE_REL.format(v=version)
    lines = [
        "# Classes — Godot 类清单（Generated）",
        "",
        f"共 {len(entries)} 个类。由 update_docs.py 自动生成，请勿手工编辑。",
        "",
        f"文档正文统一位于 `{base}/classes/class_<name>.rst`（小写文件名）。",
        "",
        "| Class | Inherits | Source Path |",
        "|---|---|---|",
    ]
    for name, inherits in entries:
        lines.append(
            f"| `{name}` | {inherits} | {base}/classes/class_{name}.rst |"
        )
    (api_dir / "classes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[update_docs] classes.md regenerated: {len(entries)} classes")
    return len(entries)


def _rst_title(rst: Path) -> str:
    """Extract the top heading from an .rst file (title line above an
    underline of ``=`` characters); fall back to the file stem."""
    try:
        with rst.open(encoding="utf-8", errors="replace") as fh:
            prev = ""
            for line in fh:
                s = line.rstrip()
                if s and set(s) <= {"="} and len(s) >= len(prev) and prev:
                    return prev.strip()
                prev = s
    except OSError:
        pass
    return rst.stem


def generate_tutorials_index(version: str, api_dir: Path, src_root: Path) -> int:
    """Regenerate api/tutorials-index.md (Generated): per-directory .rst listing
    with human-readable titles for semantic matching."""
    base = SOURCE_REL.format(v=version)
    scan_roots = ["getting_started", "tutorials", "engine_details"]
    lines = [
        "# Tutorials Index — 教程/引擎细节文件清单（Generated）",
        "",
        "由 update_docs.py 自动生成，请勿手工编辑。",
        "",
        "用途：topics.md 命中目录后，在此表内按标题语义定位具体文件，避免目录扫描。",
        "",
        "| Section | Title | File | Source Path |",
        "|---|---|---|---|",
    ]
    count = 0
    for root in scan_roots:
        rst_files = sorted((src_root / root).rglob("*.rst"))
        for rst in rst_files:
            rel = rst.relative_to(src_root).as_posix()
            title = _rst_title(rst)
            lines.append(f"| {root} | {title} | {rst.stem} | {base}/{rel} |")
            count += 1
    (api_dir / "tutorials-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[update_docs] tutorials-index.md regenerated: {count} files")
    return count


def generate_members_index(version: str, api_dir: Path, src_classes: Path) -> int:
    """Regenerate api/members-index.md (Generated): member -> defining class.

    Parses each class .rst for classref directives (:ref:`name<class_X_method_y>`
    etc.) and records which class defines which member. Enables reverse lookup:
    "which class defines move_and_slide?" -> CharacterBody2D/3D, replacing
    manual inheritance-chain climbing.
    """
    base = SOURCE_REL.format(v=version)
    member_re = re.compile(
        r":ref:`([A-Za-z0-9_@.]+)<class_([A-Za-z0-9@_]+)_(method|property|signal|enumeration|constant|theme_property)_"
    )
    lines = [
        "# Members Index — 成员反查表（Generated）",
        "",
        "由 update_docs.py 自动生成，请勿手工编辑。",
        "",
        "用途：成员名 → 定义它的类。目标类文档中找不到某成员时，用本表反查定义类，",
        "替代人工按继承链逐级上溯。",
        "",
        "| Member | Kind | Defining Class | Source Path |",
        "|---|---|---|---|",
    ]
    count = 0
    for rst in sorted(src_classes.glob("class_*.rst")):
        cls = rst.stem.removeprefix("class_")
        with rst.open(encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        seen = set()
        for m in member_re.finditer(text):
            member, kind = m.group(1), m.group(2)
            key = (member, kind)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"| `{member}` | {kind} | `{cls}` | {base}/classes/class_{cls}.rst |"
            )
            count += 1
    (api_dir / "members-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[update_docs] members-index.md regenerated: {count} members")
    return count


def generate_keyword_suggestions(version: str, api_dir: Path, src_classes: Path) -> int:
    """Regenerate api/keywords-suggested.md (Generated): class-name keyword table.

    Hand-authored routing/keywords.md covers ~45 common natural-language
    queries; this generated table covers ALL 1078 classes so an Agent can
    match any class-name-like keyword (astar, tilemap, particles, ...) to
    its Source file without full-text searching the Source tree.
    """
    base = SOURCE_REL.format(v=version)
    names = sorted(
        rst.stem.removeprefix("class_")
        for rst in src_classes.glob("class_*.rst")
    )
    lines = [
        "# Keywords Suggested — 全量类名关键词表（Generated）",
        "",
        f"共 {len(names)} 条。由 update_docs.py 自动生成，请勿手工编辑。",
        "",
        "用途：hand-authored `routing/keywords.md` 未命中时，按问题中的类名关键词",
        "在本表模糊匹配（子串），命中即获得精确 Source 路径。",
        "",
        "| Keyword | Source Path |",
        "|---|---|",
    ]
    for n in names:
        lines.append(f"| `{n}` | {base}/classes/class_{n}.rst |")
    (api_dir / "keywords-suggested.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[update_docs] keywords-suggested.md regenerated: {len(names)} entries")
    return len(names)


def verify_named_classes(api_dir: Path, src_classes: Path) -> list[str]:
    """Verify every class named in hand-authored indexes exists in Source."""
    named = set()
    for fname in ("categories.md", "INDEX.md"):
        f = api_dir / fname
        if not f.exists():
            continue
        for m in re.finditer(r"`([A-Za-z@_0-9]+)`", f.read_text(encoding="utf-8")):
            named.add(m.group(1).lstrip("@").lower())
    missing = [
        n for n in sorted(named)
        if n and not (src_classes / f"class_{n}.rst").exists()
    ]
    return missing


def verify_topics(version: str, src_root: Path, ref_dir: Path) -> list[str]:
    """Verify topic paths referenced by routing files exist in Source."""
    missing = []
    routing = ref_dir / "routing"
    for f in sorted(routing.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(
            r"godot-official-docs_sources/%s/([A-Za-z0-9_/.\-]+)" % version, text
        ):
            p = m.group(1).rstrip(".,)")
            if not (src_root / p).exists():
                missing.append(f"{f.name}: {p}")
    return missing


def build_from_sources(version: str) -> int:
    src_root = SOURCES_ROOT / version
    if not src_root.is_dir():
        raise RuntimeError(f"Source snapshot not found: {src_root}")

    ref_dir = SKILL_ROOT / "references" / version
    api_dir = ref_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    problems = []

    # 1. Regenerate the generated layer.
    generate_classes_index(version, api_dir, src_root / "classes")
    generate_tutorials_index(version, api_dir, src_root)
    generate_keyword_suggestions(version, api_dir, src_root / "classes")
    generate_members_index(version, api_dir, src_root / "classes")

    # 2. Verify topics cited by routing exist in Source.
    missing_topics = verify_topics(version, src_root, ref_dir)
    problems.extend(missing_topics)

    # 3. Verify hand-authored class references resolve.
    missing_classes = verify_named_classes(api_dir, src_root / "classes")
    problems.extend(f"class not found in Source: {c}" for c in missing_classes)

    # 4. Report.
    total = sum(f.stat().st_size for f in ref_dir.rglob("*") if f.is_file())
    print(f"[update_docs] skill navigation layer size: {total / 1024:.0f} KB")
    if problems:
        print("[update_docs] PROBLEMS:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("[update_docs] done: generated layer rebuilt, all references verified")
    return 0


def download(version: str) -> int:
    dst = SOURCES_ROOT / version
    if dst.is_dir() and any(dst.iterdir()):
        raise RuntimeError(f"Source snapshot already exists, refusing to overwrite: {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tarball = Path(tmp) / "godot-docs.tar.gz"
        url = GODOC_TARBALL.format(branch=version)
        print(f"[update_docs] downloading {url}")
        with urllib.request.urlopen(url, timeout=300) as resp, open(tarball, "wb") as out:
            shutil.copyfileobj(resp, out)
        with tarfile.open(tarball, "r:gz") as tar:
            members = tar.getmembers()
            tops = {m.name.split("/")[0] for m in members}
            if len(tops) != 1:
                raise RuntimeError(f"unexpected tarball layout: {sorted(tops)}")
            tar.extractall(tmp)
            shutil.copytree(Path(tmp) / tops.pop(), dst, dirs_exist_ok=True)
    print(f"[update_docs] Source snapshot saved to {dst}")
    return build_from_sources(version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--from-sources", action="store_true", default=True,
                      help="verify Source + regenerate generated layer (default, offline)")
    mode.add_argument("--download", metavar="BRANCH",
                      help="download godot-docs branch into _sources/, then build")
    parser.add_argument("--version", default=VERSION_DIR_NAME)
    args = parser.parse_args()
    try:
        if args.download:
            return download(args.download)
        return build_from_sources(args.version)
    except Exception as exc:  # noqa: BLE001
        print(f"[update_docs] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
