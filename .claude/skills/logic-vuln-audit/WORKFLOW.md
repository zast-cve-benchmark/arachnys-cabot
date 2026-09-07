# Workflow Orchestration

Agent coordination protocol and phase execution rules for the 9-agent team.

---

## Phase Pipeline

```
Phase 0:  INIT ──────────── Leader ──────────────── _session.json
    │
Phase 1-3: ANALYSIS ─────── Batch 1 (≤3 agents) ── per-module JSONs
    │                        wait...
    │                       Batch 2 (≤2 agents) ── per-module JSONs
    │
Phase 4:  SYNTHESIS ──────── Synthesizer ─────────── merged_vulnerabilities.json
    │
Phase 5a: CHAIN ANALYSIS ── Chain Agent ──────────── exploit_chains.json + chain_pocs/
    │
Phase 5b: REPORT ─────────── Python Scripts ──────── _section*.md
                              Chain Agent (concat) ── FINAL_LOGIC_REPORT.md
```

---

## Phase 0: INIT (Leader Agent)

**Agent**: Leader
**Reads**: @agents/LEADER.md, @reference/LANGUAGE_PROFILES.md, project source code
**Writes**: `{PROJECT}/logic_vuln_audit/_session.json`

### Steps

1. **Parse arguments**: Extract project path and `--lang` flag from `$ARGUMENTS`
   - Default project path: current working directory
   - Default lang: `en`

2. **Identify tech stack**:
   - Read dependency files (`pom.xml`, `package.json`, `go.mod`, `requirements.txt`, `composer.json`)
   - Match against `reference/LANGUAGE_PROFILES.md` profiles
   - Detect language, web frameworks, ORM, auth libraries

3. **Discover business functions**:
   - Scan routes, controllers, and endpoints using language-specific keywords
   - For each of the 5 functions (login, register, password_reset, profile_update, payment):
     - Search for matching route patterns and controller methods
     - Mark as "discovered" if confidence ≥ 0.7
   - Record discovered functions in `_session.json`

4. **Plan batch schedule**:
   ```
   IF discovered_count ≤ 3:
       batch_plan = [{ batch: 1, agents: all_discovered }]
   ELSE:
       batch_plan = [
           { batch: 1, agents: first_3 },
           { batch: 2, agents: remaining }
       ]
   ```

5. **Create output directory**: `{PROJECT}/logic_vuln_audit/`

6. **Write `_session.json`**

### _session.json Schema

```json
{
  "project_name": "string",
  "project_path": "string (absolute path)",
  "language": "string (java|php|python|golang|nodejs)",
  "frameworks": {
    "web": ["string"],
    "orm": ["string"],
    "auth": ["string"],
    "other": ["string"]
  },
  "output_lang": "string (en|zh|ja)",
  "started_at": "string (ISO8601)",
  "discovered_functions": ["string (login|register|password_reset|profile_update|payment)"],
  "batch_plan": [
    {
      "batch": "number",
      "agents": ["string"]
    }
  ]
}
```

---

## Phase 1-3: BUSINESS ANALYSIS (5 Business Agents)

**Agents**: Login, Register, Password Reset, Profile Update, Payment
**Dispatched by**: Leader, in batches per `batch_plan`
**Each agent reads**: @agents/BUSINESS_ANALYZER.md + its module files

### Dispatch Protocol

```
FOR each batch in batch_plan:
    Launch all agents in batch using Agent tool (parallel, background)
    Wait for all agents in batch to complete
    Verify each agent produced expected JSON outputs
    IF any agent failed:
        Log failure, continue with remaining agents
    Proceed to next batch
```

### Per-Agent Internal Pipeline (Serial)

Each business agent executes 3 steps internally, in strict order:

```
Step 1: Business Analysis
    Read: modules/{func}/step1_analysis.md
    Read: project source code (routes, controllers, models, configs)
    Write: {func}/business_logic.json
    Validate: JSON is well-formed, workflows[] is non-empty

Step 2: SINK Detection
    Read: modules/{func}/step2_sinks.md
    Read: {func}/business_logic.json (from Step 1)
    [Payment only]: Read modules/payment/payment_sinks_library.md
    Write: {func}/vulnerability_analysis.json

    🔴 MANDATORY VALIDATION (before proceeding to Step 3):
    Run: python3 {SKILL_DIR}/scripts/validate_vuln_json.py {func}/vulnerability_analysis.json
    IF validation fails:
        Fix ALL errors in the JSON
        Re-run validation until it passes
        Do NOT proceed to Step 3 until validation passes

Step 3: PoC Generation
    Read: reference/POC_TEMPLATES.md
    Read: modules/{func}/step3_poc.md
    Read: {func}/vulnerability_analysis.json (from Step 2)
    NOTE: Do NOT pre-create the pocs/ directory. Write files directly — the directory is auto-created.
    FOR each vulnerability with severity ≥ High:
        Write: {func}/pocs/poc_{ID}.json
        Write: {func}/pocs/poc_{ID}.py
    IF vulnerabilities with severity < High exist:
        Generate PoC only if exploitable
```

