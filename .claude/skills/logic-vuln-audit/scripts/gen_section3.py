#!/usr/bin/env python3
"""
Section 3 Generator Script

Reads merged_vulnerabilities.json and per-module vulnerability_analysis.json
to produce a complete Section 3 (Vulnerability Details) markdown file.

This script handles all JSON schema variants produced by different business agents:
- Standard schema (login, profile_update): sink/source as nested dicts
- Register variant: affected_files as list of dicts, code_snippet at top level
- Password_reset variant: affected_code as dict, code_snippet at top level

Usage:
    python3 gen_section3.py <output_dir> [--lang zh|en|ja]

Example:
    python3 gen_section3.py /path/to/project/logic_vuln_audit/
"""

import json
import os
import sys

SEVERITY_ICONS = {
    "Critical": "🔴 Critical",
    "High": "🟠 High",
    "Medium": "🟡 Medium",
    "Low": "🟢 Low",
}

MODULES = ["login", "register", "password_reset", "profile_update", "payment"]


def load_json(path):
    """Load a JSON file, return None on failure."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {path}: {e}")
        return None


def build_original_vuln_index(output_dir):
    """Build an index of original vulnerabilities keyed by (module, original_id)."""
    index = {}
    for module in MODULES:
        vuln_file = os.path.join(output_dir, module, "vulnerability_analysis.json")
        data = load_json(vuln_file)
        if not data:
            continue
        for v in data.get("vulnerabilities", []):
            # Try various ID field names
            vid = v.get("vulnerability_id") or v.get("id") or v.get("vuln_id") or ""
            index[(module, vid)] = v
    return index


def safe_str(val, default=""):
    """Safely convert a value to string."""
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return str(val)
    return str(val)


def safe_float(val, default=0.0):
    """Safely convert to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def extract_sink_info(vuln, original):
    """Extract SINK information from various schema formats.

    Returns dict with: file_path, line_number, function_name, code_snippet
    """
    # Try standard sink dict first (from merged or original)
    sink = vuln.get("sink", {})
    if isinstance(sink, str):
        sink = {}

    if sink and sink.get("file_path"):
        return {
            "file_path": sink.get("file_path", ""),
            "line_number": sink.get("line_number", ""),
            "function_name": sink.get("function_name", ""),
            "code_snippet": sink.get("code_snippet", ""),
        }

    # Try original vuln's sink
    if original:
        o_sink = original.get("sink", {})
        if isinstance(o_sink, str):
            o_sink = {}
        if o_sink and o_sink.get("file_path"):
            return {
                "file_path": o_sink.get("file_path", ""),
                "line_number": o_sink.get("line_number", ""),
                "function_name": o_sink.get("function_name", ""),
                "code_snippet": o_sink.get("code_snippet", ""),
            }

    # Try affected_code (password_reset format)
    affected_code = vuln.get("affected_code") or (original.get("affected_code") if original else None)
    if isinstance(affected_code, dict) and affected_code.get("file"):
        return {
            "file_path": affected_code.get("file", ""),
            "line_number": affected_code.get("lines", ""),
            "function_name": affected_code.get("function", ""),
            "code_snippet": affected_code.get("snippet", ""),
        }

    # Try affected_files (register format) - use first entry
    affected_files = vuln.get("affected_files") or (original.get("affected_files") if original else None)
    if isinstance(affected_files, list) and affected_files:
        first = affected_files[0]
        if isinstance(first, dict):
            # Get code_snippet from top-level
            code = vuln.get("code_snippet") or (original.get("code_snippet") if original else "") or ""
            return {
                "file_path": first.get("file_path", ""),
                "line_number": first.get("line_range", first.get("line_number", "")),
                "function_name": first.get("function_name", ""),
                "code_snippet": code,
            }

    # Last resort: check top-level code_snippet
    code = vuln.get("code_snippet") or (original.get("code_snippet") if original else "") or ""
    return {
        "file_path": "",
        "line_number": "",
        "function_name": "",
        "code_snippet": code,
    }


