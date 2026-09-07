#!/usr/bin/env python3
"""
Deduplicate webapp_sources.json.

Removes only BYTE-IDENTICAL entries — same endpoint, HTTP method, AND region
— keeping the first occurrence, and prints removed items for debugging. Two
handlers on the same path but different method/region (e.g. GET vs POST
/dashboardUser) are DISTINCT audit units and are kept; collapsing them by path
alone would drop a real handler from the audit. Finer, AST-based collapsing of
near-duplicate regions of the same handler happens later when llm-auditor
loads this file (it cannot run here — vuln_spec/zast_codebase aren't importable
inside the target workspace, so this script stays pure-stdlib).

Usage:
    python scripts/dedup_controllers.py [CONTROLLER_SOURCES_FILE]

The file to dedup is the host-injected ZAST_ENUMERATION_SOURCES_FILE — the same
authoritative path the record scripts wrote to, so the agent never has to name it.
A positional arg is honored only as a manual/standalone fallback (env wins).

Exit codes:
    0 - Success (no duplicates found, or duplicates removed)
    1 - File error
"""

import json
import os
import sys
from pathlib import Path


def main():
    target = os.environ.get("ZAST_ENUMERATION_SOURCES_FILE") or (
        sys.argv[1] if len(sys.argv) >= 2 else None
    )
    if not target:
        print(f"Usage: {sys.argv[0]} [CONTROLLER_SOURCES_FILE]  (or set ZAST_ENUMERATION_SOURCES_FILE)")
        sys.exit(1)

    filepath = Path(target)

    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)

    try:
        content = filepath.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        print(f"[ERROR] Root must be a list, got {type(data).__name__}")
        sys.exit(1)

    seen: dict[str, int] = {}
    unique: list[dict] = []
    removed: list[tuple[int, dict]] = []

    for i, item in enumerate(data):
        # Byte-identity key over (endpoint, method, region): only exact dups collapse; distinct method/region variants of the same path survive.
        key = json.dumps(
            {
                "endpoint": item.get("endpoint", ""),
                "method": item.get("method", ""),
                "region": item.get("region", {}),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if key in seen:
            removed.append((i, item))
        else:
            seen[key] = i
            unique.append(item)

    if not removed:
        print(f"[OK] No duplicates found. {len(data)} item(s) in {filepath}")
        sys.exit(0)

    # Write deduplicated data
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"[DEDUP] {filepath}: {len(data)} -> {len(unique)} item(s), {len(removed)} duplicate(s) removed:")
    for idx, item in removed:
        print(f"  [{idx}] {item.get('method', '')} {item.get('endpoint', '<unknown>')}")

    sys.exit(0)


if __name__ == "__main__":
    main()
