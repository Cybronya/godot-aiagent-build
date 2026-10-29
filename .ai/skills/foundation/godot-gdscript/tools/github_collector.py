#!/usr/bin/env python3
"""GitHub GDScript 代码收集工具。

用于 .ai/skills/foundation/godot-gdscript/code_library/ 的自动化收集管道。

子命令:
  search   按 star 自动发现优质 GDScript 仓库 (GitHub Search API)
  fetch    下载仓库 tarball，抽取 .gd/.gdshader + LICENSE + README 到 sources/
  catalog  蒸馏 sources/ 到 references/，hash 去重，生成 catalog.yaml + INDEX.md
  check    在 scratch 工程中批量 parse 检查 references/，回填 parse_status

用法示例:
  python github_collector.py search --min-stars 100 --limit 60
  python github_collector.py fetch --top 10
  python github_collector.py catalog
  python github_collector.py check

GITHUB_TOKEN 环境变量可选，用于提高 API 速率限制（搜索 10次/分 -> 30次/分）。
tarball 下载走 codeload，不占用 API 配额。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LIB_DIR = SKILL_DIR / "code_library"
SOURCES_DIR = LIB_DIR / "sources"
REFERENCES_DIR = LIB_DIR / "references"
CANDIDATES_JSON = LIB_DIR / "candidates.json"
CATALOG_YAML = LIB_DIR / "catalog.yaml"
INDEX_MD = LIB_DIR / "INDEX.md"
AI_TMP = SKILL_DIR.parents[2] / "tmp"  # .ai/tmp
FEATURE_ROOT = SKILL_DIR.parents[3] / "Features"  # 项目 Features 资产目录
FEATURE_INDEX_BUILDER = (SKILL_DIR.parents[2] / "tools" / "feature_registry"
                         / "build_feature_index.py")
CHECK_DIR = AI_TMP / "code_check"
GODOT_BIN = os.environ.get(
    "GODOT_BIN", "F:/Godot_v4.7-stable/Godot_v4.7-stable_win64_console.exe"
)

ALLOWED_LICENSES = {
    "MIT", "CC0-1.0", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0",
    "Unlicense", "ISC", "Zlib", "MPL-2.0",
}
GD_SUFFIXES = {".gd", ".gdshader"}
MAX_FILE_BYTES = 200_000  # 单文件超过 200KB 视为异常，跳过


def _http_get_json(url: str, token: str | None) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "godot-code-collector/1.0",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _slug(full_name: str) -> str:
    return full_name.replace("/", "__")


_INVALID = '<>:"|?*\0'


def _sanitize_rel(rel: Path) -> Path:
    """清洗路径各段中 Windows 非法字符与结尾点/空格。"""
    parts = []
    for seg in rel.parts:
        seg = "".join("_" if ch in _INVALID or ord(ch) < 32 else ch for ch in seg)
        seg = seg.rstrip(" .")
        if seg:
            parts.append(seg)
    return Path(*parts) if parts else Path("_unnamed")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _rmtree_force(path: Path) -> None:
    """删除目录；shutil 失败时降级到系统命令（Windows rmdir / POSIX rm -rf）。"""
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except OSError:
        if os.name == "nt":
            subprocess_run = os.system  # noqa: S605
            subprocess_run(f'rmdir /s /q "{path}"')
        else:
            os.system(f'rm -rf "{path}"')  # noqa: S605
        if path.exists():
            raise


# ───────────────────────────── search ─────────────────────────────


def cmd_search(args: argparse.Namespace) -> None:
    token = args.token or os.environ.get("GITHUB_TOKEN")
    allowed = set(args.license.split(",")) if args.license else ALLOWED_LICENSES
    query = f"language:gdscript stars:>={args.min_stars}"
    results, page = [], 1
    while len(results) < args.limit:
        params = urllib.parse.urlencode({
            "q": query, "sort": "stars", "order": "desc",
            "per_page": 50, "page": page,
        })
        url = f"https://api.github.com/search/repositories?{params}"
        data = _http_get_json(url, token)
        items = data.get("items", [])
        if not items:
            break
        for it in items:
            license_spdx = (it.get("license") or {}).get("spdx_id") or "unknown"
            if it.get("archived"):
                continue
            if it.get("fork") and not args.include_forks:
                continue
            license_ok = license_spdx in allowed
            results.append({
                "full_name": it["full_name"],
                "stars": it["stargazers_count"],
                "license": license_spdx,
                "license_ok": license_ok,
                "description": (it.get("description") or "").strip(),
                "default_branch": it.get("default_branch", "main"),
                "pushed_at": it.get("pushed_at", ""),
                "topics": it.get("topics", []),
                "html_url": it["html_url"],
            })
        page += 1
    results = results[: args.limit]
    CANDIDATES_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = sum(1 for r in results if r["license_ok"])
    print(f"[search] {len(results)} candidates -> {CANDIDATES_JSON}")
    print(f"[search] license-ok: {ok} / {len(results)}")
    for r in results:
        flag = "ok " if r["license_ok"] else "SKIP"
        print(f"  [{flag}] {r['stars']:>6}* {r['full_name']:<48} {r['license']:<12} "
              f"{r['description'][:60]}")


# ───────────────────────────── fetch ──────────────────────────────


def cmd_fetch(args: argparse.Namespace) -> None:
    targets: list[dict] = []
    if args.repo:
        info = _http_get_json(f"https://api.github.com/repos/{args.repo}", None)
        targets.append({
            "full_name": info["full_name"],
            "default_branch": info["default_branch"],
            "license": (info.get("license") or {}).get("spdx_id") or "unknown",
            "stars": info.get("stargazers_count", 0),
        })
    else:
        if not CANDIDATES_JSON.exists():
            sys.exit("[fetch] 未找到 candidates.json，先运行 search")
        candidates = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
        pool = [c for c in candidates if c.get("license_ok")] if not args.all else candidates
        targets = pool[: args.top]
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    for t in targets:
        slug = _slug(t["full_name"])
        dest = SOURCES_DIR / slug
        if dest.exists() and not args.force:
            print(f"[fetch] 已存在，跳过: {t['full_name']}")
            continue
        try:
            _fetch_one(t, dest)
        except Exception as exc:  # noqa: BLE001
            import traceback
            print(f"[fetch] 失败: {t['full_name']}: {exc}")
            traceback.print_exc()


def _fetch_one(meta: dict, dest: Path) -> None:
    full = meta["full_name"]
    slug = _slug(full)
    branch = meta.get("default_branch", "main")
    gd_dir = dest / "gd"
    url = (f"https://codeload.github.com/{full}/tar.gz/refs/heads/"
           f"{urllib.parse.quote(branch)}")
    print(f"[fetch] {full} ({branch}) ...")
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / "repo.tar.gz"
        req = urllib.request.Request(url, headers={"User-Agent": "godot-code-collector/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(tgz, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        extract_root = Path(td) / "x"
        extract_root.mkdir()
        dest.mkdir(parents=True, exist_ok=True)
        gd_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz, "r:gz") as tf:
            members = tf.getmembers()
            root_name = members[0].name.split("/")[0] if members else ""
            # 短 sha 可从根目录名解析 (repo-<sha>)
            sha = root_name[len(full.rsplit('/', 1)[-1]) + 1:] if root_name else ""
            safe = [m for m in members
                    if not m.name.startswith("/") and ".." not in Path(m.name).parts]
            tf.extractall(extract_root, members=safe, filter="data")
        src_root = extract_root / root_name
        count = 0
        for f in sorted(src_root.rglob("*")):
            rel = f.relative_to(src_root)
            if f.suffix.lower() in GD_SUFFIXES and f.stat().st_size <= MAX_FILE_BYTES:
                out = gd_dir / _sanitize_rel(rel)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out)
                count += 1
                if count >= 800:
                    print(f"[fetch] 达到单仓库上限 800 文件，截断: {full}")
                    break
            if len(rel.parts) == 1 and f.is_file() and (
                f.name.upper().startswith("LICENSE") or f.name.upper().startswith("README")
            ):
                shutil.copy2(f, dest / f.name)
    info = dict(meta)
    info.update({
        "branch": branch, "commit_sha": sha, "fetched_at": _now(),
        "gd_file_count": count, "slug": slug,
    })
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "_meta.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[fetch] {full}: {count} 个 gd 文件 -> sources/{slug}")


# ───────────────────────────── catalog ────────────────────────────

DOMAIN_RULES = [
    ("state_machine", ["state_machine", "statemachine", "state machine"]),
    ("movement", ["movement", "platformer", "characterbody", "walk", "jump",
                  "player_controller", "controller", "top_down"]),
    ("combat", ["combat", "attack", "damage", "health", "weapon", "bullet",
                "projectile", "hitbox", "hurtbox", "shoot", "boss"]),
    ("ai", ["enemy", "npc", "pathfinding", "navigation", "behavior", "steering"]),
    ("ui", ["ui", "hud", "menu", "dialog", "inventory", "shop", "button"]),
    ("save", ["save", "load_game", "persistence", "config"]),
    ("audio", ["audio", "music", "sfx", "sound"]),
    ("animation", ["animation", "sprite", "tween", "fx", "vfx", "effect"]),
    ("input", ["input", "touch", "gamepad"]),
    ("network", ["multiplayer", "network", "netcode"]),
]


def classify(rel_path: Path, text: str) -> str:
    hay = rel_path.as_posix().lower() + "\n" + text[:2000].lower()
    for domain, kws in DOMAIN_RULES:
        if any(k in hay for k in kws):
            return domain
    return "general"


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def cmd_catalog(args: argparse.Namespace) -> None:
    _rmtree_force(REFERENCES_DIR)
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    entries, seen_hashes, seen_names = [], {}, {}
    repos = sorted(p for p in SOURCES_DIR.iterdir() if p.is_dir())
    for repo_dir in repos:
        meta = json.loads((repo_dir / "_meta.json").read_text(encoding="utf-8"))
        for f in sorted((repo_dir / "gd").rglob("*")):
            if f.suffix.lower() not in GD_SUFFIXES:
                continue
            rel = f.relative_to(repo_dir / "gd")
            raw = f.read_bytes()
            if len(raw) > MAX_FILE_BYTES:
                continue
            content_hash = hashlib.sha256(raw).hexdigest()
            # flat id 先算：duplicate_of 直接指向**保留条目的 catalog id**，
            # 检索/promote 时可反查到 references/ 里的那份文件。
            flat = (f"{meta['slug']}__"
                    f"{rel.with_suffix('').as_posix().replace('/', '__')}{f.suffix}")
            dup_of = seen_hashes.get(content_hash)
            seen_hashes.setdefault(content_hash, flat)
            text = raw.decode("utf-8", errors="replace")
            domain = classify(rel, text)
            lines = text.count("\n") + 1
            name_owner = seen_names.get(flat)
            if name_owner and not dup_of:
                dup_of = name_owner  # 扁平化同名冲突视为重复
            entry = {
                "id": flat,
                "repo": meta["full_name"],
                "repo_slug": meta["slug"],
                "repo_path": rel.as_posix(),
                "domain": domain,
                "license": meta.get("license", "unknown"),
                "stars": meta.get("stars", 0),
                "lines": lines,
                "sha256": content_hash[:12],
                "duplicate_of": dup_of,
                "commit_sha": meta.get("commit_sha", ""),
                "source_url": f"https://github.com/{meta['full_name']}/blob/"
                              f"{meta.get('branch', 'main')}/{rel.as_posix()}",
                "collected_at": meta.get("fetched_at", _now()),
                "parse_status": ("duplicate" if dup_of else
                                 "skipped_shader" if f.suffix.lower() == ".gdshader"
                                 else "unchecked"),
            }
            entries.append(entry)
            if dup_of:
                continue
            seen_names[flat] = flat
            header = (
                f"# Source:  {entry['source_url']}\n"
                f"# Repo:    {meta['full_name']} (star {entry['stars']}) | "
                f"License: {entry['license']} | Collected: {entry['collected_at']}\n"
                f"# Commit:  {entry['commit_sha']}\n"
            )
            out = REFERENCES_DIR / domain / flat
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(header + text, encoding="utf-8")
    _write_catalog_yaml(entries)
    _write_index_md(entries)
    print(f"[catalog] {len(entries)} 条目, "
          f"{sum(1 for e in entries if not e['duplicate_of'])} 个去重片段 -> references/")


def _write_catalog_yaml(entries: list[dict]) -> None:
    unique = sum(1 for e in entries if not e.get("duplicate_of"))
    out = ["# AUTO-GENERATED by github_collector.py catalog - 请勿手工编辑",
           "version: 1",
           "generated_at: " + _now(),
           f"total_entries: {len(entries)}",
           f"unique_fragments: {unique}",
           "snippets:"]
    for e in entries:
        out.append(f"  - id: {_yaml_str(e['id'])}")
        for k in ("repo", "repo_slug", "repo_path", "domain", "license",
                  "stars", "lines", "sha256", "duplicate_of", "commit_sha",
                  "source_url", "collected_at", "parse_status"):
            out.append(f"    {k}: {_yaml_str(str(e[k]))}")
    CATALOG_YAML.write_text("\n".join(out) + "\n", encoding="utf-8")


def _write_index_md(entries: list[dict]) -> None:
    domains: dict[str, list[dict]] = {}
    for e in entries:
        domains.setdefault(e["domain"], []).append(e)
    repos = {}
    for e in entries:
        r = repos.setdefault(e["repo_slug"], {"stars": e["stars"],
                                              "license": e["license"],
                                              "n": 0})
        r["n"] += 1
    lines = [
        "# Godot Code Library Index",
        "",
        f"AUTO-GENERATED by github_collector.py catalog at {_now()}. 请勿手工编辑。",
        "",
        "## 检索规则 (Agent)",
        "",
        "0. **统一搜索入口**: `python .ai/tools/feature_registry/search_assets.py "
        "--query \"关键词\"`，同时搜 Features 资产与参考片段（--json 可机器消费）。",
        "1. 先读本文件了解分区，再到 `catalog.yaml` 按 domain / repo / keyword 检索。",
        "2. 片段位于 `references/<domain>/`，头部注释含出处、许可证、commit。",
        "3. 片段是**学习参考**：适配时必须按本项目约定改造"
        "(class_name 冲突、Health 节点约定、enemies 组等)，禁止机械复制。",
        "4. `parse_status: FAIL` 表示片段依赖原工程上下文，参考思路为主。",
        "",
        "## 分类边界",
        "",
        "- `examples/`(agent 自制示例代码) 与 `code_library/`(网络收集代码) 严格分离。",
        "- `sources/` = 原始下载；`references/` = 蒸馏片段(已加出处头)。",
        "",
        "## 来源仓库",
        "",
        "| Repo | Stars | License | 片段数 |",
        "|---|---|---|---|",
    ]
    for slug, r in sorted(repos.items(), key=lambda kv: -kv[1]["stars"]):
        name = slug.replace("__", "/")
        lines.append(f"| [{name}](https://github.com/{name}) | {r['stars']} | "
                     f"{r['license']} | {r['n']} |")
    lines.append("")
    for d in sorted(domains):
        uniq = [e for e in domains[d] if not e["duplicate_of"]]
        lines += [f"## domain: {d} ({len(uniq)} 片段)", "",
                  "| 片段 | 行数 | Stars | License | 来源 |", "|---|---|---|---|---|"]
        for e in sorted(uniq, key=lambda x: -x["stars"]):
            repo = e["repo"]
            lines.append(f"| `{e['id']}` | {e['lines']} | {e['stars']} | "
                         f"{e['license']} | [{repo}]({e['source_url']}) |")
        lines.append("")
    INDEX_MD.write_text("\n".join(lines), encoding="utf-8")


# ───────────────────────────── check ──────────────────────────────

CHECK_HARNESS_GD = """extends SceneTree