### Payment Special Flow

Payment agent has an additional sub-flow in Step 1:

```
Step 1a: Scenario Identification
    Scan codebase for 12 predefined payment scenario patterns
    Record identified scenarios with confidence scores

Step 1b: Per-Scenario Business Analysis
    For each identified scenario:
        Analyze payment workflow
        Extract business logic and data flow

Step 2: SINK Detection
    Read payment_sinks_library.md
    Match identified scenarios → scenario-specific SINKs
    Apply universal SINKs to all scenarios
    Analyze each matched SINK against code
```

---

## Phase 4: SYNTHESIS (Synthesizer Agent)

**Agent**: Synthesizer
**Reads**: @agents/SYNTHESIZER.md, all `*/vulnerability_analysis.json`
**Writes**: `merged_vulnerabilities.json`

### Steps

1. **Collect**: Read all `vulnerability_analysis.json` from each module directory
2. **Merge**: Combine into a single vulnerability list
3. **Deduplicate**: Identify and merge duplicate findings (same root cause across modules)
4. **Unify IDs**: Assign sequential `VULN-{SEQ:03d}` IDs, preserving original module IDs
5. **Normalize severity**: Apply consistent severity ratings across all modules
6. **Statistics**: Calculate totals by severity, by module, dedup count
7. **Write**: `merged_vulnerabilities.json`

### Deduplication Rules

```
Two vulnerabilities are considered duplicates IF:
  - Same file_path AND same line_number (within ±5 lines) AND same vulnerability_type
  - OR same function_name AND same vulnerability_type AND same root_cause pattern

When merging duplicates:
  - Keep the one with higher severity
  - Preserve both original IDs in merged record
  - Note: cross-module duplicates are rare but possible
    (e.g., shared auth middleware used by login and password_reset)
```

---

## Phase 5a: CHAIN ANALYSIS (Chain Agent)

**Agent**: Chain & Reporter (Part 1)
**Reads**: @agents/CHAIN_REPORTER.md, @reference/CHAIN_PATTERNS.md
**Reads**: `merged_vulnerabilities.json`, all `poc_*.json`
**Writes**: `exploit_chains.json`, `chain_pocs/poc_CHAIN_*.py`

### Chain Analysis Steps

1. **Load patterns**: Read `reference/CHAIN_PATTERNS.md` for known cross-function chains
2. **Scan combinations**: For each pair/triple of vulnerabilities from different modules:
   - Check if they form a viable attack chain
   - Evaluate: prerequisites, complexity, impact amplification
3. **Score chains**: Apply scoring matrix (see CHAIN_PATTERNS.md)
4. **Generate chain PoCs**: For each viable chain, produce combined Python PoC
5. **Write**: `exploit_chains.json` + `chain_pocs/`

---

## Phase 5b: REPORT GENERATION (Script-Based + Template-Enforced)

**Why scripts?**: A single agent writing the full report for 20+ vulnerabilities will exceed max_tokens. ALL six sections are pre-generated by Python scripts. The agent only runs scripts and concatenates the output files.

**Reads**: @agents/CHAIN_REPORTER.md
**Writes**: `FINAL_LOGIC_REPORT.md`

### 🔴 CRITICAL: MANDATORY SCRIPT EXECUTION — NO EXCEPTIONS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⛔ HARD REQUIREMENT: You MUST run the Python scripts to generate reports. │
│                                                                             │
│  ❌ FORBIDDEN: Writing ANY report section content from scratch.             │
│  ❌ FORBIDDEN: Generating markdown tables, vulnerability details manually.  │
│  ❌ FORBIDDEN: Bypassing scripts "to save time" or "because they failed".   │
│                                                                             │
│  ✅ REQUIRED: Run gen_section3.py, gen_sections12.py, gen_sections456.py   │
│  ✅ REQUIRED: If scripts fail, FIX THE JSON DATA and re-run scripts.        │
│  ✅ REQUIRED: Concatenate _section*.md files verbatim.                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pre-Flight Validation**: Before generating any report content, verify:
1. `merged_vulnerabilities.json` exists and is valid JSON
2. `exploit_chains.json` exists and is valid JSON
3. All three Python scripts are accessible at `{SKILL_DIR}/scripts/`

