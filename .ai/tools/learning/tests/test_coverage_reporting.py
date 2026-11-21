#!/usr/bin/env python3
"""Phase 1.76 Batch E: coverage reporting hardening tests.

The 1.75 parser reported three different ways of being wrong:

* it dropped declarations its grammar did not match (silent under-reporting);
* it reported an already captured Godot 3 `setget` declaration as unparsed
  (false over-reporting);
* it published one line number in three different coordinate spaces.

These checks are written against the grammar, not against the three sample
variables Batch D happened to find, and they keep both directions honest: a
supported declaration must never enter `unsupported_constructs`, and an
unparsed declaration must never disappear.

Fixtures are in-memory or temporary. Real-file checks only read pinned sources.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil

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


def parse(text: str) -> gd_parse.Script:
    return gd_parse.parse_text("fixture.gd", text)


def by_name(items: list[dict], name: str) -> dict | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def constructs(script: gd_parse.Script, code: str | None = None) -> list[dict]:
    items = script.coverage["unsupported_constructs"]
    return [item for item in items if code is None or item["code"] == code]


def not_interpreted(script: gd_parse.Script) -> list[dict]:
    return [item for item in constructs(script)
            if item["extent"] == gd_parse.EXTENT_NOT_INTERPRETED]


def grammar_checks() -> None:
    # ---------- capture, not silence ----------
    script = parse('export(String) var target = ""\n')
    entry = by_name(script.exports, "target")
    ok("E01: 'export(Type) var' is captured instead of dropped",
       entry is not None and entry["type"] == "String")
    ok("E02: its declaration syntax is named", 
       entry is not None and entry.get("export_syntax") == "LEGACY_PARENTHESISED")
    ok("E03: a fully captured file is not downgraded to PARTIAL",
       script.coverage["syntax_coverage_status"] == "COMPLETE"
       and script.coverage["unsupported_constructs"] == []
       and script.coverage["unrecognized_declarations"] == [])

    script = parse("export var other = 1\n")
    entry = by_name(script.exports, "other")
    ok("E04: bare 'export var' is captured and labelled LEGACY_BARE",
       entry is not None and entry.get("export_syntax") == "LEGACY_BARE")

    script = parse("onready var sprite := $Sprite\n")
    entry = by_name(script.variables, "sprite")
    ok("E05: bare 'onready var' is captured with its initialiser",
       entry is not None and entry["is_onready"] is True
       and entry["value"] == "$Sprite"
       and entry["initializer_kind"] == "INFERRED")

    # ---------- partial support is reported as partial, never as absent ----------
    script = parse("export(int, 0, 10) var hp = 5\n")
    entry = by_name(script.exports, "hp")
    hint = constructs(script, "LEGACY_EXPORT_HINT_ARGS_NOT_INTERPRETED")
    ok("E06: extra legacy export hint args keep the declaration and its type",
       entry is not None and entry["type"] == "int" and entry["value"] == "5"
       and len(hint) == 1
       and hint[0]["extent"] == gd_parse.EXTENT_PARTIALLY_INTERPRETED
       and hint[0]["declaration_gap"] is False)
    ok("E07: a partially interpreted construct does not claim a declaration gap",
       script.coverage["analysis_completeness"] == "FULL"
       and script.coverage["syntax_coverage_status"] == "PARTIAL")

    script = parse("remote func ping() -> void:\n\tpass\n")
    rpc = constructs(script, "LEGACY_RPC_MODIFIER_NOT_INTERPRETED")
    ok("E08: a Godot 3 RPC modifier keeps its function and reports the gap",
       [f.name for f in script.functions] == ["ping"]
       and len(rpc) == 1
       and rpc[0]["extent"] == gd_parse.EXTENT_PARTIALLY_INTERPRETED
       and "remote" in rpc[0]["detail"]["modifiers"])

    script = parse("export(int) var hp = 1 setget set_hp, get_hp\n")
    entry = by_name(script.exports, "hp")
    setget = constructs(script, "LEGACY_SETGET_WIRING_NOT_MODELED")
    ok("E09: a captured setget declaration is not reported as unparsed",
       entry is not None and entry["type"] == "int"
       and not_interpreted(script) == [])
    ok("E10: its accessor names are recorded and the gap is named precisely",
       len(setget) == 1
       and setget[0]["detail"]["setter"] == "set_hp"
       and setget[0]["detail"]["getter"] == "get_hp"
       and setget[0]["predecessor_code"] == "LEGACY_SETGET_NOT_INTERPRETED")
    ok("E11: the retired code never appears as the active code",
       all(item["code"] != "LEGACY_SETGET_NOT_INTERPRETED"
           for item in constructs(script)))

    script = parse("var plain = 1 setget\n")
    unknown = constructs(script, "LEGACY_SETGET_SYNTAX_UNRECOGNISED")
    ok("E12: an unreadable setget suffix keeps the declaration and is NOT_INTERPRETED",
       by_name(script.variables, "plain") is not None
       and len(unknown) == 1
       and unknown[0]["extent"] == gd_parse.EXTENT_NOT_INTERPRETED
       and unknown[0]["declaration_gap"] is True)

    script = parse('var note = " setget handler"\n'
                   'func f():\n\tvar inner = "a setget b"\n')
    ok("E13: 'setget' inside a string literal is never reported",
       constructs(script) == [] and script.coverage["unrecognized_declarations"] == []
       and script.coverage["syntax_coverage_status"] == "COMPLETE")

    # ---------- a real miss is still found ----------
    script = parse("wobble var misplaced = 1\n")
    flagged = script.coverage["unrecognized_declarations"]
    ok("E14: a declaration-shaped line the grammar cannot capture is reported",
       len(flagged) == 1 and flagged[0]["declaration_keyword"] == "var"
       and flagged[0]["declaration_gap"] is True)
    ok("E15: and it is reported as a declaration gap, not as full coverage",
       script.coverage["syntax_coverage_status"] == "PARTIAL"
       and script.coverage["analysis_completeness"] == "DECLARATION_GAPS")

    script = parse('var doc = """\nfunc not_code(x):\n\tpass\n"""\nvar hp = 1\n')
    ok("E16: declaration text inside a multi-line string is not a false positive",
       script.coverage["unrecognized_declarations"] == []
       and not_interpreted(script) == []
       and by_name(script.variables, "hp") is not None)

    script = parse("enum Mode {\n\tA,\n\tB,\n}\nvar hp = 1\n")
    enum = constructs(script, "ENUM_NOT_INTERPRETED")
    ok("E17: an enum is NOT_INTERPRETED and blocks FULL completeness",
       len(enum) == 1 and enum[0]["declaration_gap"] is True
       and enum[0]["name"] == "Mode"
       and script.coverage["analysis_completeness"] == "DECLARATION_GAPS")

    script = parse("class Inner:\n\tvar x = 1\nvar hp = 1\n")
    inner = constructs(script, "INNER_CLASS_NOT_INTERPRETED")
    ok("E18: an inner class is NOT_INTERPRETED while the file keeps parsing",
       len(inner) == 1 and inner[0]["declaration_gap"] is True
       and by_name(script.variables, "hp") is not None)

    # ---------- coordinates ----------
    script = parse("var a = 1\nfunc f() setget\n".replace("func f() setget", "class Inner:"))
    items = constructs(script)
    ok("E19: every construct states its coordinate space explicitly",
       bool(items) and all(item["line_space"] == gd_parse.LINE_SPACE_ANALYSIS
                           and item["analysis_line"] == item["line"]
                           for item in items))
    ok("E20: the parser never invents source or record coordinates",
       script.coverage["line_coordinates"]["source_line"] == "NOT_MAPPED_BY_PARSER"
       and script.coverage["line_coordinates"]["record_line"] == "NOT_MAPPED_BY_PARSER")

    sample = {"code": "ENUM_NOT_INTERPRETED", "line": 9, "analysis_line": 9,
              "line_space": gd_parse.LINE_SPACE_ANALYSIS, "extent": "NOT_INTERPRETED",
              "declaration_gap": True}
    projected = gd_parse.project_construct_lines([sample], source_offset=3, record_offset=3)[0]
    ok("E21: projecting a construct derives source/record lines without rewriting 'line'",
       projected["line"] == 9 and projected["analysis_line"] == 9
       and projected["source_line"] == 6 and projected["record_line"] == 9)
    unmapped = gd_parse.project_construct_lines([sample])[0]
    ok("E22: an unknown mapping stays None instead of being guessed",
       unmapped["source_line"] is None and unmapped["record_line"] is None
       and unmapped["line"] == 9)

    # ---------- no contradiction, deterministic ----------
    script = parse("export(int) var hp = 1 setget set_hp, get_hp\n"
                   "enum Mode { A }\n")
    coverage = script.coverage
    ok("E23: PARTIAL is never overwritten by a FULL completeness label",
       coverage["syntax_coverage_status"] == "PARTIAL"
       and coverage["coverage_derivation"]["authoritative_field"]
       == "syntax_coverage_status")
    ok("E24: derivation counts agree with the reported lists",
       coverage["coverage_derivation"]["unsupported_total"]
       == len(coverage["unsupported_constructs"])
       and coverage["coverage_derivation"]["declaration_gaps"]
       == len([item for item in coverage["unsupported_constructs"]
               if item["declaration_gap"]])
       and coverage["coverage_derivation"]["unrecognized_declarations"]
       == len(coverage["unrecognized_declarations"]))

    again = parse("export(int) var hp = 1 setget set_hp, get_hp\n"
                  "enum Mode { A }\n")
    ok("E25: the same text always produces the same coverage report",
       json.dumps(coverage, sort_keys=True) == json.dumps(again.coverage, sort_keys=True))

    mixed = parse("extends Node\nclass_name Thing\nsignal ping(a)\n"
                  "const MAX: int = 5\n@export var hp: float = 5.0\n"
                  "func go(a, b) -> int:\n\treturn a\n")
    ok("E26: supported declarations never leak into the unsupported lists",
       mixed.coverage["unsupported_constructs"] == []
       and mixed.coverage["unrecognized_declarations"] == []
       and mixed.coverage["syntax_coverage_status"] == "COMPLETE")


def real_sample_checks() -> None:
    """Checks against the pinned sources Batch D reviewed (read-only)."""
    library = os.path.join(PROJECT_ROOT, ".ai", "skills", "foundation",
                           "godot-gdscript", "code_library")
    sources = os.path.join(library, "sources")
    references = os.path.join(library, "references")
    member = os.path.join(sources, "alfredbaudisch__Godello", "gd", "scripts",
                          "board_member_button.gd")
    card = os.path.join(sources, "alfredbaudisch__Godello", "gd", "scripts",
                        "board_card.gd")
    compare = os.path.join(sources, "bitbrain__beehave", "gd", "addons", "beehave",
                           "nodes", "leaves", "blackboard_compare.gd")
    member_ref = os.path.join(references, "ui",
                              "alfredbaudisch__Godello__scripts__board_member_button.gd")

    if not (os.path.isfile(member) and os.path.isfile(card) and os.path.isfile(compare)):
        ok("R00: pinned Batch D sources are available", False)
        return
    ok("R00: pinned Batch D sources are available", True)

    script = gd_parse.parse_file(member)
    exported = by_name(script.exports, "expand_to")
    ok("R01: the declaration Batch D found missing is now in the symbol table",
       exported is not None and exported["line"] == 4 and exported["type"] == "String")
    ok("R02: it is not reported as an unsupported construct",
       not_interpreted(script) == []
       and all(item.get("name") != "expand_to" for item in constructs(script)))

    modelled = [item for item in constructs(script)
                if item["code"] == "LEGACY_SETGET_WIRING_NOT_MODELED"]
    ok("R03: both setget properties are reported as partly modelled at commit lines",
       sorted((item["name"], item["line"]) for item in modelled)
       == [("board", 7), ("model", 6)]
       and all(item["extent"] == gd_parse.EXTENT_PARTIALLY_INTERPRETED
               and item["declaration_gap"] is False for item in modelled))
    ok("R04: a file whose only gap is accessor wiring keeps analysis_completeness FULL",
       script.coverage["syntax_coverage_status"] == "PARTIAL"
       and script.coverage["analysis_completeness"] == "FULL"
       and by_name(script.variables, "normal_text") is not None)

    card_script = gd_parse.parse_file(card)
    title = by_name(card_script.variables, "title_label")
    ok("R05: the onready declaration Batch D found missing is captured",
       title is not None and title["line"] == 6 and title["is_onready"] is True
       and title["value"] == "$Title")

    compare_script = gd_parse.parse_file(compare)
    enum = constructs(compare_script, "ENUM_NOT_INTERPRETED")
    ok("R06: the enum Batch D found missing is reported at commit line 7",
       len(enum) == 1 and enum[0]["name"] == "Operators" and enum[0]["line"] == 7
       and enum[0]["declaration_gap"] is True)
    ok("R07: and it is the only reason that file is not COMPLETE",
       compare_script.coverage["analysis_completeness"] == "DECLARATION_GAPS"
       and all(item["code"] == "ENUM_NOT_INTERPRETED" for item in constructs(compare_script)))

    if not os.path.isfile(member_ref):
        ok("R08: the reference copy is available for coordinate cross-checking", False)
        return
    reference_text = open(member_ref, encoding="utf-8", errors="replace").read()
    source_text = open(member, encoding="utf-8", errors="replace").read()
    ref_lines = reference_text.splitlines()
    src_lines = source_text.splitlines()
    offset = next((index for index in range(0, 13)
                   if ref_lines[index:index + len(src_lines)] == src_lines), None)
    ok("R08: the reference copy is a record-line projection of the pinned source",
       offset == 3)

    record_script = gd_parse.parse_text("reference.gd", reference_text)
    projected = gd_parse.project_construct_lines(
        record_script.coverage["unsupported_constructs"],
        source_offset=offset, record_offset=offset) if offset is not None else []
    model = next((item for item in projected if item.get("name") == "model"), None)
    ok("R09: record lines and commit lines are kept in separate spaces",
       model is not None and model["line"] == 9 and model["source_line"] == 6
       and model["record_line"] == 9
       and "model" in src_lines[model["source_line"] - 1]
       and "model" in ref_lines[model["line"] - 1])


def main() -> int:
    print("Batch E: grammar-level coverage reporting")
    grammar_checks()
    print("\nBatch E: pinned real samples")
    real_sample_checks()
    for directory in TMP:
        shutil.rmtree(directory, ignore_errors=True)
    print("\n===== test_coverage_reporting: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
