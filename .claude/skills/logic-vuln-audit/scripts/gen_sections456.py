#!/usr/bin/env python3
"""
Sections 4, 5, 6 Generator Script

Reads exploit_chains.json and merged_vulnerabilities.json to produce
Section 4 (Exploit Chain Analysis), Section 5 (Remediation Priority),
and Section 6 (Appendix) markdown files.

This script prevents max_token overflow by pre-generating these sections
so the Chain & Reporter agent only needs to concatenate files.

Usage:
    python3 gen_sections456.py <output_dir> [--lang zh|en|ja]
"""

import json
import os
import re
import sys

MODULES = ["login", "register", "password_reset", "profile_update", "payment"]

SEVERITY_ICONS = {
    "Critical": "🔴 Critical",
    "High": "🟠 High",
    "Medium": "🟡 Medium",
    "Low": "🟢 Low",
}

PRIORITY_MAP = {
    "Critical": "P0",
    "High": "P1",
    "Medium": "P2",
    "Low": "P3",
}

MODULE_SINK_COUNTS = {
    "login": "~20",
    "register": "13",
    "password_reset": "15",
    "profile_update": "12",
    "payment": "46+",
}

MODULE_DISPLAY_NAMES = {
    "en": {
        "login": "Login",
        "register": "Register",
        "password_reset": "Password Reset",
        "profile_update": "Profile Update",
        "payment": "Payment",
    },
    "zh": {
        "login": "登录模块（login）",
        "register": "注册模块（register）",
        "password_reset": "密码重置模块（password_reset）",
        "profile_update": "个人资料更新模块（profile_update）",
        "payment": "支付模块（payment）",
    },
    "ja": {
        "login": "ログイン（login）",
        "register": "登録（register）",
        "password_reset": "パスワードリセット（password_reset）",
        "profile_update": "プロフィール更新（profile_update）",
        "payment": "決済（payment）",
    },
}

# Bilingual section headers
SECTION_HEADERS = {
    "en": {
        "s4": "## 4. Exploit Chain Analysis",
        "s5": "## 5. Remediation Priority Matrix",
        "s6": "## 6. Appendix",
    },
    "zh": {
        "s4": "## 4. 攻击链分析",
        "s5": "## 5. 修复优先级",
        "s6": "## 6. 附录",
    },
    "ja": {
        "s4": "## 4. エクスプロイトチェーン分析",
        "s5": "## 5. 修正優先度マトリックス",
        "s6": "## 6. 付録",
    },
}

# Score breakdown dimension labels
SCORE_LABELS = {
    "en": {
        "prerequisites": "Prerequisites",
        "complexity": "Complexity",
        "automation": "Automation",
        "reliability": "Reliability",
        "impact_scope": "Impact Scope",
        "detection": "Detection Difficulty",
        "persistence": "Persistence",
        "data_sensitivity": "Data Sensitivity",
    },
    "zh": {
        "prerequisites": "前置条件",
        "complexity": "复杂度",
        "automation": "自动化",
        "reliability": "可靠性",
        "impact_scope": "影响范围",
        "detection": "检测难度",
        "persistence": "持久化",
        "data_sensitivity": "数据敏感性",
    },
    "ja": {
        "prerequisites": "前提条件",
        "complexity": "複雑さ",
        "automation": "自動化",
        "reliability": "信頼性",
        "impact_scope": "影響範囲",
        "detection": "検出難易度",
        "persistence": "永続性",
        "data_sensitivity": "データ機密性",
    },
}

