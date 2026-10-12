#!/usr/bin/env python3
"""Godot Runtime Launcher —— 运行指定 Scene 并产出 runtime_result。

    godot --headless --path <project> --quit-after <frames> --scene <scene>

职责：
    - 启动 Godot（headless）运行指定 Scene
    - 捕获 stdout / stderr / exit code / duration
    - 超时强杀（TIMEOUT）、异常退出识别（CRASH）
    - 调用 capture_output 做结构化解析（保留 raw stdout / stderr）
    - 产出 runtime_result（契约见 .ai/context/runtime_result_schema.yaml）

不负责：错误分类（diagnose_runtime.py）、修复（self_repair.py）。

用法:
    python run_scene.py --scene res://Scenes/EnemyBasic.tscn
    python run_scene.py --project . --scene res://Scenes/EnemyBasic.tscn --timeout 30
    python run_scene.py --scene res://Scenes/EnemyBasic.tscn --out /tmp/runtime_result.json

退出码: 0 = PASS；1 = FAIL / TIMEOUT / CRASH；2 = 输入错误。

架构约束：Runtime Runner 只负责运行与观测，不修改项目、不做诊断。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capture_output import parse_output                                    # noqa: E402
from runtime_result import (                                              # noqa: E402
    STATUS_CRASH,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_TIMEOUT,
    build_result,
    find_godot_binary,
    find_project_root,
    load_contract,
    save_logs,
    summarize,
    validate_result,
    write_result,
)

MAIN_SCENE_RE = re.compile(r'^\s*run/main_scene\s*=\s*"([^"]*)"', re.M)


class RuntimeInputError(Exception):
    """输入错误（项目/场景/Godot 不存在），对应退出码 2。"""


def normalize_scene_ref(project_root: Path, scene: str) -> str:
    """把场景引用规范化为 res:// 形式。"""
    scene = (scene or "").strip()
    if not scene:
        return ""
    if scene.startswith("res://"):
        return scene
    candidate = Path(scene)
    if candidate.is_absolute():
        try:
            return "res://" + candidate.resolve().relative_to(project_root).as_posix()
        except ValueError:
            return scene
    return "res://" + scene.replace("\\", "/").lstrip("./")


def scene_disk_path(project_root: Path, scene: str) -> Path | None:
    """res:// 场景引用 -> 磁盘路径。"""
    if not scene.startswith("res://"):
        return None
    return project_root / scene[len("res://"):].replace("/", os.sep)


