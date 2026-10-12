#!/usr/bin/env python3
"""Godot Runtime Launcher（项目级）—— 运行整个 Godot Project。

    godot --headless --path <project> --quit-after <frames>
        （不传 --scene，运行 project.godot 的 run/main_scene）

与 run_scene.py 的区别：
    run_scene.py   —— 验证「某一个 Scene」的运行时正确性
    run_project.py —— 验证「项目主场景」的运行时正确性

两者共用同一个 Runtime Runner 内核（run_scene.run_runtime），
产出同一份 runtime_result 契约，不产生第二套运行逻辑。

用法:
    python run_project.py --project .
    python run_project.py --project . --timeout 30 --out /tmp/project_result.json

退出码: 0 = PASS；1 = FAIL / TIMEOUT / CRASH；2 = 输入错误。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_scene import (                        # noqa: E402
    RuntimeInputError,
    print_result,
    project_main_scene,
    run_runtime,
)
from runtime_result import (                   # noqa: E402
    find_project_root,
    validate_result,
    write_result,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Godot project main scene headless.")
    parser.add_argument("--project", default=".", help="Godot project directory (contains project.godot)")
    parser.add_argument("--timeout", type=float, default=None, help="Wall-clock timeout in seconds")
    parser.add_argument("--frames", type=int, default=None, help="--quit-after frame count")
    parser.add_argument("--out", default="", help="Write runtime_result JSON to this path")
    parser.add_argument("--json", action="store_true", help="Print the full runtime_result JSON")
    parser.add_argument("--show-output", action="store_true", help="Print raw Godot output")
    parser.add_argument("--no-logs", action="store_true", help="Do not save raw logs")
    args = parser.parse_args(argv)

    root = find_project_root(args.project)
    if root is None:
        print("FAIL: project.godot not found (project=%s)" % args.project)
        return 2

    print("Project main scene: %s" % (project_main_scene(root) or "<unset>"))
    try:
        result = run_runtime(
            project=root,
            scene="",
            timeout=args.timeout,
            quit_after=args.frames,
            write_logs=False if args.no_logs else None,
            tag="project",
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