def extract_source_info(vuln, original):
    """Extract SOURCE information from various schema formats.

    Returns dict with: file_path, line_number, code_snippet, endpoint
    """
    # Try standard source dict
    source = vuln.get("source", {})
    if isinstance(source, str):
        source = {}

    if source and source.get("file_path"):
        return {
            "file_path": source.get("file_path", ""),
            "line_number": source.get("line_number", ""),
            "code_snippet": source.get("code_snippet", ""),
            "endpoint": source.get("endpoint", ""),
        }

    # Try original vuln's source
    if original:
        o_source = original.get("source", {})
        if isinstance(o_source, str):
            o_source = {}
        if o_source and o_source.get("file_path"):
            return {
                "file_path": o_source.get("file_path", ""),
                "line_number": o_source.get("line_number", ""),
                "code_snippet": o_source.get("code_snippet", ""),
                "endpoint": o_source.get("endpoint", ""),
            }

    # For register/password_reset, use affected_files[1] or affected_code as source hint
    affected_files = vuln.get("affected_files") or (original.get("affected_files") if original else None)
    if isinstance(affected_files, list) and len(affected_files) > 1:
        second = affected_files[1]
        if isinstance(second, dict):
            return {
                "file_path": second.get("file_path", ""),
                "line_number": second.get("line_range", second.get("line_number", "")),
                "code_snippet": "",
                "endpoint": "",
            }

    return {
        "file_path": "",
        "line_number": "",
        "code_snippet": "",
        "endpoint": "",
    }


def extract_call_stack(vuln, original):
    """Extract call stack / data flow steps."""
    # Try data_flow.flow_steps
    data_flow = vuln.get("data_flow") or (original.get("data_flow") if original else None)
    if isinstance(data_flow, dict):
        steps = data_flow.get("flow_steps", [])
        if steps:
            return steps

    return []


def extract_cwe(vuln, original):
    """Extract CWE from various fields."""
    for src in [vuln, original]:
        if not src:
            continue
        # Try cwe_id first (new schema), then cwe (legacy)
        cwe = src.get("cwe_id", "") or src.get("cwe", "")
        if cwe:
            return cwe
    return ""


def extract_cvss_vector(vuln, original):
    """Extract CVSS 4.0 vector string."""
    for src in [vuln, original]:
        if not src:
            continue
        vec = src.get("cvss_vector", "")
        if vec:
            return vec
    return ""


def extract_exploit_steps(vuln, original):
    """Extract exploitation steps array."""
    for src in [vuln, original]:
        if not src:
            continue
        steps = src.get("exploit_steps", [])
        if steps:
            return steps
    return []


def extract_description(vuln, original):
    """Extract description, trying multiple field names."""
    for src in [vuln, original]:
        if not src:
            continue
        desc = src.get("description", "")
        if desc:
            return desc
    return ""


def extract_root_cause(vuln, original):
    """Extract root cause."""
    for src in [vuln, original]:
        if not src:
            continue
        rc = src.get("root_cause", "")
        if rc:
            return rc
    return ""


def extract_recommendation(vuln, original):
    """Extract fix recommendation, trying multiple field names."""
    for src in [vuln, original]:
        if not src:
            continue
        for field in ["recommendation", "remediation", "fix"]:
            val = src.get(field, "")
            if val:
                return val
    return ""


def extract_exploit_conditions(vuln, original):
    """Extract exploit conditions / attack scenario.

    Supports both legacy format (list of strings) and new detailed format (list of dicts).
    Returns a list that can contain either strings or dicts with detailed condition info.
    """
    for src in [vuln, original]:
        if not src:
            continue
        ec = src.get("exploit_conditions", [])
        if ec:
            return ec
        # Try attack_scenario as fallback
        scenario = src.get("attack_scenario", "")
        if scenario:
            return [scenario]
    return []


def is_detailed_condition(condition):
    """Check if a condition is in the new detailed format (dict with 'condition' key)."""
    return isinstance(condition, dict) and "condition" in condition


def format_exploit_conditions_table(conditions):
    """Format exploit conditions as a detailed markdown table.

    Args:
        conditions: List of conditions (can be strings or dicts)

    Returns:
        List of markdown lines for the conditions section
    """
    lines = []

    # Check if we have any detailed conditions
    has_detailed = any(is_detailed_condition(c) for c in conditions)

    if has_detailed:
        # Use table format for detailed conditions
        lines.append("")
        lines.append("| Condition | Type | Required | Default | Vulnerable Value | Notes |")
        lines.append("|-----------|------|----------|---------|------------------|-------|")

        for cond in conditions:
            if is_detailed_condition(cond):
                condition_text = cond.get("condition", "")
                cond_type = cond.get("type", "—")
                required = "✅ Yes" if cond.get("required", False) else "❌ No"
                default_val = f"`{cond.get('default_value', '—')}`" if cond.get("default_value") else "—"
                vuln_val = f"`{cond.get('vulnerable_value', '—')}`" if cond.get("vulnerable_value") else "—"
                notes = cond.get("notes", "—")
                lines.append(f"| {condition_text} | {cond_type} | {required} | {default_val} | {vuln_val} | {notes} |")
            else:
                # Legacy string format - convert to table row
                lines.append(f"| {cond} | — | — | — | — | — |")
        lines.append("")
    else:
        # Use simple list format for legacy conditions
        lines.append("")
        for cond in conditions:
            lines.append(f"- {cond}")
        lines.append("")

    return lines