func _init() -> void:
    var args := OS.get_cmdline_user_args()
    if args.size() < 2:
        quit(1)
        return
    var list_file := FileAccess.open(args[0], FileAccess.READ)
    var results := FileAccess.open(args[1], FileAccess.WRITE)
    while not list_file.eof_reached():
        var line := list_file.get_line().strip_edges()
        if line.is_empty():
            continue
        var script := load(line)
        results.store_line(("OK " if script != null else "FAIL ") + line)
    results.close()
    quit()
"""


def cmd_check(args: argparse.Namespace) -> None:
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    src = CHECK_DIR / "src"
    src.mkdir(parents=True, exist_ok=True)
    (CHECK_DIR / "project.godot").write_text(
        'config_version=5\n\n[application]\nconfig/name="snippet_check"\n\n'
        "[debug]\n"
        "gdscript/warnings/inference_on_variant=0\n"
        "gdscript/warnings/inference_on_native=0\n"
        "gdscript/warnings/untyped_declaration=0\n"
        "gdscript/warnings/unsafe_property_access=0\n"
        "gdscript/warnings/unsafe_method_access=0\n"
        "gdscript/warnings/unsafe_cast=0\n"
        "gdscript/warnings/unsafe_call_argument=0\n",
        encoding="utf-8")
    (CHECK_DIR / "check.gd").write_text(CHECK_HARNESS_GD, encoding="utf-8")
    file_list: list[tuple[str, str]] = []  # (res_path, catalog_id)
    for f in sorted(REFERENCES_DIR.rglob("*.gd")):
        domain = f.parent.name
        dst = src / f"{domain}__{f.name}"
        shutil.copy2(f, dst)
        file_list.append((f"res://src/{dst.name}", f.name))
    list_path = CHECK_DIR / "list.txt"
    out_path = CHECK_DIR / "results.txt"
    list_path.write_text("\n".join(p for p, _ in file_list), encoding="utf-8")
    print(f"[check] {len(file_list)} 片段, 运行 headless parse 检查 ...")
    import subprocess
    proc = subprocess.run(
        [GODOT_BIN, "--headless", "--path", str(CHECK_DIR),
         "-s", "res://check.gd", "--", "list.txt", "results.txt"],
        capture_output=True, text=True, timeout=600, cwd=str(CHECK_DIR))
    status_raw = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                status_raw[parts[1]] = parts[0]
    else:
        print(f"[check] 未产生 results.txt (exit={proc.returncode})，"
              f"stderr 前 500 字: {proc.stderr[:500]}")
    by_id = {flat_id: status_raw[res_path] for res_path, flat_id in file_list
             if res_path in status_raw}
    ok = fail = other = 0
    entries = _read_catalog_entries()
    for e in entries:
        if e.get("duplicate_of"):
            e["parse_status"] = "duplicate"
            continue
        if e.get("parse_status") == "skipped_shader":
            continue
        st = by_id.get(e["id"], "unchecked")
        e["parse_status"] = st
        if st == "OK":
            ok += 1
        elif st == "FAIL":
            fail += 1
        else:
            other += 1
    _write_catalog_yaml(entries)
    _write_index_md(entries)
    print(f"[check] OK={ok} FAIL={fail} 其他={other}")

    # ---- 反向一致性：catalog ↔ 磁盘（防止幽灵条目溜进检索） ----
    ids = {e["id"] for e in entries}
    ghosts, bad_dup, legacy_dup = [], [], 0
    unique_cnt = dup_cnt = 0
    for e in entries:
        if e.get("duplicate_of"):
            dup_cnt += 1
            target = e["duplicate_of"]
            if ":" in target:  # 旧格式 slug:repo/path，无法反查保留条目
                legacy_dup += 1
            elif target not in ids:
                bad_dup.append(e["id"])
            continue
        unique_cnt += 1
        if not (REFERENCES_DIR / e["domain"] / e["id"]).is_file():
            ghosts.append(e["id"])
    print(f"[check] 收集 {len(entries)} = 保留 {unique_cnt} + 重复 {dup_cnt}"
          + (f"（旧格式指针 {legacy_dup} 条）" if legacy_dup else ""))
    if ghosts:
        print(f"[check] ERROR: {len(ghosts)} 个非重复条目在磁盘无文件（幽灵条目）")
        for g in ghosts[:10]:
            print("  ghost:", g)
    if bad_dup:
        print(f"[check] ERROR: {len(bad_dup)} 个重复条目的 duplicate_of 指向不存在的 id")
        for b in bad_dup[:10]:
            print("  bad:", b)
    if legacy_dup:
        print("[check] WARN: 存在旧格式 duplicate_of 指针，运行 backfill-meta 迁移")
    if ghosts or bad_dup:
        sys.exit(1)


def _read_catalog_entries() -> list[dict]:
    entries, cur = [], None
    for line in CATALOG_YAML.read_text(encoding="utf-8").splitlines():
        if line.startswith("  - id: "):
            if cur:
                entries.append(cur)
            cur = {"id": json.loads(line.split(": ", 1)[1])}
        elif line.startswith("    ") and cur is not None:
            k, v = line.strip().split(": ", 1)
            val = json.loads(v)
            if k in ("stars", "lines") and isinstance(val, str) and val.isdigit():
                val = int(val)
            if k == "duplicate_of" and val in (None, "None", "null", ""):
                val = None
            cur[k] = val
    if cur:
        entries.append(cur)
    return entries


# ───────────────────────── backfill-meta（数据修缮） ────────────────────────


def _sha_looks_valid(sha: str, branch: str) -> bool:
    """fetch 早期版本把分支名写进 commit_sha；真实 sha 是 7~40 位 hex。"""
    return bool(sha) and sha != branch and all(c in "0123456789abcdef" for c in sha)


def cmd_backfill_meta(args: argparse.Namespace) -> None:
    """修复历史数据：① 回填真实 commit sha（早期 fetch 误存分支名）；
    ② duplicate_of 旧格式 slug:path -> 保留条目 id；③ 同步 catalog 与片段头。"""
    token = args.token or os.environ.get("GITHUB_TOKEN")
    entries = _read_catalog_entries()
    by_slug: dict[str, list[dict]] = {}
    for e in entries:
        by_slug.setdefault(e["repo_slug"], []).append(e)
    ids = {e["id"] for e in entries}
    dup_ids = {e["id"] for e in entries if e.get("duplicate_of")}

    # ---- ① 回填 commit sha ----
    sha_updated, sha_failed = 0, 0
    for repo_dir in sorted(SOURCES_DIR.iterdir()):
        meta_path = repo_dir / "_meta.json"
        if not repo_dir.is_dir() or not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        branch = meta.get("branch", "main")
        if _sha_looks_valid(meta.get("commit_sha", ""), branch) and not args.force:
            continue
        try:
            info = _http_get_json(
                f"https://api.github.com/repos/{meta['full_name']}/commits/{branch}",
                token)
            sha_full = info["sha"]
        except Exception as exc:  # noqa: BLE001
            print(f"[backfill] WARN sha 回填失败 {meta['full_name']}: {exc}")
            sha_failed += 1
            continue
        meta["commit_sha_full"] = sha_full
        meta["commit_sha"] = sha_full[:12]
        meta["backfilled_at"] = _now()
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        for e in by_slug.get(meta["slug"], []):
            e["commit_sha"] = meta["commit_sha"]
        sha_updated += 1
        print(f"[backfill] sha {meta['full_name']}: {branch} -> {sha_full[:12]}")

    # ---- ② duplicate_of 旧格式迁移 + 片段头 Commit 行同步 ----
    dup_migrated, dup_stuck, headers_updated = 0, 0, 0
    for e in entries:
        dup_of = e.get("duplicate_of")
        if dup_of and ":" in dup_of:
            slug, repo_path = dup_of.split(":", 1)
            cand = f"{slug}__{repo_path.replace('/', '__')}"
            if cand in ids and cand not in dup_ids:
                e["duplicate_of"] = cand
                dup_migrated += 1
            else:
                dup_stuck += 1
                print(f"[backfill] WARN duplicate_of 无法迁移: {e['id']} -> {dup_of}")
        if e.get("duplicate_of") or args.skip_headers:
            continue
        ref = REFERENCES_DIR / e["domain"] / e["id"]
        if not ref.is_file():
            continue
        lines = ref.read_text(encoding="utf-8").splitlines(keepends=True)
        if len(lines) >= 3 and lines[2].startswith("# Commit:  "):
            want = f"# Commit:  {e['commit_sha']}\n"
            if lines[2] != want:
                lines[2] = want
                ref.write_text("".join(lines), encoding="utf-8")
                headers_updated += 1

    _write_catalog_yaml(entries)
    _write_index_md(entries)
    print(f"[backfill] sha 回填 {sha_updated} 个仓库"
          + (f"（失败 {sha_failed}）" if sha_failed else "")
          + f"；duplicate_of 迁移 {dup_migrated} 条"
          + (f"（滞留 {dup_stuck} 条）" if dup_stuck else "")
          + f"；片段头 Commit 行更新 {headers_updated} 个")


# ───────────────────────────── promote ────────────────────────────

FEATURE_YAML_TEMPLATE = """# Feature Metadata: {name}
# 格式规范见 Features/FEATURE_SCHEMA.md。
# TODO(agent): 抽象简化后补全 summary / provides / interfaces / ownership 等字段。