**IF YOU CANNOT RUN SCRIPTS**: Stop and inform the user. Do NOT manually write the report.

### Report Generation Steps

**Step 1**: Run 3 Python scripts to generate all sections.

```bash
# Section 3: Vulnerability Details (largest section)
python3 {SKILL_DIR}/scripts/gen_section3.py {output_dir}
# → {output_dir}/_section3.md

# Sections 1-2: Audit Info + Executive Summary
python3 {SKILL_DIR}/scripts/gen_sections12.py {output_dir}
# → {output_dir}/_section1.md, {output_dir}/_section2.md

# Sections 4-6: Chains + Remediation + Appendix
python3 {SKILL_DIR}/scripts/gen_sections456.py {output_dir}
# → {output_dir}/_section4.md, {output_dir}/_section5.md, {output_dir}/_section6.md
```

If any script fails, check the error output and fix the underlying JSON data issue before proceeding.

**Step 2**: Agent concatenates all section files into `FINAL_LOGIC_REPORT.md`.

```
Read and concatenate in order:
1. _section1.md  (report title + audit info)
2. _section2.md  (executive summary)
3. _section3.md  (vulnerability details)
4. _section4.md  (exploit chain analysis)
5. _section5.md  (remediation priority matrix)
6. _section6.md  (appendix)
```

**CRITICAL**: Do NOT generate any section content from scratch. All sections are pre-generated by scripts. Insert content verbatim.

**Step 2.5**: Verify script execution (MANDATORY before proceeding).

```
VALIDATION CHECKPOINT:
1. Count the number of _section*.md files in {output_dir}
   EXPECTED: 6 files (_section1.md through _section6.md)
   IF < 6 files exist: STOP. Scripts did not complete. Re-run failed scripts.

2. Check that _section3.md contains the marker comment:
   <!-- Generated by gen_section3.py -->
   IF marker is missing: STOP. The file was not generated by the script.

3. Verify _section3.md contains proper SOURCE sections for each vulnerability:
   Each VULN-XXX entry must have:
   - "**SOURCE**" header
   - File path and line number table
   - Code snippet in fenced code block
   IF any vulnerability is missing SOURCE: Scripts used incomplete JSON data.
```

**Step 3**: Validate the final report.

```
Validation checklist:
- [ ] All VULN-XXX IDs from merged_vulnerabilities.json appear in Section 3
- [ ] All CHAIN-XXX IDs from exploit_chains.json appear in Section 4
- [ ] Every vulnerability has ALL mandatory fields (CWE, CVSS Vector, SINK, SOURCE, etc.)
- [ ] Report is valid markdown (no broken tables or unclosed code blocks)
- [ ] No placeholder text ({value}, TODO, ...)
```

**Step 4**: Clean up temporary files.

```
Delete: {output_dir}/_section1.md through _section6.md
```

### Mandatory Fields (enforced by gen_section3.py)

Every vulnerability in Section 3 includes these fields:

| Field | Source JSON Field |
|-------|------------------|
| ID | `unified_id` |
| Type | `vulnerability_type` |
| CWE | `cwe_id` |
| Severity | `severity` |
| CVSS 4.0 Score | `cvss_score` |
| CVSS 4.0 Vector | `cvss_vector` |
| Description | `description` |
| SINK (file + line + code) | `sink.*` |
| SOURCE (file + line + code) | `source.*` |
| Call Stack | `data_flow.flow_steps[]` |
| Root Cause | `root_cause` |
| Exploit Conditions | `exploit_conditions[]` |
| Exploitation Steps | `exploit_steps[]` |
| PoC Path | `poc_file` |
| Fix | `recommendation` |

**If validation fails, FIX the issue before finalizing.**

---

## Error Handling

### Agent Failure Recovery

