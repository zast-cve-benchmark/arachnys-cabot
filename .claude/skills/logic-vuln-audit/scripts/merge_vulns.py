#!/usr/bin/env python3
"""
Vulnerability Merge Helper Script

Merges vulnerability_analysis.json files from multiple modules into
a single merged_vulnerabilities.json with deduplication and unified IDs.

Usage:
    python3 merge_vulns.py <output_dir>

Example:
    python3 merge_vulns.py /path/to/project/logic_vuln_audit/
"""

import json
import os
import sys
from datetime import datetime

MODULES = ["login", "register", "password_reset", "profile_update", "payment"]
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def load_vulns(output_dir: str) -> tuple:
    """Load all vulnerability_analysis.json files."""
    all_vulns = []
    modules_analyzed = []
    modules_failed = []

    for module in MODULES:
        vuln_file = os.path.join(output_dir, module, "vulnerability_analysis.json")
        if not os.path.exists(vuln_file):
            continue
        try:
            with open(vuln_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            vulns = data.get("vulnerabilities", [])
            for v in vulns:
                v["_source_module"] = module
                # Normalize vulnerability_id from various agent naming conventions
                if "vulnerability_id" not in v:
                    v["vulnerability_id"] = v.get("id", v.get("vuln_id", "UNKNOWN"))
                # Normalize vulnerability_type from various agent naming conventions
                if not v.get("vulnerability_type"):
                    v["vulnerability_type"] = v.get("title", v.get("sink_category", ""))
                # Normalize sink/source to always be dicts
                if not isinstance(v.get("sink"), dict):
                    v["sink"] = {}
                if not isinstance(v.get("source"), dict):
                    v["source"] = {}
                # Normalize cvss_score to float
                try:
                    v["cvss_score"] = float(v.get("cvss_score", 0))
                except (TypeError, ValueError):
                    v["cvss_score"] = 0.0
            all_vulns.extend(vulns)
            modules_analyzed.append(module)
        except Exception as e:
            modules_failed.append(module)
            print(f"[WARN] Failed to load {vuln_file}: {e}")

    return all_vulns, modules_analyzed, modules_failed


def normalize_sink(sink) -> dict:
    """Ensure sink is always a dict."""
    if isinstance(sink, dict):
        return sink
    return {}


def is_duplicate(a: dict, b: dict) -> bool:
    """Check if two vulnerabilities are duplicates."""
    a_sink = normalize_sink(a.get("sink"))
    b_sink = normalize_sink(b.get("sink"))

    # Same file, nearby lines, AND same vulnerability type
    if (a_sink.get("file_path") == b_sink.get("file_path") and
            a_sink.get("line_number") and b_sink.get("line_number") and
            abs(a_sink["line_number"] - b_sink["line_number"]) <= 5 and
            a.get("vulnerability_type") == b.get("vulnerability_type")):
        return True

    # Same function, type, and root cause pattern
    if (a_sink.get("function_name") == b_sink.get("function_name") and
            a.get("vulnerability_type") == b.get("vulnerability_type") and
            a.get("root_cause") == b.get("root_cause")):
        return True

    return False


def merge_duplicate(kept: dict, removed: dict):
    """Merge a duplicate into the kept record."""
    # Keep higher severity
    if SEVERITY_ORDER.get(removed.get("severity"), 99) < SEVERITY_ORDER.get(kept.get("severity"), 99):
        previous_severity = kept.get("severity")
        kept["severity"] = removed["severity"]
        kept["severity_adjusted"] = True
        kept["severity_adjusted_reason"] = f"Upgraded from {previous_severity} based on duplicate from {removed['_source_module']}"

    # Track all original IDs
    if "original_ids" not in kept:
        kept["original_ids"] = [kept.get("vulnerability_id", "")]
    kept["original_ids"].append(removed.get("vulnerability_id", ""))

    # Track all affected modules
    if "affected_modules" not in kept:
        kept["affected_modules"] = [kept["_source_module"]]
    if removed["_source_module"] not in kept["affected_modules"]:
        kept["affected_modules"].append(removed["_source_module"])


def deduplicate(vulns: list) -> tuple:
    """Remove duplicate vulnerabilities."""
    deduped = []
    removed_count = 0

    for vuln in vulns:
        is_dup = False
        for existing in deduped:
            if is_duplicate(existing, vuln):
                merge_duplicate(existing, vuln)
                removed_count += 1
                is_dup = True
                break
        if not is_dup:
            deduped.append(vuln)

    return deduped, removed_count


def validate_quality(vulns: list) -> list:
    """Validate and warn about quality issues in vulnerabilities."""
    warnings = []

    for v in vulns:
        vid = v.get("vulnerability_id", "UNKNOWN")
        module = v.get("_source_module", "unknown")

        # Check description length (should be 80-120 chars)
        desc = v.get("description", "")
        if len(desc) < 80:
            warnings.append(f"[WARN] {module}/{vid}: description too short ({len(desc)} chars, need 80-120)")
        elif len(desc) > 150:
            warnings.append(f"[WARN] {module}/{vid}: description too long ({len(desc)} chars, max 120)")

        # Check recommendation length (should be 80-120 chars)
        rec = v.get("recommendation", "")
        if len(rec) < 80:
            warnings.append(f"[WARN] {module}/{vid}: recommendation too short ({len(rec)} chars, need 80-120)")
        elif len(rec) > 150:
            warnings.append(f"[WARN] {module}/{vid}: recommendation too long ({len(rec)} chars, max 120)")

        # Check code_snippet length (should be 8-15 lines)
        sink = v.get("sink", {})
        if isinstance(sink, dict):
            sink_code = sink.get("code_snippet", "")
            sink_lines = len(sink_code.split('\n')) if sink_code else 0
            if sink_lines < 8 and sink_lines > 0:
                warnings.append(f"[WARN] {module}/{vid}: sink.code_snippet too short ({sink_lines} lines, need 8-15)")

        source = v.get("source", {})
        if isinstance(source, dict):
            src_code = source.get("code_snippet", "")
            src_lines = len(src_code.split('\n')) if src_code else 0
            if src_lines < 8 and src_lines > 0:
                warnings.append(f"[WARN] {module}/{vid}: source.code_snippet too short ({src_lines} lines, need 8-15)")

        # Check call stack exists
        data_flow = v.get("data_flow", {})
        if isinstance(data_flow, dict):
            flow_steps = data_flow.get("flow_steps", [])
            if not flow_steps or len(flow_steps) < 2:
                warnings.append(f"[WARN] {module}/{vid}: MISSING call stack (data_flow.flow_steps[] should have ≥2 steps)")

    # Print all warnings
    if warnings:
        print(f"\n[!] Quality Validation Warnings ({len(warnings)} issues):")
        for w in warnings[:20]:  # Limit to first 20 warnings
            print(f"    {w}")
        if len(warnings) > 20:
            print(f"    ... and {len(warnings) - 20} more warnings")
        print()

    return vulns


def assign_unified_ids(vulns: list) -> list:
    """Sort by severity then CVSS descending, and assign VULN-XXX IDs."""
    vulns.sort(key=lambda v: (
        SEVERITY_ORDER.get(v.get("severity"), 99),
        -(v.get("cvss_score") if isinstance(v.get("cvss_score"), (int, float)) else 0),
        MODULES.index(v["_source_module"]) if v["_source_module"] in MODULES else 99
    ))

    for i, vuln in enumerate(vulns, 1):
        vuln["unified_id"] = f"VULN-{i:03d}"
        vuln["original_id"] = vuln.get("vulnerability_id", "")
        if "original_ids" not in vuln:
            vuln["original_ids"] = [vuln["original_id"]]
        if "affected_modules" not in vuln:
            vuln["affected_modules"] = [vuln["_source_module"]]
        vuln["module"] = vuln.pop("_source_module")
        if "severity_adjusted" not in vuln:
            vuln["severity_adjusted"] = False

    return vulns


def compute_summary(vulns: list, modules_analyzed: list,
                    modules_failed: list, dedup_count: int) -> dict:
    """Compute merge summary statistics."""
    by_severity = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    by_module = {m: 0 for m in MODULES}
    by_module_severity = {}
    adjustments = 0

    for v in vulns:
        sev = v.get("severity", "Low")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        mod = v.get("module", "")
        if mod in by_module:
            by_module[mod] += 1
        # Track per-module severity breakdown
        if mod not in by_module_severity:
            by_module_severity[mod] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        by_module_severity[mod][sev] = by_module_severity[mod].get(sev, 0) + 1
        if v.get("severity_adjusted"):
            adjustments += 1

    # Remove modules with 0 count that weren't analyzed
    by_module = {k: v for k, v in by_module.items() if k in modules_analyzed}
    by_module_severity = {k: v for k, v in by_module_severity.items() if k in modules_analyzed}

    return {
        "total_vulnerabilities": len(vulns),
        "by_severity": by_severity,
        "by_module": by_module,
        "by_module_severity": by_module_severity,
        "duplicates_removed": dedup_count,
        "severity_adjustments": adjustments,
        "modules_analyzed": modules_analyzed,
        "modules_failed": modules_failed
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 merge_vulns.py <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]

    print(f"[*] Loading vulnerabilities from {output_dir}...")
    all_vulns, modules_analyzed, modules_failed = load_vulns(output_dir)
    print(f"    Loaded {len(all_vulns)} vulnerabilities from {len(modules_analyzed)} modules")

    if not all_vulns:
        print("[!] No vulnerabilities found. Exiting.")
        sys.exit(0)

    print("[*] Validating quality requirements...")
    validate_quality(all_vulns)

    print("[*] Deduplicating...")
    deduped, dedup_count = deduplicate(all_vulns)
    print(f"    Removed {dedup_count} duplicates, {len(deduped)} remaining")

    print("[*] Assigning unified IDs...")
    unified = assign_unified_ids(deduped)

    summary = compute_summary(unified, modules_analyzed, modules_failed, dedup_count)

    output = {
        "merge_summary": summary,
        "vulnerabilities": unified
    }

    out_file = os.path.join(output_dir, "merged_vulnerabilities.json")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[+] Merged output written to {out_file}")
    print(f"    Total: {summary['total_vulnerabilities']} vulnerabilities")
    print(f"    Critical: {summary['by_severity']['Critical']}, "
          f"High: {summary['by_severity']['High']}, "
          f"Medium: {summary['by_severity']['Medium']}, "
          f"Low: {summary['by_severity']['Low']}")


if __name__ == "__main__":
    main()