id: {name}
version: 1
category: {category}

summary: TODO 一句话职责描述（抽象自外部片段，抽象后重写本行）。

provides:
  - TODO_provides_tag

requires: []

capabilities:
  required: []

interfaces:
  methods: []
  signals: []
  exports: []

ownership:
  state: []
  rules:
    - TODO 抽象要点：剥除原工程耦合后的核心逻辑与约定

composition:
  entry_scene: ""    # TODO 入口场景；无场景时说明如何挂载
  usage: "TODO 使用方式；来源片段: {source_url}"
  related_features: []

validation:
  self_test: test_{name}.gd
  command: godot --headless --path . -s res://Features/{name}/test_{name}.gd
  expectations:
    - 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1

relations:
  works_with: []
  commonly_used_with: []
  conflicts: []
  entity_roles: []

# 来源片段（仅供学习，抽象后此注释可删除）：
#   snippet_id: {snippet_id}
#   source_url: {source_url}
#   repo: {repo} (star {stars}) | License: {license}
"""

README_TEMPLATE = """# {name}

> 状态：**脚手架**（由 github_collector.py promote 生成，尚未完成抽象）。

## 来源片段

- snippet: `{snippet_id}`
- 出处: {source_url}
- 仓库: {repo}（star {stars}）| License: {license}

