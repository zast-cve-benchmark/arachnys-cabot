#!/usr/bin/env python3
"""
Vulnerability Analysis JSON Validator

Validates vulnerability_analysis.json files against the required schema.
Run this after Step 2 to ensure JSON compliance before proceeding to Step 3.

Usage:
    python3 validate_vuln_json.py <path_to_vulnerability_analysis.json>
    python3 validate_vuln_json.py <output_dir>  # validates all modules

Exit codes:
    0 = All validations passed
    1 = Validation errors found (fix before proceeding)
"""

import json
import os
import sys
import re

VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}
VALID_PREFIXES = {"LOGIN", "REG", "PWD", "PROF", "PAY"}


def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return None, str(e)


def validate_vulnerability(vuln, errors, warnings):
    """Validate a single vulnerability entry."""
    vid = vuln.get("vulnerability_id", "UNKNOWN")

    # Required fields
    required_fields = [
        "vulnerability_id", "vulnerability_type", "cwe_id", "severity",
        "cvss_score", "cvss_vector", "description", "recommendation",
        "sink", "source", "data_flow", "exploit_conditions"
    ]

    for field in required_fields:
        if field not in vuln:
            errors.append(f"{vid}: Missing required field '{field}'")

    # Check for wrong field names (common mistakes)
    wrong_names = {
        "id": "vulnerability_id",
        "name": "vulnerability_type",
        "title": "vulnerability_type",
        "remediation": "recommendation",
        "fix": "recommendation",
        "cwe": "cwe_id",
        "attack_scenario": "exploit_conditions (as array)",
        "exploitation": "exploit_steps (as array of objects)",
    }
    for wrong, correct in wrong_names.items():
        if wrong in vuln and correct.split()[0] not in vuln:
            errors.append(f"{vid}: Used '{wrong}' instead of '{correct}'")

    # vulnerability_id format
    if "vulnerability_id" in vuln:
        vid_val = vuln["vulnerability_id"]
        if not re.match(r"^[A-Z]+_\d{3}$", vid_val):
            errors.append(f"{vid}: vulnerability_id must match pattern PREFIX_NNN (e.g., LOGIN_001)")

    # cwe_id format
    if "cwe_id" in vuln:
        cwe = vuln["cwe_id"]
        if cwe and not re.match(r"^CWE-\d+$", cwe):
            warnings.append(f"{vid}: cwe_id should match pattern CWE-NNN (got: {cwe})")

    # severity
    if "severity" in vuln:
        if vuln["severity"] not in VALID_SEVERITIES:
            errors.append(f"{vid}: severity must be one of {VALID_SEVERITIES}")

    # cvss_score must be number
    if "cvss_score" in vuln:
        score = vuln["cvss_score"]
        if isinstance(score, str):
            errors.append(f"{vid}: cvss_score must be a number, not string (got: \"{score}\")")
        elif not isinstance(score, (int, float)):
            errors.append(f"{vid}: cvss_score must be a number")
        elif not (0.0 <= score <= 10.0):
            warnings.append(f"{vid}: cvss_score should be 0.0-10.0 (got: {score})")

    # cvss_vector format
    if "cvss_vector" in vuln:
        vec = vuln["cvss_vector"]
        if vec and not vec.startswith("CVSS:4.0/"):
            errors.append(f"{vid}: cvss_vector must start with 'CVSS:4.0/' (got: {vec[:20]}...)")

    # description length
    if "description" in vuln:
        desc = vuln["description"]
        if len(desc) < 80:
            warnings.append(f"{vid}: description too short ({len(desc)} chars, need 80-120)")
        elif len(desc) > 150:
            warnings.append(f"{vid}: description too long ({len(desc)} chars, recommend 80-120)")

    # recommendation length
    if "recommendation" in vuln:
        rec = vuln["recommendation"]
        if len(rec) < 80:
            warnings.append(f"{vid}: recommendation too short ({len(rec)} chars, need 80-120)")
        elif len(rec) > 150:
            warnings.append(f"{vid}: recommendation too long ({len(rec)} chars, recommend 80-120)")

    # sink must be dict with required fields
    if "sink" in vuln:
        sink = vuln["sink"]
        if isinstance(sink, str):
            errors.append(f"{vid}: sink must be a dict, not string")
        elif isinstance(sink, dict):
            sink_required = ["file_path", "line_number", "code_snippet"]
            for field in sink_required:
                if field not in sink or not sink[field]:
                    errors.append(f"{vid}: sink missing '{field}'")
            # Check code_snippet length
            if "code_snippet" in sink:
                lines = len(sink["code_snippet"].split('\n'))
                if lines < 8:
                    warnings.append(f"{vid}: sink.code_snippet too short ({lines} lines, need 8-15)")

    # source must be dict with required fields
    if "source" in vuln:
        source = vuln["source"]
        if isinstance(source, str):
            errors.append(f"{vid}: source must be a dict, not string")
        elif isinstance(source, dict):
            source_required = ["file_path", "line_number"]
            for field in source_required:
                if field not in source or not source[field]:
                    warnings.append(f"{vid}: source missing '{field}'")
            # Check code_snippet
            if "code_snippet" in source:
                lines = len(source["code_snippet"].split('\n'))
                if lines < 8:
                    warnings.append(f"{vid}: source.code_snippet too short ({lines} lines, need 8-15)")
            else:
                warnings.append(f"{vid}: source missing 'code_snippet'")
    else:
        errors.append(f"{vid}: source is required (not omitted)")

    # data_flow must have flow_steps[]
    if "data_flow" in vuln:
        df = vuln["data_flow"]
        if isinstance(df, dict):
            if "flow_steps" not in df:
                errors.append(f"{vid}: data_flow must have 'flow_steps' array")
            else:
                steps = df["flow_steps"]
                if not isinstance(steps, list):
                    errors.append(f"{vid}: data_flow.flow_steps must be an array")
                elif len(steps) < 2:
                    errors.append(f"{vid}: data_flow.flow_steps must have ≥2 entries (got: {len(steps)})")
                else:
                    # Validate each step
                    for i, step in enumerate(steps):
                        step_required = ["step", "file_path", "function_name", "line_number", "description"]
                        for field in step_required:
                            if field not in step:
                                warnings.append(f"{vid}: flow_steps[{i}] missing '{field}'")
        else:
            errors.append(f"{vid}: data_flow must be a dict")
    else:
        errors.append(f"{vid}: data_flow is required (not omitted)")

    # exploit_conditions must be array
    if "exploit_conditions" in vuln:
        ec = vuln["exploit_conditions"]
        if isinstance(ec, str):
            errors.append(f"{vid}: exploit_conditions must be an array, not string")
        elif not isinstance(ec, list):
            errors.append(f"{vid}: exploit_conditions must be an array")

    # exploit_steps should be array of objects
    if "exploit_steps" in vuln:
        es = vuln["exploit_steps"]
        if isinstance(es, str):
            errors.append(f"{vid}: exploit_steps must be an array of objects, not string")
        elif isinstance(es, list) and es:
            if not isinstance(es[0], dict):
                errors.append(f"{vid}: exploit_steps entries must be objects, not {type(es[0]).__name__}")


