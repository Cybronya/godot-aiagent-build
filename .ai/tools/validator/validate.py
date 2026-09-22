#!/usr/bin/env python3
"""On-demand validator for the Godot Agent Skill Framework."""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
from typing import Any
try:
    import yaml
except ImportError:
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

class Reporter:
    def __init__(self): self.failures=[]; self.warnings=[]
    def fail(self, message): self.failures.append(message)
    def warn(self, message): self.warnings.append(message)
    def summary(self):
        print("\n" + "=" * 72)
        if self.failures:
            print(f"FAIL: {len(self.failures)} error(s), {len(self.warnings)} warning(s)")
            return 1
        if self.warnings:
            print(f"WARNING: 0 error(s), {len(self.warnings)} warning(s)")
            return 0
        print("PASS: 0 error(s), 0 warning(s)")
        return 0

def load_yaml(path: Path, r: Reporter) -> dict[str, Any]:
    if not path.is_file(): r.fail(f"Missing config file: {path}"); return {}
    try: data=yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc: r.fail(f"Invalid YAML: {path}: {exc}"); return {}
    if not isinstance(data, dict): r.fail(f"Expected YAML mapping at root: {path}"); return {}
    return data

def read_text(path: Path, r: Reporter) -> str:
    if not path.is_file(): r.fail(f"Missing file: {path}"); return ""
    try: return path.read_text(encoding="utf-8")
    except Exception as exc: r.fail(f"Cannot read {path}: {exc}"); return ""

def section(text: str, heading: str) -> str:
    m=re.search(rf"^(#{{1,6}})\s+{re.escape(heading)}\s*$", text, re.M)
    if not m: return ""
    level=len(m.group(1))
    end=re.search(rf"^#{{1,{level}}}\s+", text[m.end():], re.M)
    return text[m.end():m.end()+end.start()] if end else text[m.end():]

def heading_exists(text: str, heading: str) -> bool:
    return re.search(rf"^#{{1,6}}\s+{re.escape(heading)}\s*$", text, re.M) is not None

