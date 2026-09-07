#!/usr/bin/env python3
"""
Validate and append controller endpoint entries to a JSON file.

Usage:
    python scripts/record_controllers.py <item1> [item2] ...

The output file is read from the ZAST_ENUMERATION_SOURCES_FILE env var (the host
injects it). Pass -o <file> only for manual/standalone runs; the env var wins.

Each item is a JSON string representing an HttpControllerSource, e.g.:
    '{"endpoint":"/api/users","method":"GET","protocol":"http","region":{"file_path":"src/api/users.py","start_line":10,"end_line":20}}'

Method field accepts: single ("GET"), comma-separated ("GET,POST"), or "*" for all.

Exit codes:
    0 - All items recorded successfully
    1 - Some or all items failed (valid items are still written)
"""

import argparse
import fcntl
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

# Project root directory — prefer PWD env var, fall back to cwd.
_PROJECT_ROOT = os.environ.get("PWD") or os.getcwd()

# HTTP methods, used to strip a method accidentally prefixed onto an endpoint.
_HTTP_METHODS = {
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT",
}


def _resolve_file_path(v: str) -> str:
    """Resolve a relative file_path against PWD via glob.

    Rules:
      - Must be relative and use '/' as separator.
      - If the path resolves to exactly one file under PWD → normalize it.
      - If glob returns 0 or multiple matches → reject.
    """
    if "\\" in v:
        raise ValueError(
            f"file_path must use '/' as separator, got backslash: {v}"
        )
    if re.match(r"^[A-Za-z]:", v) or v.startswith("/"):
        raise ValueError(f"file_path must be relative, got absolute path: {v}")

    # Direct match first
    direct = os.path.join(_PROJECT_ROOT, v)
    if os.path.isfile(direct):
        return v

    # Try glob under PWD — handles cases where the agent omits a prefix
    pattern = os.path.join(_PROJECT_ROOT, "**", v)
    matches = glob.glob(pattern, recursive=True)
    # Keep only regular files
    matches = [m for m in matches if os.path.isfile(m)]

    if len(matches) == 0:
        raise ValueError(
            f"file_path not found under project root: {v} "
            f"(root={_PROJECT_ROOT})"
        )
    if len(matches) > 1:
        rel_matches = [os.path.relpath(m, _PROJECT_ROOT) for m in matches]
        raise ValueError(
            f"file_path ambiguous, matched multiple files: {rel_matches}"
        )

    # Return path relative to PWD
    return os.path.relpath(matches[0], _PROJECT_ROOT)


class Region(BaseModel):
    """Source code location."""

    file_path: str
    start_line: int = Field(ge=1)
    end_line: int | None = Field(default=None, ge=1)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        return _resolve_file_path(v)


