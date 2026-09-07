#!/usr/bin/env python3
"""Validate and append RPC-handler source entries to the shared sources JSON.

Usage:
    python scripts/record_rpc_handlers.py <item1> [item2] ...

The output file is read from the ZAST_ENUMERATION_SOURCES_FILE env var (the host
injects it). Pass -o <file> only for manual/standalone runs; the env var wins.

Each item is a JSON object describing one RPC handler method, e.g.:
    '{"service":"MyService","method":"createItem",
      "framework":"thrift",
      "region":{"file_path":"src/.../Handler.java","start_line":10,"end_line":40}}'

Self-contained copy of vuln_spec.RpcHandlerSource — the worker runs this script
inside the target workspace where vuln_spec is not installed, so the validator
cannot import the real model. This schema is bound to THREE places that must move
together: this class, the "Output schema" table in the enumerate-rpc-handlers-worker
agent definition, and vuln_spec.RpcHandlerSource (what llm-auditor parses the file
back into). Changing a field means changing all three. See the "Skill output
schemas <-> zast-vuln-spec" chapter in the repo CLAUDE.md.

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

from pydantic import BaseModel, Field, ValidationError, field_validator

# Project root directory — prefer PWD env var, fall back to cwd.
_PROJECT_ROOT = os.environ.get("PWD") or os.getcwd()


def _resolve_file_path(v: str) -> str:
    """Resolve a relative file_path against PWD. Must be relative, '/'-separated,
    and resolve to exactly one existing file (direct hit, else a unique recursive
    glob match); 0 or >1 matches are rejected."""
    if "\\" in v:
        raise ValueError(f"file_path must use '/' as separator, got backslash: {v}")
    if re.match(r"^[A-Za-z]:", v) or v.startswith("/"):
        raise ValueError(f"file_path must be relative, got absolute path: {v}")

    direct = os.path.join(_PROJECT_ROOT, v)
    if os.path.isfile(direct):
        return v

    pattern = os.path.join(_PROJECT_ROOT, "**", v)
    matches = [m for m in glob.glob(pattern, recursive=True) if os.path.isfile(m)]
    if len(matches) == 0:
        raise ValueError(f"file_path not found under project root: {v} (root={_PROJECT_ROOT})")
    if len(matches) > 1:
        rel = [os.path.relpath(m, _PROJECT_ROOT) for m in matches]
        raise ValueError(f"file_path ambiguous, matched multiple files: {rel}")
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


class RpcHandlerSource(BaseModel):
    """One RPC handler method as an enumerated source (gRPC/Thrift/Dubbo)."""

    kind: str = "rpc"
    service: str = Field(description="IDL service name, e.g. 'MyService'")
    method: str = Field(description="RPC method name, case-sensitive, e.g. 'createItem'")
    framework: str = Field(description="RPC framework: 'thrift' | 'grpc' | 'dubbo'")
    region: Region = Field(description="Source code location of the handler method")

    @field_validator("kind")
    @classmethod
    def force_rpc_kind(cls, v: str) -> str:
        # This script only records RPC sources; ignore any provided kind and pin it.
        return "rpc"


def parse_and_validate(json_str: str, index: int) -> tuple[dict | None, str | None]:
    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as e:
        return None, f"Item {index}: invalid JSON: {e}"
    try:
        model = RpcHandlerSource.model_validate(raw)
    except ValidationError as e:
        return None, f"Item {index}: validation error: {e}"
    return model.model_dump(), None


def main():
    parser = argparse.ArgumentParser(
        description="Validate and append RPC handler source entries to a JSON file."
    )
    parser.add_argument("-o", "--output",
                        help="Fallback output path for manual/standalone runs. Ignored when "
                        "ZAST_ENUMERATION_SOURCES_FILE is set (the host injects the path there).")
    parser.add_argument("items", nargs="+", metavar="item",
                        help="JSON string(s) representing RpcHandlerSource entries")
    args = parser.parse_args()

    # The host injects the authoritative output path via this env var, so the recording agent
    # never names it and cannot misroute records (agents have rebuilt cwd-relative paths and
    # silently written to a phantom file). Env wins over -o; -o is a manual/standalone fallback.
    output = os.environ.get("ZAST_ENUMERATION_SOURCES_FILE") or args.output
    if not output:
        print("[ERROR] No output path: set ZAST_ENUMERATION_SOURCES_FILE or pass -o")
        sys.exit(1)
    filepath = Path(output)

    valid_items: list[dict] = []
    errors: list[str] = []
    for i, json_str in enumerate(args.items):
        item, error = parse_and_validate(json_str, i)
        if item is not None:
            valid_items.append(item)
        else:
            errors.append(error)

    # Load, append, write — under an exclusive lock so concurrent workers never clobber
    # each other's records.
    # Always open "a+": it creates the file if missing and NEVER truncates on open.
    # "w+" would truncate at open time — before flock is held — so first-time-
    # concurrent workers could wipe each other's records. The clear-and-rewrite
    # happens inside the lock via truncate().
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
            # Flush WHILE holding the lock. json.dump only fills Python's buffer; without this
            # the real write() lands at close(), after LOCK_UN — and under a+ (O_APPEND) that late
            # write appends a second array onto the next lock holder's content, corrupting the file.
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

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
