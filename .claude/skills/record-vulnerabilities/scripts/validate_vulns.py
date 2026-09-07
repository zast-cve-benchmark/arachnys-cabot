#!/usr/bin/env python3
"""Validate a worker's vulns JSON file against the SimpleVulnInfo schema.

Usage:  python validate_vulns.py <path-to-json>
Exit:   0 = valid, non-zero = invalid (stderr has per-index errors).

Self-contained — only depends on pydantic. The SimpleVulnInfo schema and
VulnCategoryId enum are hardcoded here to keep this script runnable in the
target workspace without requiring vuln-spec to be installed there.

Synced with vuln_spec.VulnCategoryId by the companion test
test_validate_vulns_schema.py — when adding/removing categories, update
VALID_CATEGORY_IDS below and ensure the test still passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError


VALID_CATEGORY_IDS: frozenset[str] = frozenset({
    "business-logic-flaw",
    "code-injection",
    "command-injection",
    "cors-misconfiguration",
    "csrf",
    "dos",
    "el-injection",
    "http-response-splitting",
    "idor",
    "incorrect-authentication",
    "incorrect-authorization",
    "incorrect-signature-verification",
    "information-disclosure",
    "insecure-archive-extract",
    "insecure-crypto-configuration",
    "insecure-database-connection",
    "insecure-deserialization",
    "insecure-file-delete",
    "insecure-file-read",
    "insecure-file-upload",
    "insecure-file-write",
    "insecure-random",
    "jndi-injection",
    "ldap-injection",
    "nosql-injection",
    "open-redirection",
    "path-traversal",
    "prompt-injection",
    "sql-injection",
    "ssrf",
    "ssti",
    "static-key-leak",
    "weak-credentials",
    "xpath-injection",
    "xslt-injection",
    "xss",
    "xxe-injection",
})

VALID_MECHANISMS: frozenset[str] = frozenset({
    "authentication", "authorization", "session-management",
    "cors", "csrf-protection", "cryptography", "transport-security",
})

VALID_ROOT_CAUSE_KINDS: frozenset[str] = frozenset({
    "injection", "missing-control", "misconfiguration", "logic-flaw",
})

VALID_CAPABILITIES: frozenset[str] = frozenset({
    "code-eval", "shell-exec", "process-spawn", "expression-eval", "xpath-eval",
    "binary-deserialize", "string-deserialize", "xml-parse", "template-render",
    "sql-query", "nosql-query", "file-read", "file-write", "file-rename",
    "file-delete", "archive-extract", "url-access", "jndi-lookup", "url-redirect",
    "xslt-transform", "ldap-query", "llm-invoke",
})
VALID_SCENARIOS: frozenset[str] = frozenset({
    "login", "register", "password-reset", "profile-update", "payment",
    "file-upload", "crud", "data-persistence", "response-rendering",
    "security-random-generation", "scheduled-task", "configuration-management",
    "file-download", "outbound-request", "search",
})

# A data_flow node must land on a real executable statement. These prefixes mark a
# line that carries no taint and breaks source/sink method extraction: a comment /
# javadoc, or an import/package/using line (outside any method body). Checked with
# pure stdlib (read the line) so the validator stays self-contained.
_COMMENT_PREFIXES = ("//", "/*", "*/", "*", "#", "<!--")
_NON_STATEMENT_PREFIXES = ("import ", "package ", "from ", "using ", "#include")


def _data_flow_line_problem(file_path: str, line: int) -> Optional[str]:
    """Return a reason if `file_path:line` can't be a taint-flow statement (blank /
    comment / import / past end-of-file), else None. Skips silently (returns None)
    when the file can't be read — a path quirk must not block a valid finding."""
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    if line > len(lines):
        return f"line {line} is past end of file ({file_path} has {len(lines)} lines)"
    stripped = lines[line - 1].strip()
    if not stripped:
        return "lands on a blank line"
    if stripped.startswith(_COMMENT_PREFIXES):
        return "lands on a comment / javadoc line"
    if stripped.startswith(_NON_STATEMENT_PREFIXES):
        return "lands on an import / package line (outside any method body)"
    return None


class CodeLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str
    line: Optional[int] = Field(default=None, ge=1)


class SimpleExploitStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    todo: str


class SimpleVulnInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: str
    description: str
    exploit_steps: list[SimpleExploitStep] = Field(default_factory=list)
    data_flow: list[CodeLine] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)  # SensitiveCapability values (the sink reached)
    scenarios: list[str] = Field(default_factory=list)     # SensitiveScenario values (the endpoint's business flow)
    endpoint: str = ""
    # Category-specific target fields (optional); keep in sync with SimpleVulnInfo in llm_auditor/tasks/audit_endpoints.py.
    static_key: str = ""           # static-key-leak: the leaked key's literal value
    static_key_type: str = ""      # static-key-leak: what the key is for
    resource_name: str = ""        # idor: the resource type the endpoint exposes
    resource_operation: str = ""   # idor: the operation on the resource
    scope_kind: str = ""            # "" | endpoint-set | application
    scope_endpoints: list[str] = Field(default_factory=list)
    scope_mechanisms: list[str] = Field(default_factory=list)
    root_cause_kind: str = ""       # RootCauseKind value or ""
    root_cause_file: str = ""
    root_cause_line: Optional[int] = Field(default=None, ge=1)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <path-to-json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: cannot read {path}: {e}", file=sys.stderr)
        return 2

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: file is not valid JSON: {e}", file=sys.stderr)
        return 2

    if not isinstance(data, list):
        print(
            f"ERROR: top-level must be a JSON array; got {type(data).__name__}. "
            "Even 0 vulns must be written as `[]`.",
            file=sys.stderr,
        )
        return 1

    errors: list[tuple[int, str]] = []
    for i, item in enumerate(data):
        try:
            vuln = SimpleVulnInfo.model_validate(item)
        except ValidationError as e:
            errors.append((i, str(e).replace("\n", "; ")))
            continue
        if vuln.category_id not in VALID_CATEGORY_IDS:
            errors.append((
                i,
                f"category_id {vuln.category_id!r} is not a valid VulnCategoryId. "
                f"Valid values: {', '.join(sorted(VALID_CATEGORY_IDS))}",
            ))
        for mech in vuln.scope_mechanisms:
            if mech not in VALID_MECHANISMS:
                errors.append((
                    i,
                    f"scope_mechanisms {mech!r} invalid. "
                    f"Valid: {', '.join(sorted(VALID_MECHANISMS))}",
                ))
        if vuln.root_cause_kind and vuln.root_cause_kind not in VALID_ROOT_CAUSE_KINDS:
            errors.append((
                i,
                f"root_cause_kind {vuln.root_cause_kind!r} invalid. "
                f"Valid: {', '.join(sorted(VALID_ROOT_CAUSE_KINDS))}",
            ))
        for cap in vuln.capabilities:
            if cap not in VALID_CAPABILITIES:
                errors.append((i, f"capabilities {cap!r} invalid. Valid: {', '.join(sorted(VALID_CAPABILITIES))}"))
        for scn in vuln.scenarios:
            if scn not in VALID_SCENARIOS:
                errors.append((i, f"scenarios {scn!r} invalid. Valid: {', '.join(sorted(VALID_SCENARIOS))}"))
        if vuln.scope_kind and vuln.scope_kind not in {"endpoint-set", "application"}:
            errors.append((
                i,
                f"scope_kind {vuln.scope_kind!r} invalid. Valid: endpoint-set, application",
            ))
        # data_flow precision: every node must point at a real executable statement.
        # The host extracts the source/sink method from the first and last node, so a
        # node on a comment / blank / import silently empties those snippets. Repoint
        # it onto the real traced statement (do NOT drop data_flow to dodge this).
        for j, node in enumerate(vuln.data_flow):
            if node.line is None:
                continue
            problem = _data_flow_line_problem(node.file_path, node.line)
            if problem:
                errors.append((
                    i,
                    f"data_flow[{j}] ({node.file_path}:{node.line}) {problem}. "
                    "Point it at the exact executable statement you traced (the input "
                    "read / assignment / sink call) inside the method body.",
                ))
        # Every finding must locate itself (an HTTP-endpoint target, leaked static key, scope, or root-cause file) or it can't be scored; a target-less framework/config finding must promote its sink into root_cause_file (+root_cause_line/kind).
        if not (vuln.endpoint or vuln.static_key or vuln.scope_kind or vuln.root_cause_file):
            errors.append((
                i,
                "finding has no locator: it sets no endpoint, no static_key, no "
                "scope_kind, and no root_cause_file, so it locates itself nowhere "
                "and cannot be scored. Fill `endpoint` (HTTP-endpoint finding), "
                "`static_key` (leaked key), `root_cause_file`+`root_cause_line`"
                "+`root_cause_kind` (a framework/config defect at a specific line, "
                "e.g. a JWT/crypto/deserialize sink), or `scope_kind` (a "
                "cross-cutting absence with no single line).",
            ))

    if errors:
        for i, msg in errors:
            print(f"ERROR: item {i} (0-based): {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
