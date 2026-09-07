---
name: logic-vuln-skill
description: >
  Business logic vulnerability audit for web applications. Uses a 9-agent team
  to analyze 5 business functions (login, registration, password reset, profile
  update, payment) for logic flaws. Cross-language: Java, PHP, Python, Go, Node.js.
  Outputs merged vulnerability list, exploit chains, executable Python PoCs, and
  a full audit report. Use when: business logic audit, logic vulnerability, logic
  flaw, business logic security, 业务逻辑漏洞, 逻辑漏洞审计, 业务安全审计.
---

# Business Logic Vulnerability Audit Skill v1.0

Automated business logic vulnerability detection for web applications.
Analyzes source code to identify logic flaws in authentication, registration,
password reset, profile management, and payment flows.

## Command Line

```bash
# Audit current directory
/logic-vuln-skill

# Audit specific project
/logic-vuln-skill /path/to/project

# Specify report language
/logic-vuln-skill /path/to/project --lang zh

# Supported --lang values: en (default), zh, ja
```

**Input**: `$ARGUMENTS` — project path and optional flags.

---

## Agent Team (9 Agents)

```
                        ① LEADER (调度)
                            │
          ┌─────────┬───────┼───────┬──────────┐
          ▼         ▼       ▼       ▼          ▼
     ② LOGIN  ③ REGISTER ④ PWD_RESET ⑤ PROFILE ⑥ PAYMENT
          │         │       │       │          │
          └─────────┴───────┼───────┴──────────┘
                            ▼
                    ⑦ SYNTHESIZER (整合)
                            │
                            ▼
                  ⑧ CHAIN & REPORTER (攻击链+报告)
```

| # | Agent | Role | Reads | Writes |
|---|-------|------|-------|--------|
| ① | Leader | Tech stack + function discovery + dispatch | Project source | `_session.json` |
| ② | **Login Agent** | **ALL authentication/authorization** (JWT, tokens, sessions, OAuth, API keys) | Module guides + source | `business_logic.json`, `vulnerability_analysis.json`, `poc_*.json` |
| ③-⑥ | Other Business Agents | Registration, password reset, profile, payment | Module guides + source | `business_logic.json`, `vulnerability_analysis.json`, `poc_*.json` |
| ⑦ | Synthesizer | Merge + deduplicate + unify IDs | All `vulnerability_analysis.json` | `merged_vulnerabilities.json` |
| ⑧ | Chain & Reporter | Exploit chains + final report | Merged vulns + all PoCs | `exploit_chains.json`, `FINAL_LOGIC_REPORT.md` |

> **Note**: The Login Agent now covers ALL authentication mechanisms, not just traditional login forms.
> This includes JWT validation, bearer tokens, API keys, OAuth/OIDC, session management, and auth proxies.

---

## Execution Phases

```
Phase 0   INIT ──────────────────── Leader Agent
               │
Phase 1-3  BUSINESS ANALYSIS ───── 5 Agents (batched parallel, max 3 concurrent)
               │
Phase 4   SYNTHESIS ────────────── Synthesizer Agent
               │
Phase 5a  CHAIN ANALYSIS ────────── Chain Agent
               │
Phase 5b  REPORT GENERATION ─────── Python Scripts + Chain Agent (assembly)
```

> **Orchestration details**: Read @WORKFLOW.md

---

## Module Index

Each business function has its own directory under `modules/`:

| Module | Files | SINK Count |
|--------|-------|------------|
| `modules/login/` | step1, step2, step3 | ~20 SINKs |
| `modules/register/` | step1, step2, step3 | 13 SINKs (SINK-01 ~ SINK-13) |
| `modules/password_reset/` | step1, step2, step3 | 15 SINKs (SINK-1 ~ SINK-15) |
| `modules/profile_update/` | step1, step2, step3 | 12 SINKs (1-12) |
| `modules/payment/` | step1, step2, step3 + `payment_sinks_library.md` | 46+ SINKs (12 scenarios + 6 universal) |

**Per-module file roles**:
- `step1_analysis.md` — Business logic analysis guide (→ `business_logic.json`)
- `step2_sinks.md` — SINK detection rules and checklist (→ `vulnerability_analysis.json`)
- `step3_poc.md` — PoC generation guide (→ `poc_{ID}.json` + `poc_{ID}.py`)

---

## Reference Index