## 抽象清单（agent 执行）

1. 通读片段（`<name>.gd` 为原始拷贝），理解思路。
2. 按本项目约定重写：剥除具体 NodePath / autoload 依赖；Health 子节点、
   `add_to_group("enemies")`、Orchestration 契约等按需适配。
3. 重写 `<name>.gd` 为正式实现，重写 feature.yaml 的
   summary / provides / interfaces / ownership。
4. 实现 `test_{name}.gd`（当前是 FAIL 占位，必须替换为真实自测）。
5. 跑 `python .ai/tools/feature_registry/build_feature_index.py` 刷新资产库，
   并用 feature.yaml 里的 validation.command 验证。

片段许可证: {license}（对外发布需遵守，含署名义务）。
"""

TEST_TEMPLATE = """extends SceneTree

# TODO(agent): 替换为真实自测。当前为 promote 脚手架占位，恒定 FAIL。
# 参考: Features/health/test_health.gd 等既有 Feature 的写法。

func _init() -> void:
    print("FAIL {name}: test not implemented (scaffold placeholder)")
    quit(1)
"""


def cmd_promote(args: argparse.Namespace) -> None:
    name = args.name
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        sys.exit(f"[promote] 非法 Feature 名: {name}（需 snake_case）")
    dest = FEATURE_ROOT / name
    if dest.exists():
        sys.exit(f"[promote] Feature 已存在: {dest}")
    entries = {e["id"]: e for e in _read_catalog_entries()}
    entry = entries.get(args.snippet)
    if entry is None:
        sys.exit(f"[promote] catalog 中无此片段: {args.snippet}")
    if entry.get("duplicate_of"):
        sys.exit(f"[promote] 该片段是重复项，原件: {entry['duplicate_of']}")
    snippet_file = (REFERENCES_DIR / entry["domain"] / entry["id"])
    if not snippet_file.exists():
        sys.exit(f"[promote] 片段文件缺失: {snippet_file}")
    if entry.get("license") not in ALLOWED_LICENSES:
        print(f"[promote] 警告: 片段许可证 {entry.get('license')} 不在白名单，"
              f"只可参考思路，不可拷贝代码")

    dest.mkdir(parents=True)
    (dest / f"{name}.gd").write_text(
        snippet_file.read_text(encoding="utf-8")
        + "\n\n# ===== TODO(agent): 以上是原始片段拷贝，抽象重写为正式实现 =====\n",
        encoding="utf-8")
    ctx = {
        "name": name, "category": args.category,
        "snippet_id": entry["id"], "source_url": entry["source_url"],
        "repo": entry["repo"], "stars": entry["stars"],
        "license": entry["license"],
    }
    (dest / "feature.yaml").write_text(
        FEATURE_YAML_TEMPLATE.format(**ctx), encoding="utf-8")
    (dest / "README.md").write_text(
        README_TEMPLATE.format(**ctx), encoding="utf-8")
    (dest / f"test_{name}.gd").write_text(
        TEST_TEMPLATE.format(**ctx), encoding="utf-8")
    print(f"[promote] 脚手架完成: {dest}")
    import subprocess
    r = subprocess.run([sys.executable, str(FEATURE_INDEX_BUILDER)],
                       capture_output=True, text=True)
    print(f"[promote] 资产库刷新: {r.stdout.strip() or r.stderr.strip()}")
    print(f"[promote] 下一步（agent）: 抽象重写 {name}.gd → 补全 feature.yaml → "
          f"实现 test_{name}.gd → 验证")


# ───────────────────────────── main ───────────────────────────────


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search")
    s.add_argument("--min-stars", type=int, default=50)
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--license", default=None,
                   help="逗号分隔 SPDX 白名单，缺省用内置宽松许可证表")
    s.add_argument("--include-forks", action="store_true")
    s.add_argument("--token", default=None)
    s.set_defaults(fn=cmd_search)

    f = sub.add_parser("fetch")
    f.add_argument("--repo", default=None)
    f.add_argument("--branch", default="main")
    f.add_argument("--top", type=int, default=10)
    f.add_argument("--all", action="store_true", help="不按许可证过滤")
    f.add_argument("--force", action="store_true")
    f.set_defaults(fn=cmd_fetch)

    c = sub.add_parser("catalog")
    c.set_defaults(fn=cmd_catalog)

    k = sub.add_parser("check")
    k.set_defaults(fn=cmd_check)

    r = sub.add_parser("reindex", help="从 catalog.yaml 重读并重写 INDEX.md")
    r.set_defaults(fn=lambda _a: _write_index_md(_read_catalog_entries()))

    bf = sub.add_parser(
        "backfill-meta",
        help="回填真实 commit sha + 迁移 duplicate_of 旧格式 + 同步片段头")
    bf.add_argument("--token", default=None)
    bf.add_argument("--force", action="store_true", help="sha 已有效也强制重取")
    bf.add_argument("--skip-headers", action="store_true",
                    help="跳过片段头 Commit 行同步（省 IO）")
    bf.set_defaults(fn=cmd_backfill_meta)

    pm = sub.add_parser(
        "promote", help="把片段脚手架成 Features/<name>/ 并刷新资产库")
    pm.add_argument("--snippet", required=True, help="catalog 片段 id")
    pm.add_argument("--name", required=True, help="新 Feature 名（snake_case）")
    pm.add_argument("--category", default="component")
    pm.set_defaults(fn=cmd_promote)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