def project_main_scene(project_root: Path) -> str:
    """读取 project.godot 的 run/main_scene（缺失返回空串）。"""
    config = project_root / "project.godot"
    if not config.is_file():
        return ""
    match = MAIN_SCENE_RE.search(config.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else ""


def build_command(godot: Path, project_root: Path, scene: str, quit_after: int) -> list[str]:
    command = [str(godot), "--headless", "--path", str(project_root)]
    if quit_after and quit_after > 0:
        command += ["--quit-after", str(quit_after)]
    if scene:
        command += ["--scene", scene]
    return command


def _missing_scene_result(project_root: Path, scene: str, timeout: int,
                          godot: Path | None, quit_after: int) -> dict:
    """Scene 在项目中不存在：不启动 Godot，直接产出可诊断的结果。"""
    entry = {
        "type": "runtime_error",
        "severity": "error",
        "message": "Scene not found in project: %s" % scene,
        "detail": "requested scene file does not exist under %s" % project_root,
        "script": "",
        "line": 0,
        "function": "",
        "source": "runner",
        "patterns": ["resource_missing"],
        "repeat": 1,
    }
    return build_result(
        status=STATUS_FAIL,
        scene=scene,
        exit_code=None,
        duration=0.0,
        stdout="",
        stderr=entry["message"] + "\n",
        errors=[entry],
        warnings=[],
        timeout=False,
        crash=False,
        command=[],
        project=str(project_root),
        godot=str(godot or ""),
        run_frames=quit_after,
        playtest_note="scene_missing_precheck",
    )


def run_runtime(project: str | os.PathLike | None = None,
                scene: str = "",
                timeout: float | None = None,
                quit_after: int | None = None,
                contract: dict | None = None,
                godot_path: str | os.PathLike | None = None,
                use_main_scene: bool = True,
                tag: str = "scene",
                write_logs: bool | None = None,
                log_dir: str | os.PathLike | None = None) -> dict:
    """运行 Scene（或项目主场景）并返回 runtime_result。

    输入错误抛 RuntimeInputError（项目不存在 / Godot 找不到）。
    """
    contract = contract or load_contract()
    root = find_project_root(project)
    if root is None:
        raise RuntimeInputError("project.godot not found (project=%s)" % (project or os.getcwd()))

    if not scene and use_main_scene:
        scene = project_main_scene(root)
    scene = normalize_scene_ref(root, scene)

    godot = Path(godot_path) if godot_path else find_godot_binary(root, contract)
    if godot is None or not godot.is_file():
        raise RuntimeInputError(
            "godot executable not found; set GODOT_BIN or runtime_playtest.godot_binary "
            "in .ai/config/runtime-playtest.yaml"
        )

    budget = float(timeout if timeout is not None else contract.get("timeout", 30) or 30)
    frames = int(quit_after if quit_after is not None else contract.get("run_frames", 60) or 60)

    if scene:
        disk = scene_disk_path(root, scene)
        if disk is not None and not disk.is_file():
            result = _missing_scene_result(root, scene, budget, godot, frames)
            result["errors"][0]["classification"] = "scene_load_error"
            _maybe_save(result, contract, tag, log_dir, write_logs)
            return result

    command = build_command(godot, root, scene, frames)
    started = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            cwd=str(root),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, stderr = proc.communicate(timeout=budget)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = proc.returncode
    except OSError as exc:
        raise RuntimeInputError("cannot start godot: %s" % exc)
    duration = time.monotonic() - started

    parsed = parse_output(stdout or "", stderr or "")
    errors = parsed["parsed_errors"]
    warnings = parsed["parsed_warnings"]

    if timed_out:
        status = STATUS_TIMEOUT
    elif errors and contract.get("fail_on_error", True):
        status = STATUS_FAIL
    elif warnings and contract.get("fail_on_warning", False):
        status = STATUS_FAIL
    elif exit_code not in (0, None):
        status = STATUS_CRASH
    else:
        status = STATUS_PASS

    crash = status == STATUS_CRASH
    capture = bool(contract.get("capture_output", True))
    result = build_result(
        status=status,
        scene=scene,
        exit_code=exit_code,
        duration=duration,
        stdout=(stdout or "") if capture else "",
        stderr=(stderr or "") if capture else "",
        errors=errors,
        warnings=warnings,
        timeout=timed_out,
        crash=crash,
        command=command,
        project=str(root),
        godot=str(godot),
        run_frames=frames,
        playtest_note="timeout after %.0fs" % budget if timed_out else "",
    )
    _maybe_save(result, contract, tag, log_dir, write_logs)
    return result


def _maybe_save(result: dict, contract: dict, tag: str,
                log_dir: str | os.PathLike | None, write_logs: bool | None) -> None:
    enabled = contract.get("save_logs", True) if write_logs is None else write_logs
    if not enabled:
        return
    directory = log_dir or (Path(result.get("project") or ".") / contract.get("log_dir", ".ai/memory/runtime-logs"))
    try:
        paths = save_logs(result, tag=tag, log_dir=directory)
        result["log_path"] = paths["result"]
    except OSError:
        # 日志写入失败不改变运行结论
        result["log_path"] = ""


def print_result(result: dict, json_output: bool = False, show_output: bool = False) -> int:
    if json_output:
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Runtime Playtest")
        print("Scene:    %s" % (result.get("scene") or "<project main scene>"))
        print("Command:  %s" % " ".join(result.get("command") or []))
        print("Result:   %s" % summarize(result))
        for entry in result.get("errors") or []:
            location = entry.get("script") or "<engine>"
            if entry.get("line"):
                location += ":%d" % entry["line"]
            print("  ERROR: %s  (%s)" % (entry.get("message", "").strip(), location))
        for entry in result.get("warnings") or []:
            print("  WARNING: %s" % entry.get("message", "").strip())
        if show_output and result.get("stdout"):
            print("--- raw output ---")
            print(result["stdout"])
    return 0 if result.get("status") == STATUS_PASS else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a Godot scene headless and capture the runtime result.")
    parser.add_argument("--scene", required=True, help="Scene reference, e.g. res://Scenes/EnemyBasic.tscn")
    parser.add_argument("--project", default=".", help="Godot project directory (contains project.godot)")
    parser.add_argument("--timeout", type=float, default=None, help="Wall-clock timeout in seconds (default: contract)")
    parser.add_argument("--frames", type=int, default=None, help="--quit-after frame count (default: contract)")
    parser.add_argument("--out", default="", help="Write runtime_result JSON to this path")
    parser.add_argument("--json", action="store_true", help="Print the full runtime_result JSON")
    parser.add_argument("--show-output", action="store_true", help="Print raw Godot output")
    parser.add_argument("--no-logs", action="store_true", help="Do not save raw logs")
    args = parser.parse_args(argv)

    try:
        result = run_runtime(
            project=args.project,
            scene=args.scene,
            timeout=args.timeout,
            quit_after=args.frames,
            write_logs=False if args.no_logs else None,
        )
    except RuntimeInputError as exc:
        print("FAIL: %s" % exc)
        return 2

    schema_errors = validate_result(result)
    if args.out:
        write_result(result, args.out)
        print("runtime_result written: %s" % args.out)
    code = print_result(result, json_output=args.json, show_output=args.show_output)
    for error in schema_errors:
        print("SCHEMA ERROR: %s" % error)
    return code if not schema_errors else 2


if __name__ == "__main__":
    sys.exit(main())