def extract_impact(vuln, original):
    """Extract impact description."""
    for src in [vuln, original]:
        if not src:
            continue
        impact = src.get("impact", "")
        if impact:
            return impact
    return ""


def build_crossref_map(merged_vulns):
    """Build a mapping from original module IDs to unified IDs for fixing cross-references.

    Vulnerability descriptions may reference other vulns by their original module IDs
    (e.g., "see VULN-001" meaning profile_update's VULN-001). This function builds
    a per-module mapping so we can replace these with unified IDs in text.

    Returns: dict of {(module, original_id): unified_id}
    """
    crossref = {}
    for v in merged_vulns:
        crossref[(v.get("module", ""), v.get("original_id", ""))] = v.get("unified_id", "")
    return crossref


def fix_crossrefs(text, module, crossref_map):
    """Replace original module IDs with unified IDs in description text.

    Only replaces IDs that belong to the same module (intra-module cross-references).
    Skips PoC filenames (poc_VULN-XXX.py patterns).
    """
    if not text:
        return text

    import re

    # Build module-specific replacements (same module only)
    replacements = {}
    for (mod, orig_id), unified_id in crossref_map.items():
        if mod == module and orig_id != unified_id:
            replacements[orig_id] = unified_id

    if not replacements:
        return text

    # Replace original IDs with unified IDs, but NOT in PoC filenames
    for orig_id, unified_id in sorted(replacements.items(), key=lambda x: -len(x[0])):
        # Negative lookbehind for "poc_" to avoid replacing in filenames
        pattern = r'(?<!poc_)(?<!\w)' + re.escape(orig_id) + r'(?!\w)'
        text = re.sub(pattern, unified_id, text)

    return text


def find_poc_file(output_dir, module, original_id, unified_id):
    """Find PoC file for this vulnerability."""
    # Try various naming patterns
    patterns = [
        os.path.join(output_dir, module, "pocs", f"poc_{original_id}.py"),
        os.path.join(output_dir, module, "pocs", f"poc_{unified_id}.py"),
        os.path.join(output_dir, module, "pocs", f"poc_{original_id}.json"),
    ]
    for p in patterns:
        if os.path.exists(p):
            return os.path.relpath(p, output_dir)
    return ""


def detect_language(output_dir):
    """Detect project language from _session.json."""
    session = load_json(os.path.join(output_dir, "_session.json"))
    if session:
        return session.get("language", "go")
    return "go"