# Priority tier labels
PRIORITY_LABELS = {
    "en": {
        "P0": {"title": "### P0 — Immediate (24 hours)", "scope": "Critical severity vulnerabilities requiring immediate remediation."},
        "P1": {"title": "### P1 — Urgent (1 week)", "scope": "High severity vulnerabilities involved in exploit chains."},
        "P2": {"title": "### P2 — Normal (1 month)", "scope": "Medium severity vulnerabilities with conditional exploitability."},
        "P3": {"title": "### P3 — Low (Next Release)", "scope": "Low severity vulnerabilities with limited impact."},
    },
    "zh": {
        "P0": {"title": "### P0 — 立即修复（24 小时内）", "scope": "Critical 级别漏洞，需立即修复。"},
        "P1": {"title": "### P1 — 紧急修复（1 周内）", "scope": "High 级别漏洞，参与攻击链利用。"},
        "P2": {"title": "### P2 — 常规修复（1 个月内）", "scope": "Medium 级别漏洞，需特定条件才可利用。"},
        "P3": {"title": "### P3 — 低优先级（下个版本）", "scope": "Low 级别漏洞，影响范围有限。"},
    },
    "ja": {
        "P0": {"title": "### P0 — 即時対応（24時間以内）", "scope": "Critical深刻度の脆弱性、即時修正が必要。"},
        "P1": {"title": "### P1 — 緊急対応（1週間以内）", "scope": "High深刻度の脆弱性、エクスプロイトチェーンに関与。"},
        "P2": {"title": "### P2 — 通常対応（1ヶ月以内）", "scope": "Medium深刻度の脆弱性、条件付きで悪用可能。"},
        "P3": {"title": "### P3 — 低優先度（次回リリース）", "scope": "Low深刻度の脆弱性、影響範囲が限定的。"},
    },
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
    """Safely convert to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def format_success_rate(val):
    """Format success_rate to percentage string."""
    if isinstance(val, str):
        return val
    if isinstance(val, (int, float)):
        return f"{val * 100:.0f}%"
    return "N/A"


def get_label(labels_dict, lang, key, fallback=""):
    """Get a localized label with fallback to English."""
    return labels_dict.get(lang, labels_dict.get("en", {})).get(key, fallback)


# ─── Section 4: Exploit Chain Analysis ───────────────────────────────────────

def generate_chain_section(chain, merged_vulns, lang):
    """Generate markdown for a single exploit chain."""
    chain_id = chain.get("chain_id", "CHAIN-???")
    chain_name = chain.get("chain_name", "")
    severity = chain.get("severity", "Medium")
    score = chain.get("score", 0)
    score_breakdown = chain.get("score_breakdown", {})
    modules = chain.get("modules_involved", [])
    vulns_used = chain.get("vulnerabilities_used", [])
    original_ids = chain.get("original_ids_used", [])
    attack_flow = chain.get("attack_flow", [])
    impact = chain.get("impact", "")
    success_rate = chain.get("success_rate", "")
    mitigation = chain.get("mitigation", [])
    poc_file = chain.get("poc_file", "")
    prerequisites = chain.get("prerequisites", [])

    # Compute max score from breakdown or default to 24
    if score_breakdown:
        notes = score_breakdown.get("notes", "")
        dims = {k: v for k, v in score_breakdown.items() if k != "notes" and isinstance(v, (int, float))}
        max_score = len(dims) * 3
    else:
        max_score = 24

    # Build vulns_used display string with original IDs
    vulns_display_parts = []
    for i, vid in enumerate(vulns_used):
        orig = original_ids[i] if i < len(original_ids) else ""
        if orig:
            vulns_display_parts.append(f"{vid} ({orig})")
        else:
            vulns_display_parts.append(vid)
    vulns_display = ", ".join(vulns_display_parts)

    lines = []
    lines.append(f"### {chain_id} — {chain_name}")
    lines.append("")

    # Info table
    if lang == "zh":
        lines.append("| 属性 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| **Chain ID** | {chain_id} |")
        lines.append(f"| **名称** | {chain_name} |")
        lines.append(f"| **严重级别** | {severity} |")
        lines.append(f"| **评分** | {score} / {max_score} |")
        lines.append(f"| **涉及模块** | {', '.join(modules)} |")
        lines.append(f"| **利用漏洞** | {vulns_display} |")
        lines.append(f"| **成功率** | {format_success_rate(success_rate)} |")
        if poc_file:
            lines.append(f"| **PoC 文件** | `{poc_file}` |")
    elif lang == "ja":
        lines.append("| 属性 | 値 |")
        lines.append("|---|---|")
        lines.append(f"| **Chain ID** | {chain_id} |")
        lines.append(f"| **名前** | {chain_name} |")
        lines.append(f"| **深刻度** | {severity} |")
        lines.append(f"| **スコア** | {score} / {max_score} |")
        lines.append(f"| **関連モジュール** | {', '.join(modules)} |")
        lines.append(f"| **利用脆弱性** | {vulns_display} |")
        lines.append(f"| **成功率** | {format_success_rate(success_rate)} |")
        if poc_file:
            lines.append(f"| **PoC ファイル** | `{poc_file}` |")
    else:
        lines.append("| Property | Value |")
        lines.append("|---|---|")
        lines.append(f"| **Chain ID** | {chain_id} |")
        lines.append(f"| **Name** | {chain_name} |")
        lines.append(f"| **Severity** | {severity} |")
        lines.append(f"| **Score** | {score} / {max_score} |")
        lines.append(f"| **Modules Involved** | {', '.join(modules)} |")
        lines.append(f"| **Vulnerabilities Used** | {vulns_display} |")
        lines.append(f"| **Success Rate** | {format_success_rate(success_rate)} |")
        if poc_file:
            lines.append(f"| **PoC File** | `{poc_file}` |")
    lines.append("")

    # Score breakdown table (if present)
    if score_breakdown:
        dims = {k: v for k, v in score_breakdown.items() if k != "notes" and isinstance(v, (int, float))}
        if dims:
            score_labels = SCORE_LABELS.get(lang, SCORE_LABELS["en"])
            if lang == "zh":
                lines.append("**评分细项**")
                lines.append("")
                lines.append("| 维度 | 分数 | 说明 |")
            elif lang == "ja":
                lines.append("**スコア内訳**")
                lines.append("")
                lines.append("| 項目 | スコア | 説明 |")
            else:
                lines.append("**Score Breakdown**")
                lines.append("")
                lines.append("| Dimension | Score | Notes |")
            lines.append("|---|---|---|")

            # Parse notes for per-dimension explanations
            # Notes format: "Key1=N (explanation); Key2=N (explanation); ..."
            # Some explanations contain semicolons, so use regex to match Key=N patterns
            notes_str = score_breakdown.get("notes", "")
            dim_notes = {}
            if notes_str:
                # Match each "Key=N (explanation)" block using lookahead for next key or end
                pattern = r'(\w+)=\d+\s*\(([^)]*(?:\([^)]*\))*[^)]*)\)'
                for m in re.finditer(pattern, notes_str):
                    dim_notes[m.group(1).lower()] = m.group(2).strip()

            # Map notes keys (e.g. "impact", "datasensitivity") to dim_keys
            notes_key_map = {
                "prerequisites": "prerequisites",
                "complexity": "complexity",
                "automation": "automation",
                "reliability": "reliability",
                "impact": "impact_scope",
                "impact_scope": "impact_scope",
                "detection": "detection",
                "persistence": "persistence",
                "datasensitivity": "data_sensitivity",
                "data_sensitivity": "data_sensitivity",
            }
            mapped_notes = {}
            for nk, nv in dim_notes.items():
                mapped_key = notes_key_map.get(nk, nk)
                mapped_notes[mapped_key] = nv

            for dim_key in ["prerequisites", "complexity", "automation", "reliability",
                            "impact_scope", "detection", "persistence", "data_sensitivity"]:
                if dim_key in dims:
                    label = score_labels.get(dim_key, dim_key)
                    val = dims[dim_key]
                    note = mapped_notes.get(dim_key, "")
                    lines.append(f"| {label} | {val} | {note} |")
            lines.append("")

    # Attack flow
    if attack_flow:
        if lang == "zh":
            lines.append("**攻击流程**")
        elif lang == "ja":
            lines.append("**攻撃フロー**")
        else:
            lines.append("**Attack Flow**")
        lines.append("")
        lines.append("```")
        for step in attack_flow:
            step_num = step.get("step", "?")
            vuln = step.get("vulnerability", "")
            action = step.get("action", "")
            input_val = step.get("input", "")
            output_val = step.get("output", "")

            if lang == "zh":
                lines.append(f"步骤 {step_num}  [{vuln}]")
                lines.append(f"  行动：{action}")
                lines.append(f"  输入：{input_val}")
                lines.append(f"  输出：{output_val}")
            elif lang == "ja":
                lines.append(f"ステップ {step_num}  [{vuln}]")
                lines.append(f"  アクション：{action}")
                lines.append(f"  入力：{input_val}")
                lines.append(f"  出力：{output_val}")
            else:
                lines.append(f"Step {step_num}  [{vuln}]")
                lines.append(f"  Action: {action}")
                lines.append(f"  Input:  {input_val}")
                lines.append(f"  Output: {output_val}")

            # Add arrow between steps (not after last)
            if step != attack_flow[-1]:
                lines.append("")
        lines.append("```")
        lines.append("")

    # Combined impact
    if impact:
        if lang == "zh":
            lines.append("**综合影响**")
        elif lang == "ja":
            lines.append("**総合的影響**")
        else:
            lines.append("**Combined Impact**")
        lines.append("")
        lines.append(impact)
        lines.append("")

    # Chain-breaking recommendations
    if mitigation:
        if lang == "zh":
            lines.append("**链条阻断建议**")
            lines.append("")
            lines.append("| 修复措施 | 阻断步骤 | 说明 |")
        elif lang == "ja":
            lines.append("**チェーン阻止策**")
            lines.append("")
            lines.append("| 修正措置 | 阻止ステップ | 説明 |")
        else:
            lines.append("**Chain-Breaking Recommendations**")
            lines.append("")
            lines.append("| Fix | Breaks At | Notes |")
        lines.append("|---|---|---|")

        # Handle both string and list formats for mitigation
        mitigation_list = mitigation if isinstance(mitigation, list) else [mitigation]
        for mit_str in mitigation_list:
            # Extract VULN-ID from mitigation string
            vuln_match = re.search(r'VULN-\d+', mit_str)
            vuln_ref = vuln_match.group(0) if vuln_match else ""
            # Extract step reference
            step_match = re.search(r'(?:step|步骤|ステップ)\s*(\d+)', mit_str, re.IGNORECASE)
            step_ref = step_match.group(0) if step_match else ""
            lines.append(f"| {mit_str} | {step_ref} | |")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def generate_section4(chains_data, merged_data, lang):
    """Generate complete Section 4 (Exploit Chain Analysis)."""
    header = SECTION_HEADERS.get(lang, SECTION_HEADERS["en"])["s4"]
    lines = ["<!-- Generated by gen_sections456.py -->", header, ""]

    chains = chains_data.get("chains", []) if chains_data else []

    if not chains:
        if lang == "zh":
            lines.append("未识别出有效攻击链。")
        elif lang == "ja":
            lines.append("有効なエクスプロイトチェーンは識別されませんでした。")
        else:
            lines.append("No exploit chains were identified.")
        lines.append("")
        return "\n".join(lines)

    # Build a vuln lookup for enriching chain display
    merged_vulns = {}
    if merged_data:
        for v in merged_data.get("vulnerabilities", []):
            merged_vulns[v.get("unified_id", "")] = v

    for chain in chains:
        lines.append(generate_chain_section(chain, merged_vulns, lang))

    return "\n".join(lines)


# ─── Section 5: Remediation Priority Matrix ──────────────────────────────────

def generate_section5(merged_data, lang):
    """Generate complete Section 5 (Remediation Priority Matrix)."""
    header = SECTION_HEADERS.get(lang, SECTION_HEADERS["en"])["s5"]
    lines = [header, ""]

    vulns = merged_data.get("vulnerabilities", []) if merged_data else []

    if not vulns:
        if lang == "zh":
            lines.append("未发现漏洞。")
        elif lang == "ja":
            lines.append("脆弱性は発見されませんでした。")
        else:
            lines.append("No vulnerabilities found.")
        lines.append("")
        return "\n".join(lines)

    # Group by priority tier
    tiers = {"P0": [], "P1": [], "P2": [], "P3": []}
    for v in vulns:
        tier = PRIORITY_MAP.get(v.get("severity", "Low"), "P3")
        tiers[tier].append(v)

    priority_labels = PRIORITY_LABELS.get(lang, PRIORITY_LABELS["en"])

    for tier_name in ["P0", "P1", "P2", "P3"]:
        tier_vulns = tiers[tier_name]
        tier_info = priority_labels[tier_name]

        lines.append(tier_info["title"])
        lines.append("")

        if not tier_vulns:
            if lang == "zh":
                lines.append("（无）")
            elif lang == "ja":
                lines.append("（なし）")
            else:
                lines.append("(None)")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        # Scope description
        lines.append(tier_info["scope"])
        lines.append("")

        # Table header
        if lang == "zh":
            lines.append("| # | Vuln ID | 类型 | 模块 | 修复建议 |")
        elif lang == "ja":
            lines.append("| # | Vuln ID | タイプ | モジュール | 修正推奨 |")
        else:
            lines.append("| # | Vuln ID | Type | Module | Fix Recommendation |")
        lines.append("|---|---|---|---|---|")

        for i, v in enumerate(tier_vulns, 1):
            uid = v.get("unified_id", "")
            orig_id = v.get("original_id", "")
            vuln_type = v.get("vulnerability_type", "")
            module = v.get("module", "")
            rec = v.get("recommendation", "") or v.get("remediation", "") or ""

            vid_display = f"{uid} ({orig_id})" if orig_id and orig_id != uid else uid
            lines.append(f"| {i} | {vid_display} | {vuln_type} | {module} | {rec} |")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ─── Section 6: Appendix ─────────────────────────────────────────────────────

def discover_module_pocs(output_dir):
    """Discover PoC .py files per module. Returns {module: [filename, ...]}."""
    result = {}
    for module in MODULES:
        poc_dir = os.path.join(output_dir, module, "pocs")
        if not os.path.isdir(poc_dir):
            continue
        files = sorted(f for f in os.listdir(poc_dir) if f.endswith(".py"))
        if files:
            result[module] = files
    return result


def discover_chain_pocs(output_dir):
    """Discover chain PoC .py files. Returns [filename, ...]."""
    chain_poc_dir = os.path.join(output_dir, "chain_pocs")
    if not os.path.isdir(chain_poc_dir):
        return []
    return sorted(f for f in os.listdir(chain_poc_dir) if f.endswith(".py"))


def generate_poc_listing(output_dir, merged_data, chains_data, lang):
    """Generate subsection A: PoC File Listing."""
    lines = []

    if lang == "zh":
        lines.append("### A. PoC 文件清单")
        lines.append("")
        lines.append("以下列出本次审计生成的所有概念验证（PoC）文件，按模块分类排列。")
    elif lang == "ja":
        lines.append("### A. PoCファイル一覧")
        lines.append("")
        lines.append("本監査で生成されたすべてのPoCファイルをモジュール別に一覧します。")
    else:
        lines.append("### A. PoC File Listing")
        lines.append("")
        lines.append("All Proof-of-Concept files generated during this audit, organized by module.")
    lines.append("")

    # Build vuln lookup
    vuln_map = {}
    if merged_data:
        for v in merged_data.get("vulnerabilities", []):
            uid = v.get("unified_id", "")
            orig_id = v.get("original_id", "")
            vuln_map[uid] = v
            vuln_map[orig_id] = v

    # Build chain lookup
    chain_map = {}
    if chains_data:
        for c in chains_data.get("chains", []):
            chain_map[c.get("chain_id", "")] = c

    module_pocs = discover_module_pocs(output_dir)
    chain_pocs = discover_chain_pocs(output_dir)
    total_module_pocs = sum(len(files) for files in module_pocs.values())
    total_chain_pocs = len(chain_pocs)

    module_names = MODULE_DISPLAY_NAMES.get(lang, MODULE_DISPLAY_NAMES["en"])

    for module in MODULES:
        if module not in module_pocs:
            continue
        files = module_pocs[module]
        lines.append(f"#### {module_names.get(module, module)}")
        lines.append("")

        if lang == "zh":
            lines.append("| 文件名 | 对应漏洞 ID | 漏洞类型 | 严重级别 |")
        elif lang == "ja":
            lines.append("| ファイル名 | 脆弱性ID | タイプ | 深刻度 |")
        else:
            lines.append("| Filename | Vulnerability ID | Type | Severity |")
        lines.append("|---|---|---|---|")

        for fname in files:
            rel_path = f"{module}/pocs/{fname}"
            # Extract ID from filename: poc_XXX.py → XXX
            poc_id = fname.replace("poc_", "").replace(".py", "")
            v = vuln_map.get(poc_id, {})
            uid = v.get("unified_id", "")
            orig_id = v.get("original_id", poc_id)
            vuln_type = v.get("vulnerability_type", "")
            severity = v.get("severity", "")
            vid_display = f"{uid} ({orig_id})" if uid and uid != orig_id else (uid or orig_id)
            lines.append(f"| `{rel_path}` | {vid_display} | {vuln_type} | {severity} |")

        lines.append("")

    # Chain PoCs
    if chain_pocs:
        if lang == "zh":
            lines.append("#### 攻击链 PoC（chain_pocs）")
            lines.append("")
            lines.append("| 文件名 | 对应攻击链 | 链名称 | 严重级别 |")
        elif lang == "ja":
            lines.append("#### エクスプロイトチェーンPoC（chain_pocs）")
            lines.append("")
            lines.append("| ファイル名 | チェーンID | チェーン名 | 深刻度 |")
        else:
            lines.append("#### Exploit Chain PoCs (chain_pocs)")
            lines.append("")
            lines.append("| Filename | Chain ID | Chain Name | Severity |")
        lines.append("|---|---|---|---|")

        for fname in chain_pocs:
            rel_path = f"chain_pocs/{fname}"
            chain_id = fname.replace("poc_", "").replace(".py", "")
            c = chain_map.get(chain_id, {})
            chain_name = c.get("chain_name", "")
            severity = c.get("severity", "")
            lines.append(f"| `{rel_path}` | {chain_id} | {chain_name} | {severity} |")

        lines.append("")

    # Total count
    total = total_module_pocs + total_chain_pocs
    if lang == "zh":
        lines.append(f"**PoC 文件总计：{total} 个**（单漏洞 PoC {total_module_pocs} 个 + 攻击链 PoC {total_chain_pocs} 个）")
    elif lang == "ja":
        lines.append(f"**PoCファイル合計：{total} 件**（脆弱性PoC {total_module_pocs} 件 + チェーンPoC {total_chain_pocs} 件）")
    else:
        lines.append(f"**Total PoC files: {total}** (Vulnerability PoCs: {total_module_pocs} + Chain PoCs: {total_chain_pocs})")
    lines.append("")

    return "\n".join(lines)


def generate_methodology(session, merged_data, chains_data, lang):
    """Generate subsection B: Methodology with actual statistics."""
    lines = []

    discovered = session.get("discovered_functions", []) if session else []
    language = session.get("language", "unknown") if session else "unknown"
    total_vulns = 0
    by_severity = {}
    if merged_data:
        summary = merged_data.get("merge_summary", {})
        total_vulns = summary.get("total_vulnerabilities", 0)
        by_severity = summary.get("by_severity", {})
    total_chains = 0
    chains_by_sev = {}
    if chains_data:
        chain_summary = chains_data.get("chain_summary", {})
        total_chains = chain_summary.get("total_chains", 0)
        chains_by_sev = chain_summary.get("by_severity", {})

    num_modules = len(discovered)
    sev_breakdown = ", ".join(f"{k} {v}" for k, v in by_severity.items() if v > 0)
    chain_sev_breakdown = ", ".join(f"{k} {v}" for k, v in chains_by_sev.items() if v > 0)

    if lang == "zh":
        lines.append("### B. 审计方法论")
        lines.append("")
        lines.append(f"本次审计采用**三阶段静态代码分析方法**，针对 {language.capitalize()} 源代码中的业务逻辑漏洞进行系统性评估。")
        lines.append("")
        lines.append("**阶段一 — 功能发现（Function Discovery）**")
        lines.append("")
        modules_str = "、".join(discovered) if discovered else "无"
        lines.append(f"对目标代码库进行全局扫描，识别所有与身份认证、账号管理相关的业务功能入口。本次识别出 {num_modules} 个核心功能域：{modules_str}。")
        lines.append("")
        lines.append("**阶段二 — 漏洞挖掘（Vulnerability Auditing）**")
        lines.append("")
        lines.append(f"针对每个功能域，以数据流追踪（Source → Sink 分析）和配置默认值审查为核心方法，系统性识别业务逻辑漏洞。{num_modules} 个模块合计发现 {total_vulns} 个漏洞（{sev_breakdown}）。")
        lines.append("")
        lines.append("**阶段三 — 攻击链构建（Exploit Chain Analysis）**")
        lines.append("")
        lines.append(f"基于第二阶段发现的漏洞，运用跨功能攻击链模式矩阵对漏洞进行组合分析，评估跨模块利用的可行性和危害放大效应。共识别出 {total_chains} 条有效攻击链（{chain_sev_breakdown}）。")
    elif lang == "ja":
        lines.append("### B. 監査方法論")
        lines.append("")
        lines.append(f"本監査は**3段階の静的コード分析手法**を採用し、{language.capitalize()}ソースコードのビジネスロジック脆弱性を体系的に評価しました。")
        lines.append("")
        lines.append("**フェーズ1 — 機能発見**")
        lines.append("")
        modules_str = "、".join(discovered) if discovered else "なし"
        lines.append(f"コードベース全体をスキャンし、{num_modules}個のコア機能ドメインを特定：{modules_str}。")
        lines.append("")
        lines.append("**フェーズ2 — 脆弱性検出**")
        lines.append("")
        lines.append(f"各機能ドメインに対し、データフロー追跡とデフォルト値レビューにより、{total_vulns}件の脆弱性を発見（{sev_breakdown}）。")
        lines.append("")
        lines.append("**フェーズ3 — エクスプロイトチェーン分析**")
        lines.append("")
        lines.append(f"発見された脆弱性を組み合わせ、クロスモジュール攻撃の実現可能性を評価。{total_chains}件のエクスプロイトチェーンを特定（{chain_sev_breakdown}）。")
    else:
        lines.append("### B. Methodology")
        lines.append("")
        lines.append(f"This audit employed a **three-phase static code analysis approach** to systematically assess business logic vulnerabilities in the {language.capitalize()} source code.")
        lines.append("")
        lines.append("**Phase 1 — Function Discovery**")
        lines.append("")
        modules_str = ", ".join(discovered) if discovered else "none"
        lines.append(f"Global scan of the codebase identified {num_modules} core functional domains: {modules_str}.")
        lines.append("")
        lines.append("**Phase 2 — Vulnerability Auditing**")
        lines.append("")
        lines.append(f"Data flow tracing (Source → Sink analysis) and default configuration review identified {total_vulns} vulnerabilities across {num_modules} modules ({sev_breakdown}).")
        lines.append("")
        lines.append("**Phase 3 — Exploit Chain Analysis**")
        lines.append("")
        lines.append(f"Cross-function analysis of discovered vulnerabilities identified {total_chains} exploit chains ({chain_sev_breakdown}).")

    lines.append("")
    return "\n".join(lines)


def generate_references(merged_data, lang):
    """Generate subsection C: References."""
    lines = []

    if lang == "zh":
        lines.append("### C. 参考资料")
    elif lang == "ja":
        lines.append("### C. 参考文献")
    else:
        lines.append("### C. References")
    lines.append("")

    # Static references — always in English identifiers
    lines.append("- **OWASP Testing Guide v4.2 — Business Logic Testing**")
    lines.append("  - OTG-BUSLOGIC-001: Test Business Logic Data Validation")
    lines.append("  - OTG-BUSLOGIC-002: Test Ability to Forge Requests")
    lines.append("  - OTG-BUSLOGIC-003: Test Integrity Checks")
    lines.append("  - OTG-BUSLOGIC-004: Test for Process Timing")
    lines.append("  - OTG-BUSLOGIC-005: Test Number of Times a Function Can be Used Limits")
    lines.append("  - OTG-BUSLOGIC-007: Test Defenses Against Application Mis-use")
    lines.append("")
    lines.append("- **OWASP Top 10 2021**")
    lines.append("  - A01:2021 — Broken Access Control")
    lines.append("  - A02:2021 — Cryptographic Failures")
    lines.append("  - A04:2021 — Insecure Design")
    lines.append("  - A05:2021 — Security Misconfiguration")
    lines.append("  - A07:2021 — Identification and Authentication Failures")
    lines.append("")
    lines.append("- **NIST SP 800-63B — Digital Identity Guidelines: Authentication and Lifecycle Management**")
    lines.append("")

    return "\n".join(lines)


def generate_section6(output_dir, session, merged_data, chains_data, lang):
    """Generate complete Section 6 (Appendix)."""
    header = SECTION_HEADERS.get(lang, SECTION_HEADERS["en"])["s6"]
    lines = [header, ""]

    lines.append(generate_poc_listing(output_dir, merged_data, chains_data, lang))
    lines.append("---")
    lines.append("")
    lines.append(generate_methodology(session, merged_data, chains_data, lang))
    lines.append("---")
    lines.append("")
    lines.append(generate_references(merged_data, lang))

    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gen_sections456.py <output_dir> [--lang zh|en|ja]")
        sys.exit(1)

    output_dir = sys.argv[1]

    # Override lang from CLI if provided
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

    if not merged_data:
        print("[!] Failed to load merged_vulnerabilities.json")
        sys.exit(1)

    # Section 4
    print("[*] Generating Section 4 (Exploit Chain Analysis)...")
    s4 = generate_section4(chains_data, merged_data, lang)
    s4_file = os.path.join(output_dir, "_section4.md")
    with open(s4_file, 'w', encoding='utf-8') as f:
        f.write(s4)
    print(f"    Written to {s4_file}")

    # Section 5
    print("[*] Generating Section 5 (Remediation Priority Matrix)...")
    s5 = generate_section5(merged_data, lang)
    s5_file = os.path.join(output_dir, "_section5.md")
    with open(s5_file, 'w', encoding='utf-8') as f:
        f.write(s5)
    print(f"    Written to {s5_file}")

    # Section 6
    print("[*] Generating Section 6 (Appendix)...")
    s6 = generate_section6(output_dir, session, merged_data, chains_data, lang)
    s6_file = os.path.join(output_dir, "_section6.md")
    with open(s6_file, 'w', encoding='utf-8') as f:
        f.write(s6)
    print(f"    Written to {s6_file}")

    print(f"[+] All sections generated successfully.")


if __name__ == "__main__":
    main()