```
IF a business agent fails (no output JSON produced):
    Leader logs the failure in _session.json
    Other agents continue normally
    Synthesizer skips the failed module
    Final report notes the incomplete analysis

IF Synthesizer fails:
    Chain & Reporter reads individual vulnerability_analysis.json directly
    Deduplication is skipped

IF Chain & Reporter fails at chain analysis (Phase 5a):
    Report generation (Phase 5b) proceeds without chains
    exploit_chains.json is empty: {"chain_summary": {"total_chains": 0}, "chains": []}

IF Report generation fails (Phase 5b):
    Individual module results + PoCs are still available
    User can manually review per-module vulnerability_analysis.json
    If gen_section3.py succeeded, _section3.md contains the vulnerability details
```

### Validation Gates

Each JSON output is validated before the next phase reads it:

| Output | Validation |
|--------|-----------|
| `_session.json` | `language` is set, `discovered_functions` is non-empty |
| `business_logic.json` | `workflows[]` is non-empty |
| `vulnerability_analysis.json` | **STRICT** — see detailed validation below |
| `poc_*.json` | `vuln_id` matches a known vulnerability |
| `merged_vulnerabilities.json` | `vulnerabilities[]` exists, `merge_summary` populated |
| `exploit_chains.json` | Valid JSON, `chains` key exists |

### 🔴 MANDATORY: vulnerability_analysis.json Field Validation

**After writing `vulnerability_analysis.json`, the Business Agent MUST validate every vulnerability entry against this checklist:**

```
FOR each vulnerability in vulnerabilities[]:
    ASSERT vulnerability_id exists AND matches pattern {PREFIX}_\d{3}
    ASSERT vulnerability_type exists AND is non-empty string
    ASSERT cwe_id exists AND matches pattern CWE-\d+
    ASSERT severity exists AND is one of: Critical, High, Medium, Low
    ASSERT cvss_score exists AND is a number (not string) between 0.0-10.0
    ASSERT cvss_vector exists AND starts with "CVSS:4.0/"
    ASSERT description exists AND length is 80-120 characters
    ASSERT recommendation exists AND length is 80-120 characters

    ASSERT sink is a dict with:
        - file_path (string, non-empty)
        - line_number (number)
        - function_name (string)
        - code_snippet (string, 8-15 lines)

    ASSERT source is a dict with:
        - file_path (string, non-empty)
        - line_number (number)
        - code_snippet (string, 8-15 lines)

    ASSERT data_flow is a dict with:
        - flow_steps[] (array with ≥2 elements)
        - Each step has: step, file_path, function_name, line_number, description

    ASSERT exploit_conditions is an array (of detailed objects OR legacy strings)
    ASSERT exploit_steps is an array of step objects

IF ANY assertion fails:
    FIX the vulnerability entry before proceeding
    Do NOT proceed to Step 3 until all validations pass
```

**Common Field Name Errors to Avoid:**

| ❌ WRONG | ✅ CORRECT |
|----------|-----------|
| `id` | `vulnerability_id` |
| `name`, `title` | `vulnerability_type` |
| `remediation`, `fix` | `recommendation` |
| `cwe` | `cwe_id` |
| `attack_scenario` (string) | `exploit_conditions` (array) |
| `exploitation` (string) | `exploit_steps` (array of objects) |
| sink as string | `sink` as dict with `file_path`, `line_number`, `code_snippet` |
| source omitted | `source` as dict (REQUIRED) |
| data_flow omitted | `data_flow` with `flow_steps[]` (REQUIRED, ≥2 steps) |

---

## Context Budget Management

| Phase | Agent | Max Files Loaded | Estimated Tokens |
|-------|-------|-----------------|-----------------|
| 0 | Leader | SKILL.md + WORKFLOW.md + LEADER.md + LANGUAGE_PROFILES.md | ~10K |
| 1-3 | Business | BUSINESS_ANALYZER.md + step1/2/3.md + (payment_sinks_library.md) | ~8-12K |
| 4 | Synthesizer | SYNTHESIZER.md + all vuln_analysis.json | ~8K |
| 5a | Chain Agent | CHAIN_REPORTER.md + CHAIN_PATTERNS.md + merged JSON | ~10K |
| 5b | Report Agent | CHAIN_REPORTER.md + 6 × _section*.md (read only) | ~3K (agent generates ~0.5K tokens) |

**Max_token mitigation**: ALL 6 report sections are pre-generated by Python scripts (`gen_section3.py`, `gen_sections12.py`, `gen_sections456.py`). The agent only reads and concatenates the output files — it generates zero section content. This completely eliminates max_token overflow risk even for extreme scenarios (50+ vulnerabilities, 15+ chains).
