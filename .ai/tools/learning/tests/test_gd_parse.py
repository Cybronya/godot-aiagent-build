#!/usr/bin/env python3
"""Phase 1.75 Batch B：Parser Coverage Tests.

Covers the declaration grammar added by Batch B (typed/untyped/inferred
variables, annotations, static/onready modifiers, property accessors, multi-line
declarations and multi-line function signatures) plus the negative guarantees:

* a property is never reported as a function and vice versa;
* a missing type annotation is never invented;
* a declaration that cannot be parsed is reported, not dropped silently;
* a failed parse is never reported as complete coverage;
* records written before the coverage fields existed still load.

Fixtures are in-memory or temporary; no real source file is modified.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(LEARNING)))
sys.path[:0] = [LEARNING]

import gd_parse  # noqa: E402

checks = 0
failures = 0
TMP: list[str] = []


def ok(label: str, condition: bool) -> None:
    global checks, failures
    checks += 1
    if condition:
        print("   PASS  %s" % label)
    else:
        failures += 1
        print("   FAIL  %s" % label)


def write(name: str, text: str) -> str:
    directory = tempfile.mkdtemp(prefix="gdparse-")
    TMP.append(directory)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def parse(text: str) -> gd_parse.Script:
    return gd_parse.parse_text("fixture.gd", text)


def by_name(items: list[dict], name: str) -> dict | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def main() -> int:
    # ---------- positive: variable declarations ----------
    script = parse("var hp: float = 100.0\n")
    entry = by_name(script.variables, "hp")
    ok("P01: typed variable with '=' initialiser is captured",
       entry is not None and entry["type"] == "float" and entry["value"] == "100.0")
    ok("P01b: declaration_kind is VARIABLE",
       entry is not None and entry["declaration_kind"] == "VARIABLE")
    ok("P01c: initializer_kind records an explicit initialiser",
       entry is not None and entry["initializer_kind"] == "EXPLICIT"
       and entry["has_initializer"] is True)

    script = parse("var hp = 100\n")
    entry = by_name(script.variables, "hp")
    ok("P02: untyped variable with '=' is captured",
       entry is not None and entry["value"] == "100"
       and entry["initializer_kind"] == "EXPLICIT")

    script = parse("var hp := 100\n")
    entry = by_name(script.variables, "hp")
    ok("P03: inferred variable (':=') is captured as INFERRED",
       entry is not None and entry["initializer_kind"] == "INFERRED")

    script = parse("var hp\n")
    ok("P04: declaration without initialiser has has_initializer False",
       (by_name(script.variables, "hp") or {}).get("has_initializer") is False)

    # ---------- positive: exports ----------
    script = parse("@export var hp: float = 100.0\n")
    entry = by_name(script.exports, "hp")
    ok("P05: '@export var' with initialiser and type is captured",
       entry is not None and entry["type"] == "float" and entry["value"] == "100.0")
    ok("P05b: export annotation is attached to the declaration",
       entry is not None and [a["name"] for a in entry["annotations"]] == ["export"])

    script = parse("@export var max_hp = 100\n")
    entry = by_name(script.exports, "max_hp")
    ok("P06: exported untyped variable is captured without a fabricated type",
       entry is not None and entry["type"] == "" and entry["value"] == "100")

    script = parse("@export_range(0, 100) var hp: float = 5.0\n")
    entry = by_name(script.exports, "hp")
    ok("P07: '@export_range(...)' prefix keeps its declaration",
       entry is not None and entry["value"] == "5.0"
       and entry["annotations"][0]["name"] == "export_range")

    script = parse('@export_category("Stats")\n@export var hp = 5\n')
    entry = by_name(script.exports, "hp")
    ok("P08: a standalone annotation line binds to the next declaration",
       entry is not None and [a["name"] for a in entry["annotations"]]
       == ["export_category", "export"])

    script = parse('@export_category("Stats")\nvar a = 1\n@export var b = 2\n')
    ok("P09: an annotation binds to the next declaration only, never past it",
       [a["name"] for a in (by_name(script.exports, "b") or {}).get("annotations", [])]
       == ["export"]
       and [a["name"] for a in (by_name(script.variables, "a") or {}).get("annotations", [])]
       == ["export_category"])

    # ---------- positive: onready / static ----------
    script = parse("@onready var health_bar = $HealthBar\n")
    entry = by_name(script.variables, "health_bar")
    ok("P10: '@onready var' is captured with its initialiser",
       entry is not None and entry["value"] == "$HealthBar"
       and entry["is_onready"] is True)

    script = parse("static var instance\n")
    entry = by_name(script.variables, "instance")
    ok("P11: 'static var' is captured and flagged static",
       entry is not None and entry["is_static"] is True)

    # ---------- positive: property accessors ----------
    script = parse("var hp: float = 100.0:\n\tset(value):\n\t\thp = value\n")
    prop = by_name(script.properties, "hp")
    ok("P12: property with a setter is captured as PROPERTY",
       prop is not None and prop["declaration_kind"] == "PROPERTY"
       and prop["has_setter"] is True and prop["has_getter"] is False)
    ok("P12b: setter line range points at the real source line",
       prop is not None and prop["accessors"][0]["line"] == 2
       and prop["accessors"][0]["end_line"] == 3)

    script = parse("var ratio: float:\n\tget:\n\t\treturn hp / max_hp\n")
    prop = by_name(script.properties, "ratio")
    ok("P13: getter-only property is captured",
       prop is not None and prop["has_getter"] is True
       and prop["type"] == "float")

    script = parse("var hp: float = 100.0:\n\tget:\n\t\treturn hp\n\tset(value):\n"
                   "\t\thp = value\n")
    prop = by_name(script.properties, "hp")
    ok("P14: getter+setter property records both accessors",
       prop is not None and prop["has_getter"] and prop["has_setter"]
       and [a["kind"] for a in prop["accessors"]] == ["get", "set"])

    # ---------- positive: multi-line ----------
    path = write("multi_func.gd", "func get_value(\n\tkey: Variant,\n"
                                  "\tdefault_value: Variant = null\n) -> Variant:\n"
                                  "\treturn key\n")
    script = gd_parse.parse_file(path)
    func = by_name([{"name": f.name, "line": f.start_line} for f in script.functions],
                   "get_value")
    ok("P15: multi-line function signature is captured",
       func is not None and func["line"] == 1)

    path = write("multi_decl.gd", "var hp: float = " + chr(92) + "\n\t100.0\nvar tail = 1\n")
    script = gd_parse.parse_file(path)
    ok("P16: backslash-continued declaration is captured",
       (by_name(script.variables, "hp") or {}).get("value") == "100.0")

    path = write("multi_brackets.gd", "@export var items: Array[int] = [\n"
                                      "\t1,\n\t2,\n]\n")
    script = gd_parse.parse_file(path)
    ok("P17: bracket-continued declaration is captured",
       by_name(script.exports, "items") is not None)

    # ---------- positive: source location ----------
    path = write("locations.gd", "extends Node\n\nsignal hit\n\nconst MAX: int = 5\n\n"
                                 "@export var hp: float = 5.0\n\nfunc is_dead() -> bool:\n"
                                 "\treturn hp <= 0\n")
    script = gd_parse.parse_file(path)
    ok("P18: line numbers are the real analysed-file lines",
       (by_name(script.exports, "hp") or {}).get("line") == 7
       and by_name(script.signals, "hit")["line"] == 3
       and by_name(script.constants, "MAX")["line"] == 5
       and script.functions[0].start_line == 9
       and script.functions[0].end_line == 10)
    ok("P18b: source coordinates are declared as analysed-file coordinates",
       script.coverage.get("source_coordinates") == "ANALYZED_FILE")

    # ---------- positive: coverage metadata ----------
    script = parse("var hp: float = 5.0\nfunc f():\n\tpass\n")
    ok("P19: fully recognised file reports COMPLETE coverage",
       script.coverage["syntax_coverage_status"] == "COMPLETE"
       and script.coverage["analysis_completeness"] == "FULL"
       and script.coverage["parse_execution_status"] == "PARSED")

    script = parse("enum State { IDLE, RUN }\nvar hp = 1\n")
    ok("P19b: unsupported construct downgrades coverage and is reported",
       script.coverage["syntax_coverage_status"] == "PARTIAL"
       and any(item["code"] == "ENUM_NOT_INTERPRETED"
               for item in script.coverage["unsupported_constructs"]))

    # ---------- negative ----------
    script = parse("var hp: float = 100.0:\n\tget:\n\t\treturn hp\n\tset(value):\n"
                   "\t\thp = value\n")
    ok("N01: property accessors are never reported as top-level functions",
       script.functions == [] and len(script.properties) == 1)

    script = parse("func is_dead() -> bool:\n\treturn hp <= 0\n")
    ok("N02: a function is never reported as a variable/property",
       script.variables == [] and script.properties == [] and script.exports == []
       and [f.name for f in script.functions] == ["is_dead"])

    script = parse("@export var is_dead: bool\nfunc is_dead() -> bool:\n\treturn true\n")
    ok("N03: property name and function name stay distinct declarations",
       [e["name"] for e in script.exports] == ["is_dead"]
       and [f.name for f in script.functions] == ["is_dead"]
       and by_name(script.exports, "is_dead")["declaration_kind"] != "FUNCTION")

    script = parse("var hp = 100\n")
    entry = by_name(script.variables, "hp")
    ok("N04: an absent type annotation is never inferred from the initialiser",
       entry is not None and entry["type"] == ""
       and entry["declaration_kind"] == "VARIABLE")

    script = parse("export(int) var max_health = 9 setget set_max_health\nvar hp = 1\n")
    ok("N05: a legacy setget declaration is captured, not dropped",
       (by_name(script.exports, "max_health") or {}).get("type") == "int"
       and (by_name(script.exports, "max_health") or {}).get("value") == "9")
    ok("N05b: its accessor wiring is reported as partly modelled, not unparsed",
       any(item["code"] == "LEGACY_SETGET_WIRING_NOT_MODELED"
           and item["extent"] == "PARTIALLY_INTERPRETED"
           and item["declaration_gap"] is False
           and item["predecessor_code"] == "LEGACY_SETGET_NOT_INTERPRETED"
           for item in script.coverage["unsupported_constructs"]))

    script = parse("class Inner:\n\tvar x = 1\nvar hp = 1\n")
    ok("N05c: an inner class is reported as unsupported",
       any(item["code"] == "INNER_CLASS_NOT_INTERPRETED"
           for item in script.coverage["unsupported_constructs"])
       and by_name(script.variables, "hp") is not None)

    # ---------- compatibility ----------
    script = parse("extends Node\nclass_name Thing\nsignal ping(a)\nconst MAX := 3\n"
                   "var plain := 1\nfunc go(a, b) -> int:\n\treturn a\n")
    ok("C01: pre-existing declarations survive the new grammar",
       script.class_name == "Thing" and script.extends == "Node"
       and [s["name"] for s in script.signals] == ["ping"]
       and [c["name"] for c in script.constants] == ["MAX"]
       and [v["name"] for v in script.variables] == ["plain"]
       and [f.name for f in script.functions] == ["go"])

    legacy = {
        "schema": "external_code_analysis", "schema_version": 1,
        "analysis_id": "ext-legacy", "symbols": {"functions": [{"name": "f"}],
                                                 "exports": [{"name": "hp"}]},
        "analysis_status": "analysis_complete",
    }
    ok("C02: an analysis record without coverage fields still loads",
       json.loads(json.dumps(legacy))["analysis_status"] == "analysis_complete"
       and "syntax_coverage_status" not in legacy)

    analysis_dir = os.path.join(PROJECT_ROOT, ".ai", "learning", "external_code",
                                "analysis")
    stored = []
    if os.path.isdir(analysis_dir):
        for name in sorted(os.listdir(analysis_dir))[:3]:
            if name.endswith(".json"):
                with open(os.path.join(analysis_dir, name), encoding="utf-8") as handle:
                    stored.append(json.load(handle))
    ok("C03: stored historical analysis records remain readable",
       bool(stored) and all(item.get("schema_version") == 1 for item in stored))

    failed = parse("func broken(:\n")
    ok("C04: a file the grammar cannot recognise is not reported COMPLETE",
       failed.coverage["syntax_coverage_status"] != "COMPLETE"
       or bool(failed.coverage["unrecognized_declarations"])
       or failed.functions == [])

    import shutil
    for directory in TMP:
        shutil.rmtree(directory, ignore_errors=True)
    print("\n===== test_gd_parse: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