| File | Purpose | When to Load |
|------|---------|-------------|
| `reference/JSON_SCHEMAS.md` | All JSON output schemas (MANDATORY) | Any step writing JSON |
| `reference/POC_TEMPLATES.md` | Python PoC base class + templates | Step 3 |
| `reference/CHAIN_PATTERNS.md` | Cross-function exploit chain patterns | Phase 5a |
| `reference/REPORT_FORMAT.md` | Final report structure + format (MANDATORY) | Phase 5b |
| `reference/LANGUAGE_PROFILES.md` | Language/framework detection profiles | Phase 0 + Step 1 |
| `scripts/gen_section3.py` | Generate Section 3 markdown from JSON | Phase 5b |
| `scripts/gen_sections12.py` | Generate Sections 1-2 markdown | Phase 5b |
| `scripts/gen_sections456.py` | Generate Sections 4-6 markdown | Phase 5b |

---

## Runtime Output Structure

```
{PROJECT_ROOT}/logic_vuln_audit/
├── _session.json                         # Session metadata
├── login/
│   ├── business_logic.json
│   ├── vulnerability_analysis.json
│   └── pocs/
│       ├── poc_LOGIN_001.json
│       └── poc_LOGIN_001.py
├── register/                             # Same structure
├── password_reset/                       # Same structure
├── profile_update/                       # Same structure
├── payment/                              # Same structure (with scenarios)
├── merged_vulnerabilities.json
├── exploit_chains.json
├── chain_pocs/
│   ├── poc_CHAIN_001.json
│   └── poc_CHAIN_001.py
└── FINAL_LOGIC_REPORT.md
```

> Only directories for discovered business functions are created.

---

## Progressive Loading

| Layer | Content | Token Budget |
|-------|---------|-------------|
| Always | This SKILL.md | ~4K |
| Session start | + WORKFLOW.md | +3K |
| Per agent | + agent role file + module step file | +3-4K |
| On demand | + reference file | +2-3K |

**Maximum per-agent context**: ~12K tokens (well within limits).

---

## Supported Languages & Frameworks

| Language | Web Frameworks | ORM | Auth |
|----------|---------------|-----|------|
| Java | Spring Boot, Spring MVC, Struts2 | MyBatis, Hibernate, JPA | Spring Security, Shiro, Sa-Token |
| PHP | Laravel, ThinkPHP, CodeIgniter, Yii2 | Eloquent, ThinkORM | Laravel Auth, JWT |
| Python | Django, Flask, FastAPI | Django ORM, SQLAlchemy | Django Auth, Flask-Login |
| Go | Gin, Echo, Fiber, Beego | GORM, sqlx | JWT, Casbin |
| Node.js | Express, Koa, NestJS, Fastify | Sequelize, TypeORM, Prisma | Passport, JWT |

> Full profiles: `reference/LANGUAGE_PROFILES.md`
> To add a new language, append a new section to that file.

---

## Quick Start

1. Leader reads this SKILL.md + WORKFLOW.md
2. Leader scans project → creates `_session.json`
3. Leader dispatches business agents in batches
4. Each business agent runs 3-step pipeline (business_logic.json → vulnerability_analysis.json → PoCs)
5. Synthesizer merges all findings → `merged_vulnerabilities.json`
6. Chain Agent analyzes exploit chains → `exploit_chains.json`
7. **Python scripts generate report sections** (`gen_section3.py`, `gen_sections12.py`, `gen_sections456.py`)
8. Chain Agent assembles final report from generated sections (concatenation only)
9. Output at `{PROJECT}/logic_vuln_audit/FINAL_LOGIC_REPORT.md`

---

## 🔴 MANDATORY: Script-Based Report Generation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⛔ HARD REQUIREMENT — REPORT GENERATION MUST USE PYTHON SCRIPTS           │
│                                                                             │
│  Phase 5b REQUIRES running these 3 Python scripts:                         │
│                                                                             │
│  1. python3 {SKILL_DIR}/scripts/gen_section3.py {output_dir}               │
│  2. python3 {SKILL_DIR}/scripts/gen_sections12.py {output_dir}             │
│  3. python3 {SKILL_DIR}/scripts/gen_sections456.py {output_dir}            │
│                                                                             │
│  ❌ FORBIDDEN: Manually writing FINAL_LOGIC_REPORT.md content                     │
│  ❌ FORBIDDEN: Generating markdown tables or vulnerability details manually│
│  ❌ FORBIDDEN: Skipping scripts to "save time" or because "they failed"    │
│                                                                             │
│  If scripts fail → FIX THE JSON DATA → Re-run scripts                      │
│  Do NOT bypass scripts by writing report content manually.                 │
│                                                                             │
│  DETECTION: Script-generated reports contain marker comments:               │
│  - <!-- Generated by gen_section3.py -->                                   │
│  - <!-- Generated by gen_sections12.py -->                                 │
│  - <!-- Generated by gen_sections456.py -->                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**CRITICAL**: FINAL_LOGIC_REPORT.md must contain ALL fields defined in REPORT_FORMAT.md. The scripts enforce this automatically — only script-generated reports are compliant.