def validate_file(path):
    """Validate a single vulnerability_analysis.json file."""
    print(f"\n[*] Validating: {path}")

    data = None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"    [ERROR] Invalid JSON: {e}")
        return 1
    except FileNotFoundError:
        print(f"    [ERROR] File not found")
        return 1

    errors = []
    warnings = []

    # Check top-level structure
    if "vulnerabilities" not in data:
        errors.append("Missing 'vulnerabilities' array at top level")

    if "scan_summary" not in data:
        warnings.append("Missing 'scan_summary' at top level")
    elif "by_severity" not in data.get("scan_summary", {}):
        warnings.append("scan_summary missing 'by_severity'")

    # Validate each vulnerability
    vulns = data.get("vulnerabilities", [])
    for vuln in vulns:
        validate_vulnerability(vuln, errors, warnings)

    # Report results
    if errors:
        print(f"\n    [ERRORS] {len(errors)} validation errors (MUST fix):")
        for e in errors:
            print(f"        ✗ {e}")

    if warnings:
        print(f"\n    [WARNINGS] {len(warnings)} quality issues:")
        for w in warnings[:10]:
            print(f"        ⚠ {w}")
        if len(warnings) > 10:
            print(f"        ... and {len(warnings) - 10} more warnings")

    if not errors and not warnings:
        print(f"    [OK] All {len(vulns)} vulnerabilities passed validation")
    elif not errors:
        print(f"\n    [PASS] No critical errors, but {len(warnings)} warnings")

    return 1 if errors else 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_vuln_json.py <path_or_dir>")
        print("\nExamples:")
        print("  python3 validate_vuln_json.py login/vulnerability_analysis.json")
        print("  python3 validate_vuln_json.py /path/to/logic_vuln_audit/")
        sys.exit(1)

    path = sys.argv[1]
    exit_code = 0

    if os.path.isfile(path):
        exit_code = validate_file(path)
    elif os.path.isdir(path):
        # Validate all modules
        modules = ["login", "register", "password_reset", "profile_update", "payment"]
        found = 0
        for module in modules:
            vuln_file = os.path.join(path, module, "vulnerability_analysis.json")
            if os.path.exists(vuln_file):
                found += 1
                result = validate_file(vuln_file)
                if result != 0:
                    exit_code = 1

        if found == 0:
            print(f"[!] No vulnerability_analysis.json files found in {path}")
            exit_code = 1
        else:
            print(f"\n[*] Validated {found} module(s)")
    else:
        print(f"[!] Path not found: {path}")
        exit_code = 1

    if exit_code == 0:
        print("\n[+] All validations PASSED")
    else:
        print("\n[!] Validation FAILED — fix errors before proceeding to Step 3")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