def heading_value(text: str, heading: str):
    # Canonical template fields are level-2 headings followed by one value line.
    # Match the heading literally and read the first non-empty line after it.
    pattern = r"^##[ \\t]+" + re.escape(heading) + r"[ \\t]*$"
    match=re.search(pattern, text, re.M)
    if not match:
        return None
    rest=text[match.end():]
    next_heading=re.search(r"^##[ \\t]+", rest, re.M)
    block=rest[:next_heading.start()] if next_heading else rest
    lines=[line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[0].strip("`").strip()
def bullets(text: str, heading: str):
    block=section(text, heading)
    return [m.group(1).strip().strip(chr(96)) for m in re.finditer(r"^\s*-\s+(.+?)\s*$", block, re.M) if m.group(1).strip().lower() not in {"none","[]"}]

def parse_skill(skill_dir: Path, r: Reporter):
    path=skill_dir/"SKILL.md"; text=read_text(path,r)
    # Identity fields are level-2 sibling headings under the level-1 Skill Identity block.
    # Parse them from the full document because section() intentionally stops at
    # the next heading of the same or higher level.
    skill_id=heading_value(text,"Skill ID"); name=heading_value(text,"Skill Name"); version=heading_value(text,"Version"); category=heading_value(text,"Category")
    for value,label in [(skill_id,"Skill ID"),(name,"Skill Name"),(version,"Version"),(category,"Category")]:
        if not value: r.fail(f"{path}: missing {label}")
    if skill_id and skill_id != skill_dir.name: r.fail(f"{path}: Skill ID {skill_id!r} does not match directory {skill_dir.name!r}")
    meta=section(text,"Registry Metadata")
    load_block=section(meta,"Load Policy")
    load_policy=next((x.strip().strip(chr(96)) for x in load_block.splitlines() if x.strip().strip(chr(96)) in {"required","conditional","optional"}),None)
    if not load_policy: r.fail(f"{path}: invalid or missing Load Policy")
    required=bullets(meta,"Required"); related=bullets(meta,"Related")
    for h in ["Description","Purpose","Responsibility","Trigger Conditions","Input Contract","Workflow","Output Contract","Validation","Failure Handling"]:
        if not heading_exists(text,h): r.fail(f"{path}: missing required section {h!r}")
    return {"dir":skill_dir,"file":path,"text":text,"id":skill_id,"name":name,"version":version,"category":category,"load_policy":load_policy,"required":required,"related":related}

def main():
    p=argparse.ArgumentParser(description="Validate the Godot Agent Skill Framework.")
    p.add_argument("--config-dir",type=Path,default=Path(__file__).resolve().parents[2]/"config")
    args=p.parse_args(); config_dir=args.config_dir.resolve(); r=Reporter()
    print("Godot Agent Skill Framework Validator"); print(f"Config: {config_dir}")
    files={k:config_dir/n for k,n in {
      "agent":"agent.yaml","rules":"framework-rules.yaml","schema":"skill-schema.yaml","types":"skill-types.yaml",
      "registry":"skill-registry.yaml","loading":"skill-loading.yaml","dependency":"skill-dependency.yaml","collaboration":"skill-collaboration.yaml"}.items()}
    template_path=config_dir/"SKILL_TEMPLATE.md"; cfg={k:load_yaml(v,r) for k,v in files.items()}; template=read_text(template_path,r)

    # Legacy Registry migration check.
    # .ai/registry/ is retained only as a migration source and must never become
    # an active discovery source. Its entries are compared against the canonical
    # .ai/config/skill-registry.yaml and the canonical Skill files.
    legacy_dir=config_dir.parent/"registry"
    legacy_registry=legacy_dir/"skill_registry.yaml"
    legacy_rules=legacy_dir/"registry_rules.md"
    # Load the canonical Registry before comparing legacy entries against it.
    reg=cfg["registry"].get("registry",{})
    entries=cfg["registry"].get("skills",[])
    if not isinstance(entries,list):
        r.fail("skill-registry.yaml: registry.skills must be a list")
        entries=[]
    legacy_entries=[]
    if legacy_registry.is_file():
        legacy_cfg=load_yaml(legacy_registry,r)
        legacy_root=legacy_cfg.get("registry",{})
        legacy_entries=legacy_root.get("skills",[]) if isinstance(legacy_root,dict) else []
        if not isinstance(legacy_entries,list):
            r.fail("Legacy Registry .ai/registry/skill_registry.yaml: registry.skills must be a list")
            legacy_entries=[]
        r.warn("Legacy Registry detected at .ai/registry/; it is migration-only and must not be used for Skill discovery.")
        for entry in legacy_entries:
            if not isinstance(entry,dict):
                r.fail("Legacy Registry: every entry must be a mapping")
                continue
            sid=entry.get("id")
            legacy_path=entry.get("path")
            if not sid or not legacy_path:
                r.fail("Legacy Registry: every entry requires id and path")
                continue
            if sid not in {e.get("id") for e in entries if isinstance(e,dict)}:
                r.fail(f"Legacy Registry entry {sid!r} is missing from canonical skill-registry.yaml")
            # Resolve old paths against the repository root, then compare with
            # the canonical registry's resolved Skill directory.
            old_rel=Path(str(legacy_path).replace("\\\\","/"))
            if old_rel.parts[:1] == (".ai",):
                old_target=(config_dir.parent.parent/old_rel).resolve()
            else:
                old_target=(config_dir/old_rel).resolve()
            canonical_entry=next((e for e in entries if isinstance(e,dict) and e.get("id")==sid),None)
            if canonical_entry:
                canonical_target=(config_dir/Path(str(canonical_entry.get("path")))).resolve()
                if old_target != canonical_target:
                    r.fail(
                        f"Legacy Registry path conflict for {sid!r}: "
                        f"legacy={legacy_path!r}, canonical={canonical_entry.get('path')!r}"
                    )
            if old_target.name != "SKILL.md" and (old_target/"SKILL.md").is_file():
                old_target=old_target/"SKILL.md"
            if not old_target.exists():
                r.fail(f"Legacy Registry stale path for {sid!r}: {legacy_path!r}")
        if legacy_rules.is_file():
            r.warn("Legacy Registry rules detected at .ai/registry/registry_rules.md; framework-rules.yaml and skill-schema.yaml are the active contracts.")
    elif legacy_rules.is_file():
        r.warn("Legacy Registry rules detected at .ai/registry/registry_rules.md without skill_registry.yaml.")

    agent_fw=cfg["agent"].get("framework",{}); rules_fw=cfg["rules"].get("framework",{})
    if agent_fw.get("version") != rules_fw.get("version"): r.fail(f"Framework version mismatch: agent.yaml={agent_fw.get('version')!r}, framework-rules.yaml={rules_fw.get('version')!r}")

    for key,value in agent_fw.items():
        if key in {"id","version"}: continue
        if not isinstance(value,str) or Path(value).is_absolute() or value.startswith((".ai/",".agent/")): r.fail(f"agent.yaml framework.{key} must be a root-independent relative path: {value!r}")
        elif not (config_dir/Path(value)).resolve().exists(): r.fail(f"agent.yaml framework.{key} points to missing path: {value}")

    registry_ids=set(); records={}
    forbidden=set(cfg["schema"].get("registry_contract",{}).get("forbidden_canonical_fields",[]))
    for entry in entries:
        if not isinstance(entry,dict): r.fail("skill-registry.yaml: every entry must be a mapping"); continue
        extra_fields=set(entry)-{"id","path"}
        if extra_fields: r.fail(f"skill-registry.yaml: forbidden/non-index fields: {sorted(extra_fields)}")
        sid=entry.get("id"); rel=entry.get("path")
        if not sid or not rel: r.fail("skill-registry.yaml: every entry requires id and path"); continue
        if sid in registry_ids: r.fail(f"skill-registry.yaml: duplicate Skill id {sid!r}")
        registry_ids.add(sid)
        relpath=Path(rel)
        if relpath.is_absolute() or ".ai" in relpath.parts or ".agent" in relpath.parts: r.fail(f"skill-registry.yaml: non-root-independent path for {sid!r}: {rel}"); continue
        records[sid]=parse_skill((config_dir/relpath).resolve(),r)
        if records[sid].get("id") and records[sid]["id"] != sid: r.fail(f"Registry/Skill id mismatch: registry={sid!r}, canonical={records[sid]['id']!r}")

    # Load the Skill taxonomy before scanning the physical Skill tree because
    # category validation is part of the physical-tree contract.
    types=cfg["types"].get("types",{}); valid=set(types)

    # Bidirectional Skill/Registry integrity: every physical Skill directory must
    # be registered, and every registry entry must resolve to a physical Skill.
    skills_root=config_dir.parent/"skills"
    physical_skills={}
    if skills_root.is_dir():
        # A Skill is exactly one directory below a declared category directory:
        # .ai/skills/{category}/{skill-id}/SKILL.md
        # Do not recursively treat Skill-local references/examples/templates as
        # Skills; those are explicitly supported by the Skill Schema.
        for category_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
            if category_dir.name not in valid:
                # Unknown top-level directories are not valid Skill categories.
                r.fail(f"Unknown Skill category directory: {category_dir}")
                continue
            for skill_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
                skill_file=skill_dir/"SKILL.md"
                if skill_file.is_file():
                    physical_skills[skill_dir.name]=skill_dir.resolve()
                else:
                    # Only immediate children of a category are Skill candidates.
                    # Nested support directories inside a Skill are ignored here.
                    if any(child.is_file() for child in skill_dir.iterdir()):
                        r.fail(f"Unrecognized Skill directory without SKILL.md: {skill_dir}")
    else:
        r.fail(f"Missing Skills root: {skills_root}")
    for sid, physical_dir in physical_skills.items():
        if sid not in registry_ids:
            r.fail(f"Unregistered physical Skill directory: {physical_dir}")
        elif records.get(sid, {}).get("dir") != physical_dir:
            r.fail(f"Registry path mismatch for physical Skill {sid!r}: registry resolves to {records.get(sid, {}).get('dir')}, physical={physical_dir}")
    for sid, rec in records.items():
        if sid not in physical_skills:
            r.fail(f"Registered Skill is missing from physical Skills tree: {sid!r}")

    # Validate the machine-readable Skill Loading contract against the canonical taxonomy
    # and every loaded Skill's canonical load policy.
    loading=cfg["loading"]
    if not isinstance(loading,dict):
        r.fail("skill-loading.yaml: loading must be a mapping")
        loading={}
    if loading.get("version") != 2:
        r.fail(f"skill-loading.yaml: expected loading.version=2, got {loading.get('version')!r}")
    canonical_source=loading.get("canonical_source",{})
    if not isinstance(canonical_source,dict) or not canonical_source.get("rule"):
        r.fail("skill-loading.yaml: canonical_source.rule is required")
    policies=loading.get("policies",{})
    expected_policies={"required","conditional","optional"}
    if not isinstance(policies,dict):
        r.fail("skill-loading.yaml: policies must be a mapping")
        policies={}
    elif set(policies) != expected_policies:
        r.fail(f"skill-loading.yaml: policies must define exactly {sorted(expected_policies)}, got {sorted(policies)}")
    policy_contracts={
        "required": {"load_before_task_analysis": True, "may_be_unloaded": False},
        "conditional": {"load_before_task_execution": True, "load_only_when_relevant": True},
        "optional": {"load_on_demand": True},
    }
    for policy,expected in policy_contracts.items():
        block=policies.get(policy,{})
        behavior=block.get("behavior",{}) if isinstance(block,dict) else {}
        if not isinstance(behavior,dict):
            r.fail(f"skill-loading.yaml: policies.{policy}.behavior must be a mapping")
            continue
        for key,value in expected.items():
            if behavior.get(key) is not value:
                r.fail(f"skill-loading.yaml: policies.{policy}.behavior.{key} must be {value!r}")
    selection_order=loading.get("selection_order",[])
    allowed_selection={"task_intent","required_skills","architecture_skills","foundation_skills","system_skills","engineering_skills","dependency_closure"}
    if not isinstance(selection_order,list) or not selection_order:
        r.fail("skill-loading.yaml: selection_order must be a non-empty list")
    else:
        unknown=set(selection_order)-allowed_selection
        if unknown: r.fail(f"skill-loading.yaml: selection_order contains unknown stages: {sorted(unknown)}")
        if len(selection_order) != len(set(selection_order)): r.fail("skill-loading.yaml: selection_order contains duplicate stages")
        if selection_order[-1] != "dependency_closure": r.fail("skill-loading.yaml: dependency_closure must be the final selection stage")
        if "task_intent" not in selection_order or "required_skills" not in selection_order:
            r.fail("skill-loading.yaml: selection_order must include task_intent and required_skills")
        for category,stage in {"architecture":"architecture_skills","foundation":"foundation_skills","systems":"system_skills","engineering":"engineering_skills"}.items():
            if stage not in selection_order: r.fail(f"skill-loading.yaml: selection_order missing {stage!r} for category {category!r}")
        category_positions={stage:selection_order.index(stage) for stage in selection_order if stage.endswith("_skills")}
        expected_category_order=["architecture_skills","foundation_skills","system_skills","engineering_skills"]
        if any(category_positions[a] >= category_positions[b] for a,b in zip(expected_category_order,expected_category_order[1:])):
            r.fail("skill-loading.yaml: category selection stages must follow architecture -> foundation -> systems -> engineering")
    loading_rules=loading.get("rules",[])
    if not isinstance(loading_rules,list) or not all(isinstance(x,str) and x.strip() for x in loading_rules):
        r.fail("skill-loading.yaml: rules must be a non-empty list of strings")
    for sid,rec in records.items():
        policy=rec.get("load_policy")
        if policy not in expected_policies:
            continue
        if policy not in policies: r.fail(f"{sid}: load policy {policy!r} is not defined by skill-loading.yaml")

    # Validate the machine-readable Skill Collaboration contract against the
    # canonical taxonomy and the workflow categories used by the framework.
    collaboration=cfg["collaboration"]
    if not isinstance(collaboration,dict):
        r.fail("skill-collaboration.yaml: collaboration must be a mapping")
        collaboration={}
    if collaboration.get("version") != 1:
        r.fail(f"skill-collaboration.yaml: expected collaboration.version=1, got {collaboration.get('version')!r}")
    principle=collaboration.get("principle",{})
    if not isinstance(principle,dict) or not principle.get("description"):
        r.fail("skill-collaboration.yaml: principle.description is required")
    ownership=collaboration.get("ownership",{})
    if not isinstance(ownership,dict):
        r.fail("skill-collaboration.yaml: ownership must be a mapping")
        ownership={}
    if set(ownership) != valid:
        r.fail(f"skill-collaboration.yaml: ownership must define exactly the Skill categories {sorted(valid)}, got {sorted(ownership)}")
    for category in valid:
        block=ownership.get(category,{})
        decides=block.get("decides",[]) if isinstance(block,dict) else []
        if not isinstance(decides,list) or not decides or not all(isinstance(x,str) and x.strip() for x in decides):
            r.fail(f"skill-collaboration.yaml: ownership.{category}.decides must be a non-empty list of strings")
    workflow=collaboration.get("workflow",{})
    if not isinstance(workflow,dict):
        r.fail("skill-collaboration.yaml: workflow must be a mapping")
        workflow={}
    workflow_contracts={
        "architecture_first": ["architecture","foundation","systems","engineering"],
        "local_implementation": ["relevant_foundation","relevant_system","relevant_engineering"],
    }
    for name,expected_sequence in workflow_contracts.items():
        block=workflow.get(name,{})
        when=block.get("when",[]) if isinstance(block,dict) else []
        sequence=block.get("sequence",[]) if isinstance(block,dict) else []
        if not isinstance(when,list) or not when or not all(isinstance(x,str) and x.strip() for x in when):
            r.fail(f"skill-collaboration.yaml: workflow.{name}.when must be a non-empty list of strings")
        if sequence != expected_sequence:
            r.fail(f"skill-collaboration.yaml: workflow.{name}.sequence must be {expected_sequence!r}")
    handoff_rules=collaboration.get("handoff_rules",[])
    if not isinstance(handoff_rules,list) or not handoff_rules or not all(isinstance(x,str) and x.strip() for x in handoff_rules):
        r.fail("skill-collaboration.yaml: handoff_rules must be a non-empty list of strings")
    output=collaboration.get("output",{})
    report_fields=output.get("each_skill_should_report",[]) if isinstance(output,dict) else []
    expected_report_fields={"decisions_made","artifacts_changed","dependencies_used","unresolved_issues","handoff_information"}
    if not isinstance(report_fields,list) or set(report_fields) != expected_report_fields:
        actual=sorted(report_fields) if isinstance(report_fields,list) else report_fields
        r.fail(f"skill-collaboration.yaml: output.each_skill_should_report must define exactly {sorted(expected_report_fields)}, got {actual!r}")

    dependency_direction=cfg["dependency"].get("category_direction",{})
    if not dependency_direction:
        r.fail("skill-dependency.yaml: missing category_direction")
    elif set(dependency_direction) != valid:
        r.fail("skill-dependency.yaml: category_direction must define exactly the categories from skill-types.yaml")
    for sid,rec in records.items():
        cat=rec.get("category")
        if cat and cat not in valid: r.fail(f"{sid}: unknown category {cat!r}")
        for dep in rec.get("required",[]):
            if dep not in registry_ids: r.fail(f"{sid}: required dependency {dep!r} is not registered")
        for rel in rec.get("related",[]):
            if rel not in registry_ids: r.warn(f"{sid}: related Skill {rel!r} is not registered")
        if cat in valid:
            allowed=set(dependency_direction.get(cat,{}).get("may_depend_on",[]))
            for dep in rec.get("required",[]):
                if dep in records and records[dep].get("category") not in allowed: r.fail(f"{sid}: dependency {dep!r} category {records[dep].get('category')!r} violates {cat}.may_depend_on={sorted(allowed)}")

    graph={sid:[d for d in rec.get("required",[]) if d in registry_ids] for sid,rec in records.items()}; visiting=set(); visited=set()
    def visit(node,stack):
        if node in visiting: r.fail("Circular required dependency: "+" -> ".join(stack+[node])); return
        if node in visited: return
        visiting.add(node)
        for dep in graph.get(node,[]): visit(dep,stack+[node])
        visiting.remove(node); visited.add(node)
    for node in graph: visit(node,[])

    for field,label in [("id","Skill ID"),("name","Skill Name"),("version","Version"),("category","Category"),("description","Description"),("purpose","Purpose"),("responsibility","Responsibility"),("load_policy","Load Policy")]:
        if field in set(cfg["schema"].get("required",[])) and label not in template: r.fail(f"SKILL_TEMPLATE.md: missing schema-required field {label!r}")

    # Collaboration is optional and may explain relationships in prose.
    # Only an exact duplicate of canonical dependency/related IDs is invalid;
    # explanatory collaboration notes are allowed by the template contract.
    for sid,rec in records.items():
        collab=section(rec.get("text",""),"Collaboration")
        if not collab:
            continue
        canonical_required=set(rec.get("required",[]))
        canonical_related=set(rec.get("related",[]))
        dep_block=section(collab,"Dependencies")
        related_block=section(collab,"Related Skills")
        dep_ids=set(re.findall(r"\b[a-z][a-z0-9-]*\b", dep_block))
        related_ids=set(re.findall(r"\b[a-z][a-z0-9-]*\b", related_block))
        if canonical_required and canonical_required.issubset(dep_ids):
            r.fail(f"{sid}: Collaboration duplicates canonical Required dependencies; keep them in Registry Metadata")
        exact_related_bullets={b.strip() for b in re.findall(r"^\s*-\s+(.+?)\s*$", related_block, re.M)}
        if canonical_related & exact_related_bullets:
            r.fail(f"{sid}: Collaboration duplicates canonical Related Skills; keep them in Registry Metadata")

    for path in files.values():
        if not path.is_file(): continue
        for no,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
            if re.search(r"(?<![A-Za-z0-9_-])(?:\.ai|\.agent)(?:/|\\)",line): r.fail(f"{path}:{no}: framework-internal path hardcodes .ai/.agent")

    print("\nChecks"); print(f"  Registry entries: {len(entries)}"); print(f"  Canonical Skills loaded: {len(records)}"); print(f"  Categories defined: {len(valid)}"); print(f"  Required dependency edges: {sum(len(x.get('required',[])) for x in records.values())}"); print(f"  Legacy Registry entries checked: {len(legacy_entries)}")
    if r.failures: print("\nFAILURES"); [print(f"  - {x}") for x in r.failures]
    if r.warnings: print("\nWARNINGS"); [print(f"  - {x}") for x in r.warnings]
    return r.summary()

if __name__=="__main__": raise SystemExit(main())