def generate_vuln_section(vuln, original, lang_code, output_dir, crossref_map=None):
    """Generate markdown for a single vulnerability."""
    uid = vuln.get("unified_id", "VULN-???")
    vuln_type = vuln.get("vulnerability_type") or vuln.get("title") or vuln.get("sink_category") or ""
    severity = vuln.get("severity", "Medium")
    cvss = safe_float(vuln.get("cvss_score", 0))
    module = vuln.get("module", "")
    component = vuln.get("component", "")
    original_id = vuln.get("original_id", "")
    cwe = extract_cwe(vuln, original)

    sink = extract_sink_info(vuln, original)
    source = extract_source_info(vuln, original)
    call_stack = extract_call_stack(vuln, original)
    description = extract_description(vuln, original)
    root_cause = extract_root_cause(vuln, original)
    recommendation = extract_recommendation(vuln, original)
    exploit_conditions = extract_exploit_conditions(vuln, original)
    exploit_steps = extract_exploit_steps(vuln, original)
    impact = extract_impact(vuln, original)
    cvss_vector = extract_cvss_vector(vuln, original)
    poc_file = find_poc_file(output_dir, module, original_id, uid)

    # Also check poc_file field directly
    if not poc_file:
        poc_file = vuln.get("poc_file", "") or (original.get("poc_file", "") if original else "")

    # Fix cross-references: replace original module IDs with unified IDs in text
    if crossref_map:
        description = fix_crossrefs(description, module, crossref_map)
        root_cause = fix_crossrefs(root_cause, module, crossref_map)
        recommendation = fix_crossrefs(recommendation, module, crossref_map)
        impact = fix_crossrefs(impact, module, crossref_map)

    lines = []
    lines.append(f"### {uid}: {vuln_type}\n")

    # Info table
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| ID | {uid} |")
    lines.append(f"| Type | {vuln_type} |")
    lines.append(f"| CWE | {cwe if cwe else 'N/A'} |")
    lines.append(f"| Severity | {SEVERITY_ICONS.get(severity, severity)} |")
    lines.append(f"| CVSS 4.0 Score | {cvss:.1f} |")
    lines.append(f"| CVSS 4.0 Vector | `{cvss_vector}` |" if cvss_vector else "| CVSS 4.0 Vector | N/A |")
    lines.append(f"| Module | {module} |")
    if component:
        lines.append(f"| Component | {component} |")
    lines.append("")

    # Description
    if description:
        lines.append(f"**Description / 描述**: {description}")
        lines.append("")

    # SINK
    if sink["file_path"] or sink["code_snippet"]:
        lines.append("**SINK**")
        lines.append("")
        if sink["file_path"]:
            lines.append("| | |")
            lines.append("|---|---|")
            lines.append(f"| File | `{sink['file_path']}` |")
            lines.append(f"| Line | {sink['line_number']} |")
            if sink["function_name"]:
                lines.append(f"| Function | {sink['function_name']} |")
            lines.append("")
        if sink["code_snippet"]:
            lines.append(f"```{lang_code}")
            lines.append(sink["code_snippet"])
            lines.append("```")
            lines.append("")

    # SOURCE
    if source["file_path"] or source["code_snippet"]:
        lines.append("**SOURCE**")
        lines.append("")
        if source["file_path"]:
            lines.append("| | |")
            lines.append("|---|---|")
            lines.append(f"| File | `{source['file_path']}` |")
            lines.append(f"| Line | {source['line_number']} |")
            if source.get("endpoint"):
                lines.append(f"| Endpoint | {source['endpoint']} |")
            lines.append("")
        if source["code_snippet"]:
            lines.append(f"```{lang_code}")
            lines.append(source["code_snippet"])
            lines.append("```")
            lines.append("")

    # Call Stack (MANDATORY)
    lines.append("**Call Stack (SOURCE → SINK) / 调用栈**")
    lines.append("")
    if call_stack and len(call_stack) >= 2:
        lines.append("```")
        for step in call_stack:
            step_num = step.get("step", "?")
            fp = step.get("file_path", "")
            fn = step.get("function_name", "")
            ln = step.get("line_number", "")
            desc = step.get("description", "")
            lines.append(f"{step_num}. {fp}:{ln} — {fn}() — {desc}")
        lines.append("```")
    else:
        lines.append("> ⚠️ **Call stack data not provided**. See `data_flow.flow_steps[]` in vulnerability_analysis.json.")
        lines.append(">")
        lines.append("> Expected format: Step 1 (entry) → Step 2 (processing) → ... → Step N (vulnerable operation)")
    lines.append("")

    # Root Cause
    if root_cause:
        lines.append(f"**Root Cause / 根本原因**: {root_cause}")
        lines.append("")

    # Exploit Conditions
    if exploit_conditions:
        lines.append("**Exploit Conditions / 漏洞利用条件**")
        condition_lines = format_exploit_conditions_table(exploit_conditions)
        lines.extend(condition_lines)

    # Exploitation Steps
    if exploit_steps:
        lines.append("**Exploitation Steps / 利用步骤**")
        lines.append("")
        for step in exploit_steps:
            step_num = step.get("step", "?")
            action = step.get("action", "")
            http_method = step.get("http_method", "")
            endpoint = step.get("endpoint", "")
            params = step.get("parameters", "")
            if http_method and endpoint:
                lines.append(f"{step_num}. **Step {step_num}**: `{http_method} {endpoint}` — {action}")
            else:
                lines.append(f"{step_num}. **Step {step_num}**: {action}")
            if params:
                lines.append(f"   - Parameters: `{params}`")
        lines.append("")

    # Impact
    if impact:
        lines.append(f"**Impact / 影响**: {impact}")
        lines.append("")

    # PoC
    if poc_file:
        lines.append(f"**PoC**: `{poc_file}`")
        lines.append("")

    # Fix
    if recommendation:
        lines.append(f"**Fix / 修复建议**: {recommendation}")
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gen_section3.py <output_dir> [--lang zh|en|ja]")
        sys.exit(1)

    output_dir = sys.argv[1]

    # Detect language for code blocks
    lang_code = detect_language(output_dir)
    # Map language to code block language
    lang_map = {"golang": "go", "java": "java", "php": "php", "python": "python", "nodejs": "javascript"}
    code_lang = lang_map.get(lang_code, lang_code)

    print(f"[*] Loading merged vulnerabilities from {output_dir}...")
    merged = load_json(os.path.join(output_dir, "merged_vulnerabilities.json"))
    if not merged:
        print("[!] Failed to load merged_vulnerabilities.json")
        sys.exit(1)

    vulns = merged.get("vulnerabilities", [])
    if not vulns:
        print("[!] No vulnerabilities found in merged data")
        sys.exit(0)

    print(f"[*] Building original vulnerability index...")
    original_index = build_original_vuln_index(output_dir)
    print(f"    Indexed {len(original_index)} original vulnerabilities")

    # Build cross-reference map for fixing intra-module ID references in text
    crossref_map = build_crossref_map(vulns)
    print(f"    Built cross-reference map ({len(crossref_map)} entries)")

    # Sort by unified_id (VULN-001, VULN-002, ...)
    def sort_key(v):
        uid = v.get("unified_id", "VULN-999")
        try:
            return int(uid.split("-")[1])
        except (IndexError, ValueError):
            return 999
    vulns.sort(key=sort_key)

    print(f"[*] Generating Section 3 for {len(vulns)} vulnerabilities...")

    # Quality validation warnings
    warnings = []
    for vuln in vulns:
        uid = vuln.get("unified_id", "UNKNOWN")
        original = original_index.get((vuln.get("module", ""), vuln.get("original_id", "")))

        # Check call stack
        call_stack = extract_call_stack(vuln, original)
        if not call_stack or len(call_stack) < 2:
            warnings.append(f"[WARN] {uid}: MISSING call stack (data_flow.flow_steps[] should have ≥2 steps)")

        # Check sink code_snippet length
        sink = extract_sink_info(vuln, original)
        if sink.get("code_snippet"):
            sink_lines = len(sink["code_snippet"].split('\n'))
            if sink_lines < 8:
                warnings.append(f"[WARN] {uid}: sink.code_snippet too short ({sink_lines} lines, need 8-15)")

        # Check source code_snippet length
        source = extract_source_info(vuln, original)
        if source.get("code_snippet"):
            src_lines = len(source["code_snippet"].split('\n'))
            if src_lines < 8:
                warnings.append(f"[WARN] {uid}: source.code_snippet too short ({src_lines} lines, need 8-15)")

        # Check description length
        desc = extract_description(vuln, original)
        if len(desc) < 80:
            warnings.append(f"[WARN] {uid}: description too short ({len(desc)} chars, need 80-120)")

        # Check recommendation length
        rec = extract_recommendation(vuln, original)
        if len(rec) < 80:
            warnings.append(f"[WARN] {uid}: recommendation too short ({len(rec)} chars, need 80-120)")

    if warnings:
        print(f"\n[!] Quality Validation Warnings ({len(warnings)} issues):")
        for w in warnings[:15]:  # Limit display
            print(f"    {w}")
        if len(warnings) > 15:
            print(f"    ... and {len(warnings) - 15} more warnings")
        print()

    section_lines = []
    section_lines.append("<!-- Generated by gen_section3.py -->")
    section_lines.append("## 3. Vulnerability Details / 漏洞详情")
    section_lines.append("")
    section_lines.append("(Ordered by severity: Critical → High → Medium → Low)")
    section_lines.append("")

    for vuln in vulns:
        module = vuln.get("module", "")
        original_id = vuln.get("original_id", "")
        original = original_index.get((module, original_id))

        section_md = generate_vuln_section(vuln, original, code_lang, output_dir, crossref_map)
        section_lines.append(section_md)

    out_file = os.path.join(output_dir, "_section3.md")
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(section_lines))

    print(f"[+] Section 3 written to {out_file}")
    print(f"    Total: {len(vulns)} vulnerability entries")


if __name__ == "__main__":
    main()