class HttpControllerSource(BaseModel):
    """HTTP controller endpoint info.

    Self-contained copy of `vuln_spec.HttpControllerSource` — the worker runs this
    script inside the target workspace where `vuln_spec` is not installed, so the
    validator cannot import the real model. This schema is bound to THREE places
    that must move together: this class, the field table in the
    `enumerate-http-controllers-worker` agent definition (the authoritative prose the
    worker LLM reads), and `vuln_spec.HttpControllerSource` (what `llm-auditor`
    parses the file back into). Changing a field means changing all three. See the
    "Skill output schemas ⇄ zast-vuln-spec" chapter in the repo CLAUDE.md.
    """

    endpoint: str = Field(description="HTTP endpoint path (e.g., '/api/v1/users')")
    method: str = Field(
        description='HTTP method: single ("GET"), comma-separated ("GET,POST"), or "*" for all'
    )
    protocol: str = Field(
        default="http",
        description="Protocol type (e.g., 'http', 'websocket', ...)",
    )
    region: Region = Field(description="Source code location of the controller")
    graphql_operation: Optional[str] = Field(
        default=None,
        description="GraphQL operation identity (e.g. 'Mutation.addTemplate') for a GraphQL resolver; omit/None for ordinary HTTP endpoints.",
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        # Strip a leading HTTP-method token some models prefix onto the path ("GET /overview") so the stored endpoint is path-only and matches the path-only label at diff time — only when the first token is purely method(s) + the rest is a path, so "/getData" is untouched.
        s = v.strip()
        head, sep, rest = s.partition(" ")
        if sep and rest.lstrip().startswith("/"):
            tokens = [t.strip().upper() for t in head.split(",") if t.strip()]
            if tokens and all(t in _HTTP_METHODS for t in tokens):
                return rest.lstrip()
        return s

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v == "*":
            return v
        parts = [p.strip().upper() for p in v.split(",")]
        if "*" in parts and len(parts) > 1:
            raise ValueError(
                "'*' must appear alone, cannot combine with other methods"
            )
        return ",".join(sorted(set(parts)))


def parse_and_validate(
    json_str: str, index: int
) -> tuple[dict | None, str | None]:
    """Parse and validate a single JSON item.

    Returns (parsed_dict, None) on success, or (None, error_message) on failure.
    """
    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as e:
        return None, f"Item {index}: invalid JSON: {e}"

    try:
        model = HttpControllerSource.model_validate(raw)
    except ValidationError as e:
        return None, f"Item {index}: validation error: {e}"

    return model.model_dump(), None


def main():
    parser = argparse.ArgumentParser(
        description="Validate and append controller endpoint entries to a JSON file."
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Fallback output path for manual/standalone runs. Ignored when "
        "ZAST_ENUMERATION_SOURCES_FILE is set (the host injects the authoritative path there).",
    )
    parser.add_argument(
        "items",
        nargs="+",
        metavar="item",
        help="JSON string(s) representing HttpControllerSource entries",
    )
    args = parser.parse_args()

    # The host (llm-auditor) injects the authoritative output path via this env var, so the
    # recording agent never has to name it — and structurally cannot send records elsewhere.
    # We saw agents rebuild a cwd-relative path ("/local-workspace/src/<tail>") instead of the
    # canonical file, silently routing whole batches to a phantom file the host never reads.
    # Env wins over -o; -o remains only as a fallback for manual/standalone invocation.
    output = os.environ.get("ZAST_ENUMERATION_SOURCES_FILE") or args.output
    if not output:
        print("[ERROR] No output path: set ZAST_ENUMERATION_SOURCES_FILE or pass -o")
        sys.exit(1)
    filepath = Path(output)

    # Validate all items
    valid_items: list[dict] = []
    errors: list[str] = []

    for i, json_str in enumerate(args.items):
        item, error = parse_and_validate(json_str, i)
        if item is not None:
            valid_items.append(item)
        else:
            errors.append(error)

    # Load, append, write — under an exclusive file lock so concurrent workers never clobber each other's records.
    # Always open "a+": it creates the file if missing and NEVER truncates on open. "w+" would truncate at open
    # time — before flock is held — so a batch of first-time-concurrent workers could wipe each other's already
    # committed records out from under the lock. The real clear-and-rewrite happens inside the lock via truncate().
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = f.read()
            data = json.loads(raw) if raw.strip() else []
            if not isinstance(data, list):
                print(f"[ERROR] {filepath}: root must be a list, got {type(data).__name__}")
                sys.exit(1)
            data.extend(valid_items)
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2, ensure_ascii=False)
            # Push the buffered bytes to disk WHILE still holding the lock. json.dump only fills
            # Python's buffer; without this the real write() lands at close(), after LOCK_UN — and
            # under a+ (O_APPEND) that late write appends a second array onto whatever the next
            # lock holder already wrote, corrupting the file ("Extra data" on reload).
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    # Report
    if valid_items:
        print(f"[RECORDED] {len(valid_items)} item(s) -> {filepath} (total: {len(data)})")

    if errors:
        print(f"[ERROR] {len(errors)} item(s) failed:")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
