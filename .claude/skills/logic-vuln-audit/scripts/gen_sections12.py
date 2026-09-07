#!/usr/bin/env python3
"""
Sections 1, 2 Generator Script

Reads _session.json, merged_vulnerabilities.json, and exploit_chains.json
to produce Section 1 (Audit Information) and Section 2 (Executive Summary).

Usage:
    python3 gen_sections12.py <output_dir> [--lang zh|en|ja]
"""

import json
import os
import sys

MODULES = ["login", "register", "password_reset", "profile_update", "payment"]

SEVERITY_ICONS = {
    "Critical": "🔴 Critical",
    "High": "🟠 High",
    "Medium": "🟡 Medium",
    "Low": "🟢 Low",
}

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

MODULE_DISPLAY = {
    "login": "Login",
    "register": "Register",
    "password_reset": "Password Reset",
    "profile_update": "Profile Update",
    "payment": "Payment",
}

REPORT_TITLES = {
    "en": "# Business Logic Vulnerability Audit Report",
    "zh": "# 业务逻辑漏洞审计报告",
    "ja": "# ビジネスロジック脆弱性監査レポート",
}


# ─── Utilities ───────────────────────────────────────────────────────────────

def load_json(path):
    """Load a JSON file, return None on failure."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {path}: {e}")
        return None


def detect_output_lang(output_dir):
    """Read output_lang from _session.json, default 'en'."""
    session = load_json(os.path.join(output_dir, "_session.json"))
    if session:
        return session.get("output_lang", "en")
    return "en"


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ─── Section 1: Audit Information ────────────────────────────────────────────

def generate_section1(session, lang):
    """Generate Section 1 (Audit Information)."""
    lines = []

    if lang == "zh":
        lines.append("## 1. 审计信息")
    elif lang == "ja":
        lines.append("## 1. 監査情報")
    else:
        lines.append("## 1. Audit Information")
    lines.append("")

    project_name = session.get("project_name", "Unknown") if session else "Unknown"
    project_path = session.get("project_path", "N/A") if session else "N/A"
    language = session.get("language", "N/A") if session else "N/A"
    frameworks = session.get("frameworks", {}) if session else {}
    started_at = session.get("started_at", "N/A") if session else "N/A"
    discovered = session.get("discovered_functions", []) if session else []

    fw_parts = []
    for key in ["web", "orm", "auth", "other"]:
        items = frameworks.get(key, [])
        if items:
            fw_parts.extend(items)
    fw_str = ", ".join(fw_parts) if fw_parts else "N/A"
    scope_str = ", ".join(discovered) if discovered else "N/A"

    if lang == "zh":
        lines.append("| 项目 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| 项目名称 | {project_name} |")
        lines.append(f"| 项目路径 | {project_path} |")
        lines.append(f"| 语言 | {language} |")
        lines.append(f"| 框架 | {fw_str} |")
        lines.append(f"| 审计日期 | {started_at} |")
        lines.append(f"| 审计范围 | {scope_str} |")
        lines.append("| 方法论 | 业务逻辑功能源代码分析 |")
    elif lang == "ja":
        lines.append("| 項目 | 値 |")
        lines.append("|---|---|")
        lines.append(f"| プロジェクト | {project_name} |")
        lines.append(f"| パス | {project_path} |")
        lines.append(f"| 言語 | {language} |")
        lines.append(f"| フレームワーク | {fw_str} |")
        lines.append(f"| 監査日 | {started_at} |")
        lines.append(f"| 対象範囲 | {scope_str} |")
        lines.append("| 方法論 | ビジネスロジック機能のソースコード分析 |")
    else:
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Project | {project_name} |")
        lines.append(f"| Path | {project_path} |")
        lines.append(f"| Language | {language} |")
        lines.append(f"| Frameworks | {fw_str} |")
        lines.append(f"| Audit Date | {started_at} |")
        lines.append(f"| Scope | {scope_str} |")
        lines.append("| Methodology | Source code analysis of business logic functions |")

    lines.append("")
    return "\n".join(lines)


# ─── Section 2: Executive Summary ────────────────────────────────────────────

def generate_section2(session, merged_data, chains_data, lang):
    """Generate Section 2 (Executive Summary)."""
    lines = []

    if lang == "zh":
        lines.append("## 2. 执行摘要")
    elif lang == "ja":
        lines.append("## 2. エグゼクティブサマリー")
    else:
        lines.append("## 2. Executive Summary")
    lines.append("")

    summary = merged_data.get("merge_summary", {}) if merged_data else {}
    vulns = merged_data.get("vulnerabilities", []) if merged_data else []
    by_severity = summary.get("by_severity", {"Critical": 0, "High": 0, "Medium": 0, "Low": 0})
    by_module_severity = summary.get("by_module_severity", {})
    total = summary.get("total_vulnerabilities", 0)
    chains = chains_data.get("chains", []) if chains_data else []

    # ── Risk Overview ──
    if lang == "zh":
        lines.append("### 风险概览")
    elif lang == "ja":
        lines.append("### リスク概要")
    else:
        lines.append("### Risk Overview")
    lines.append("")

    if lang == "zh":
        lines.append("| 严重级别 | 数量 | 占比 |")
    elif lang == "ja":
        lines.append("| 深刻度 | 件数 | 割合 |")
    else:
        lines.append("| Severity | Count | Percentage |")
    lines.append("|----------|-------|-----------|")

    for sev in ["Critical", "High", "Medium", "Low"]:
        count = by_severity.get(sev, 0)
        pct = f"{count / total * 100:.0f}%" if total > 0 else "0%"
        icon = SEVERITY_ICONS.get(sev, sev)
        lines.append(f"| {icon} | {count} | {pct} |")
    lines.append(f"| **Total** | **{total}** | **100%** |")
    lines.append("")

    # ── Module Distribution ──
    if lang == "zh":
        lines.append("### 按模块分布")
    elif lang == "ja":
        lines.append("### モジュール別分布")
    else:
        lines.append("### Distribution by Module")
    lines.append("")

    lines.append("| Module | Critical | High | Medium | Low | Total |")
    lines.append("|--------|----------|------|--------|-----|-------|")

    modules_analyzed = summary.get("modules_analyzed", [])
    for module in MODULES:
        if module not in modules_analyzed:
            continue
        ms = by_module_severity.get(module, {})
        c = ms.get("Critical", 0)
        h = ms.get("High", 0)
        m = ms.get("Medium", 0)
        l = ms.get("Low", 0)
        t = c + h + m + l
        display = MODULE_DISPLAY.get(module, module)
        lines.append(f"| {display} | {c} | {h} | {m} | {l} | {t} |")
    lines.append("")

    # ── Top 3 Most Critical ──
    if lang == "zh":
        lines.append("### 最高危漏洞 Top 3")
    elif lang == "ja":
        lines.append("### 最重要な脆弱性 Top 3")
    else:
        lines.append("### Top 3 Most Critical Findings")
    lines.append("")

    # Sort by severity then CVSS descending
    sorted_vulns = sorted(vulns, key=lambda v: (
        SEVERITY_ORDER.get(v.get("severity", "Low"), 99),
        -safe_float(v.get("cvss_score", 0))
    ))

    for i, v in enumerate(sorted_vulns[:3], 1):
        uid = v.get("unified_id", "")
        vtype = v.get("vulnerability_type", "")
        module = v.get("module", "")
        lines.append(f"{i}. **{uid}**: {vtype} — {module}")
    lines.append("")

    # ── Highest Risk Chain ──
    if chains:
        if lang == "zh":
            lines.append("### 最高风险攻击链")
        elif lang == "ja":
            lines.append("### 最もリスクの高いエクスプロイトチェーン")
        else:
            lines.append("### Highest Risk Exploit Chain")
        lines.append("")

        top_chain = max(chains, key=lambda c: c.get("score", 0))
        cid = top_chain.get("chain_id", "")
        cname = top_chain.get("chain_name", "")
        cmods = ", ".join(top_chain.get("modules_involved", []))
        cimpact = top_chain.get("impact", "")

        lines.append(f"- **{cid}**: {cname}")
        lines.append(f"- Modules: {cmods}")
        lines.append(f"- Impact: {cimpact}")
        lines.append("")

    # ── P0 Action Items ──
    if lang == "zh":
        lines.append("### 立即行动项（P0）")
    elif lang == "ja":
        lines.append("### 即時対応項目（P0）")
    else:
        lines.append("### Immediate Action Items (P0)")
    lines.append("")

    critical_vulns = [v for v in vulns if v.get("severity") == "Critical"]
    if critical_vulns:
        for v in critical_vulns:
            uid = v.get("unified_id", "")
            rec = v.get("recommendation", "") or v.get("remediation", "") or ""
            lines.append(f"- [ ] Fix {uid}: {rec}")
    else:
        # If no Critical, list top High vulns
        high_vulns = [v for v in sorted_vulns if v.get("severity") == "High"][:3]
        for v in high_vulns:
            uid = v.get("unified_id", "")
            rec = v.get("recommendation", "") or v.get("remediation", "") or ""
            lines.append(f"- [ ] Fix {uid}: {rec}")
    lines.append("")

    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gen_sections12.py <output_dir> [--lang zh|en|ja]")
        sys.exit(1)

    output_dir = sys.argv[1]

    lang = None
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        if idx + 1 < len(sys.argv):
            lang = sys.argv[idx + 1]

    if not lang:
        lang = detect_output_lang(output_dir)

    print(f"[*] Loading data from {output_dir} (lang={lang})...")

    session = load_json(os.path.join(output_dir, "_session.json"))
    merged_data = load_json(os.path.join(output_dir, "merged_vulnerabilities.json"))
    chains_data = load_json(os.path.join(output_dir, "exploit_chains.json"))

    # Section 1
    print("[*] Generating Section 1 (Audit Information)...")
    s1 = generate_section1(session, lang)

    # Report title with generator marker
    title = REPORT_TITLES.get(lang, REPORT_TITLES["en"])
    s1_content = "<!-- Generated by gen_sections12.py -->\n" + title + "\n\n---\n\n" + s1

    s1_file = os.path.join(output_dir, "_section1.md")
    with open(s1_file, 'w', encoding='utf-8') as f:
        f.write(s1_content)
    print(f"    Written to {s1_file}")

    # Section 2
    print("[*] Generating Section 2 (Executive Summary)...")
    s2 = generate_section2(session, merged_data, chains_data, lang)
    s2_file = os.path.join(output_dir, "_section2.md")
    with open(s2_file, 'w', encoding='utf-8') as f:
        f.write(s2)
    print(f"    Written to {s2_file}")

    print("[+] Sections 1-2 generated successfully.")


if __name__ == "__main__":
    main()
