#!/usr/bin/env python3
"""Repair Engine —— 确定性、最小范围的修复执行器。

本模块负责「怎么改」，不负责「该不该改」（那是 repair_plan.py 的安全策略）。

当前支持的修复策略（唯一一种，刻意保持狭窄）：

    node_path_literal
        Node not found 且错误位置能定位到脚本/场景中的硬编码节点路径字面量时：
          1. 解析场景，得到场景内真实节点路径
          2. 用名称相似度在真实节点里找唯一候选
          3. 把出错的字面量替换为候选节点的正确相对路径

修复约束：
    - 每次只改一个文件、只做一处字面量替换
    - 替换前必须确认目标字面量在文件中唯一出现（否则拒绝修改，避免误伤）
    - 保持原文件换行风格（不重写整个文件）
    - 修改前备份原文，支持回滚

不负责：分类（diagnose_runtime.py）、策略选择（repair_plan.py）、流程编排（self_repair.py）。
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_result import find_godot_binary, load_contract          # noqa: E402

# ---------- 场景解析 ----------

NODE_BLOCK_RE = re.compile(r'^\[node name="(?P<name>[^"]*)"(?P<attrs>[^\]]*)\]\s*$(?P<body>(?:\n(?!\[).*$)*)',
                           re.M)
EXT_RESOURCE_RE = re.compile(r'^\[ext_resource[^\]]*?path="(?P<path>[^"]+)"[^\]]*?id="(?P<id>[^"]+)"[^\]]*\]',
                             re.M)
EXT_RESOURCE_RE_ALT = re.compile(r'^\[ext_resource[^\]]*?id="(?P<id>[^"]+)"[^\]]*?path="(?P<path>[^"]+)"[^\]]*\]',
                                 re.M)
PARENT_RE = re.compile(r'\bparent="(?P<parent>[^"]*)"')
SCRIPT_PROP_RE = re.compile(r'^\s*script\s*=\s*ExtResource\("(?P<id>[^"]+)"\)', re.M)
NODE_PATH_TOKEN_RE = re.compile(r'Node not found:\s*"?([^"\n()]+?)"?\s*(?:\(relative to|\(|$)')
RELATIVE_TO_RE = re.compile(r'relative to\s+"([^"]*)"')


def read_text_preserve(path: Path) -> str:
    """按原始换行读取（不转换行尾），避免修复时重写整个文件的换行风格。"""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text_preserve(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def parse_scene_nodes(text: str) -> list[dict[str, Any]]:
    """解析 .tscn 的节点块，返回带场景内绝对路径的节点列表。

    路径表示：根节点为 "."，子节点为 "Child"，孙节点为 "Child/GrandChild"。
    """
    nodes: list[dict[str, Any]] = []
    for match in NODE_BLOCK_RE.finditer(text):
        name = match.group("name")
        attrs = match.group("attrs") or ""
        body = match.group("body") or ""
        parent_match = PARENT_RE.search(attrs)
        parent = parent_match.group("parent") if parent_match else ""
        if not parent:
            path = "."
        elif parent == ".":
            path = name
        else:
            path = "%s/%s" % (parent.replace("./", ""), name)
        script_id = ""
        script_match = SCRIPT_PROP_RE.search(body)
        if script_match:
            script_id = script_match.group("id")
        nodes.append({
            "name": name,
            "parent": parent,
            "path": path,
            "script_id": script_id,
            "body": body,
        })
    return nodes


def ext_resource_paths(text: str) -> dict[str, str]:
    resources: dict[str, str] = {}
    for match in EXT_RESOURCE_RE.finditer(text):
        resources[match.group("id")] = match.group("path")
    for match in EXT_RESOURCE_RE_ALT.finditer(text):
        resources.setdefault(match.group("id"), match.group("path"))
    return resources


def scene_disk_path(project_root: Path, scene: str) -> Path | None:
    if not scene.startswith("res://"):
        return None
    return project_root / scene[len("res://"):].replace("/", os.sep)


def relative_node_path(owner_path: str, target_path: str) -> str:
    """计算场景内两个节点之间的相对路径（Godot get_node 语义）。"""
    owner = [] if owner_path == "." else owner_path.split("/")
    target = [] if target_path == "." else target_path.split("/")
    common = 0
    while common < len(owner) and common < len(target) and owner[common] == target[common]:
        common += 1
    ups = len(owner) - common
    down = target[common:]
    if not down:
        return "." if ups == 0 else "../" * ups
    return "../" * ups + "/".join(down)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def name_similarity(token: str, candidate: str) -> float:
    """名称相似度（0..1），用于确定唯一候选节点。"""
    left, right = normalize_name(token), normalize_name(candidate)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    ratio = difflib.SequenceMatcher(None, left, right).ratio()
    if left in right or right in left:
        return min(0.95, 0.6 + 0.4 * ratio)
    return ratio


def rank_candidates(nodes: list[dict[str, Any]], owner_path: str, token: str) -> list[tuple[float, dict]]:
    ranked = []
    for node in nodes:
        if node["path"] == owner_path:
            continue
        score = name_similarity(token, node["name"])
        ranked.append((score, node))
    ranked.sort(key=lambda item: (-item[0], item[1]["path"]))
    return ranked


# ---------- 出错字面量定位 ----------

QUOTED_FORMS = ('"%s"', "'%s'")


def _occurrences(text: str, needle: str) -> int:
    return text.count(needle)


def find_literal(target_text: str, token: str) -> dict[str, Any] | None:
    """在目标文件中查找唯一可替换的节点路径字面量。"""
    forms = [form % token for form in QUOTED_FORMS]
    forms.append("$%s" % token)
    for form in forms:
        count = _occurrences(target_text, form)
        if count == 1:
            return {"form": form, "topic": token, "count": count}
        if count > 1:
            return {"form": form, "topic": token, "count": count, "ambiguous": True}
    return None


# ---------- 分析与应用 ----------


def analyze_node_path_error(project_root: Path, error: dict, scene: str) -> dict[str, Any]:
    """分析一条 node_not_found 错误，给出可执行的修复分析（不修改项目）。"""
    analysis: dict[str, Any] = {"ok": False, "reason": "", "strategy": "node_path_literal"}
    message = str(error.get("message") or "")
    token_match = NODE_PATH_TOKEN_RE.search(message)
    if not token_match:
        analysis["reason"] = "node path token not found in error message"
        return analysis
    token = token_match.group(1).strip()
    if not token:
        analysis["reason"] = "empty node path token"
        return analysis

    scene_path = scene_disk_path(project_root, scene or "")
    owner_hint = RELATIVE_TO_RE.search(message)
    owner_abs = owner_hint.group(1) if owner_hint else ""

    nodes: list[dict[str, Any]] = []
    scene_text = ""
    if scene_path and scene_path.is_file():
        scene_text = read_text_preserve(scene_path)
        nodes = parse_scene_nodes(scene_text)

    # diagnosis 条目用 file 承载位置；runtime_result 原始事件用 script
    script = str(error.get("script") or error.get("file") or "")
    analysis["owner_hint"] = owner_abs
    analysis["scene"] = scene
    analysis["token"] = token

    # 1. 定位字面量：优先错误发生脚本，其次验证场景
    script_path = None
    if script.startswith("res://"):
        candidate = project_root / script[len("res://"):].replace("/", os.sep)
        if candidate.is_file():
            script_path = candidate

    literal = None
    target_path = None
    if script_path is not None:
        script_text = read_text_preserve(script_path)
        found = find_literal(script_text, token)
        if found and not found.get("ambiguous"):
            literal, target_path = found, script_path
        elif found and found.get("ambiguous"):
            analysis["reason"] = ("literal %r appears %d times in %s; refusing to edit"
                                  % (found["form"], found["count"], script.relative_to(project_root).as_posix()))
            return analysis

    if literal is None and scene_path is not None and scene_path.is_file():
        found = find_literal(scene_text, token)
        if found and not found.get("ambiguous"):
            literal, target_path = found, scene_path
        elif found and found.get("ambiguous"):
            analysis["reason"] = ("literal %r appears %d times in %s; refusing to edit"
                                  % (found["form"], found["count"],
                                     scene_path.relative_to(project_root).as_posix()))
            return analysis

    if literal is None or target_path is None:
        analysis["reason"] = "no unique node path literal found for token %r" % token
        return analysis

    # 2. 确定 owner 节点（脚本挂载点）与候选节点
    if not nodes:
        analysis["reason"] = "scene could not be parsed: %s" % (scene or "<none>")
        return analysis

    owner_path = ""
    if script_path is not None:
        resources = ext_resource_paths(scene_text)
        script_ref = "res://" + script_path.relative_to(project_root).as_posix()
        for node in nodes:
            resource_id = node.get("script_id") or ""
            if resource_id and resources.get(resource_id) == script_ref:
                owner_path = node["path"]
                break
    if not owner_path and owner_abs.startswith("/root/"):
        root_name = owner_abs.split("/")[2] if len(owner_abs.split("/")) > 2 else ""
        for node in nodes:
            if node["name"] == root_name:
                owner_path = node["path"]
                break
    if not owner_path:
        owner_path = "."

    ranked = rank_candidates(nodes, owner_path, token)
    analysis["owner_path"] = owner_path
    analysis["candidates"] = [
        {"node": node["name"], "path": relative_node_path(owner_path, node["path"]), "score": round(score, 3)}
        for score, node in ranked[:3]
    ]
    if not ranked:
        analysis["reason"] = "scene has no node other than the script owner"
        return analysis

    best_score, best_node = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < 0.75:
        analysis["reason"] = ("no confident node candidate in scene (best=%r score=%.2f)"
                              % (best_node["name"], best_score))
        return analysis

    confidence = "high" if best_score >= 0.85 else "medium"
    analysis.update({
        "ok": True,
        "target_file": target_path,
        "target_rel": "res://" + target_path.relative_to(project_root).as_posix(),
        "old_literal": literal["form"],
        "new_literal": literal["form"].replace(token, relative_node_path(owner_path, best_node["path"])),
        "token": token,
        "candidate": best_node,
        "candidate_path": relative_node_path(owner_path, best_node["path"]),
        "confidence": confidence,
        "score": round(best_score, 3),
        "runner_up": round(second_score, 3) if len(ranked) > 1 else None,
        "reason": "",
    })
    return analysis


def apply_change(target_file: Path, old_literal: str, new_literal: str) -> dict[str, Any]:
    """应用单点字面量替换（保持换行风格，返回备份）。"""
    text = read_text_preserve(target_file)
    count = text.count(old_literal)
    if count != 1:
        return {"ok": False, "reason": "literal %r occurs %d times; refusing to edit" % (old_literal, count)}
    updated = text.replace(old_literal, new_literal, 1)
    backup = {"file": str(target_file), "content": text}
    write_text_preserve(target_file, updated)
    return {"ok": True, "backup": backup, "diff": unified_diff(text, updated, target_file.name)}


def revert_change(backup: dict[str, Any]) -> None:
    target = Path(backup["file"])
    write_text_preserve(target, backup["content"])


def unified_diff(before: str, after: str, name: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile="a/%s" % name, tofile="b/%s" % name, lineterm="", n=2,
    )
    return "\n".join(diff)


# ---------- 静态验证 ----------

def check_script_parses(project_root: Path, script_ref: str,
                        godot: Path | None = None, contract: dict | None = None) -> dict[str, Any]:
    """用 godot --check-only --script 做 GDScript 解析校验。"""
    contract = contract or load_contract()
    godot = godot or find_godot_binary(project_root, contract)
    if godot is None:
        return {"ok": False, "name": "gdscript parse check", "reason": "godot executable not found"}
    command = [str(godot), "--headless", "--path", str(project_root), "--check-only", "--script", script_ref]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60, stdin=subprocess.DEVNULL, cwd=str(project_root))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "name": "gdscript parse check", "reason": str(exc)}
    detail = (proc.stderr or proc.stdout or "").strip()
    return {
        "ok": proc.returncode == 0,
        "name": "gdscript parse check (%s)" % script_ref,
        "reason": "" if proc.returncode == 0 else detail[-400:],
        "command": " ".join(command),
    }


def check_scene_node_paths(project_root: Path, scene: str) -> dict[str, Any]:
    """结构校验：场景内所有节点的 parent 路径必须可达。"""
    path = scene_disk_path(project_root, scene or "")
    if path is None or not path.is_file():
        return {"ok": False, "name": "scene structure check", "reason": "scene not found: %s" % scene}
    text = read_text_preserve(path)
    nodes = parse_scene_nodes(text)
    known = {node["path"] for node in nodes} | {"."}
    findings = []
    for node in nodes:
        if node["parent"] and node["parent"] != "." and node["parent"] not in known:
            findings.append("node %s parent=%r is not declared in scene" % (node["name"], node["parent"]))
    return {
        "ok": not findings,
        "name": "scene structure check (%s, %d node(s))" % (scene, len(nodes)),
        "reason": "; ".join(findings),
    }


def static_validation(project_root: Path, plan: dict, changed_files: list | None = None,
                      contract: dict | None = None,
                      run_framework_validator: bool = True) -> dict[str, Any]:
    """修复后的静态验证：脚本解析 + 场景结构（+ 可选 Framework Validator）。"""
    contract = contract or load_contract()
    steps: list[dict[str, Any]] = []
    changed = [str(path) for path in (changed_files or [])]

    for rel in changed:
        if rel.lower().endswith(".gd"):
            steps.append(check_script_parses(project_root, "res://" + rel.replace(os.sep, "/"), contract=contract))

    scene = str(plan.get("error", {}).get("scene") or plan.get("_scene") or "")
    if scene:
        steps.append(check_scene_node_paths(project_root, scene))

    validator = project_root / ".ai" / "tools" / "validator" / "validate.py"
    if run_framework_validator and validator.is_file() and (project_root / ".ai" / "config" / "agent.yaml").is_file():
        try:
            proc = subprocess.run(
                [sys.executable, str(validator)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=300, stdin=subprocess.DEVNULL, cwd=str(project_root),
            )
            tail = "\n".join((proc.stdout or "").strip().splitlines()[-3:])
            steps.append({
                "ok": proc.returncode == 0,
                "name": "framework validator (validate.py)",
                "reason": "" if proc.returncode == 0 else tail,
            })
        except (OSError, subprocess.TimeoutExpired) as exc:
            steps.append({"ok": False, "name": "framework validator (validate.py)", "reason": str(exc)})

    return {"ok": all(step.get("ok") for step in steps) if steps else True, "steps": steps}


def main(argv=None) -> int:
    """独立分析入口：给出某条错误的修复分析（不修改项目）。"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Analyze a node_not_found error into a concrete edit (dry run).")
    parser.add_argument("--project", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--message", required=True, help="Error message, e.g. 'Node not found: \"Helth\" (relative to \"/root/X\").'")
    parser.add_argument("--script", default="")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    analysis = analyze_node_path_error(
        project_root,
        {"message": args.message, "script": args.script},
        args.scene,
    )
    printable = {key: value for key, value in analysis.items() if key != "candidate"}
    print(json.dumps(printable, indent=2, ensure_ascii=False, default=str))
    return 0 if analysis.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
