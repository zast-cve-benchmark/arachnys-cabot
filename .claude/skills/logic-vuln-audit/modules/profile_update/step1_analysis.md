# Profile Update Business Logic Analysis Guide

## Objective

Perform deep analysis of the **Profile Update** functionality in a web project to understand its original design intent, security control mechanisms, and complete business logic workflow.

## Task Overview

1. Analyze all Profile Update entry points, controllers, and route definitions
2. Understand framework-specific patterns (Java, PHP, Python, Golang, Node.js)
3. Trace global components (filters, interceptors, middleware, decorators, AOP)
4. Map the complete data flow for each modifiable field
5. Record critical code snippets from the business logic workflow
6. Output structured results to `business_logic.json`

---

## Global Components to Investigate (Cross-Language)

| Language | Components to Trace |
|----------|-------------------|
| Java | Filter, Interceptor, AOP, `@Transactional`, config files (`application.yml/properties`) |
| PHP | Middleware, Event Listener, Service Provider, config files (`.env`, `config/`) |
| Python | Middleware, Decorator, Signal, config files (`settings.py`, `config.py`) |
| Golang | Middleware, Interceptor, config files (`yaml/json/toml`) |
| Node.js | Middleware, Hook, Plugin, config files (`config.js`, `.env`) |

---

## High-Risk Fields

The following fields require focused analysis due to their security sensitivity:

- **password** -- credential field, account takeover risk
- **username** -- identity field, uniqueness and history implications
- **phone** -- authentication factor, account recovery vector
- **email** -- authentication factor, account recovery vector
- **2FA/MFA configuration** -- second factor settings, bypass risk
- **Security questions and answers** -- account recovery mechanism
- **API keys / tokens** -- programmatic access credentials
- **OAuth bindings** -- third-party authentication links
- **ID card numbers** (national ID, passport, etc.) -- PII with regulatory implications

---

## Analysis Steps

### Step 1: Identify Entry Points

- Locate all HTTP endpoints that modify user profile data (URL paths, API routes, controller actions)
- Identify the corresponding controller methods or handler functions
- Record supported HTTP methods (PUT, POST, PATCH)
- Note any route-level middleware or guards applied

### Step 2: Trace Execution Flow

Starting from the request entry point, trace in order:

**Pre-Processing:**
- Authentication middleware (how is user identity verified?)
- Authorization checks (is modification permission validated?)
- Parameter filtering / sanitization
- Rate limiting
- CSRF protection

**Core Business Logic:**
- Parameter reception and parsing
- Data validation logic (field-level and business-level)
- Special handling of sensitive fields (e.g., does password change require the old password?)
- Permission checks (can the user only modify their own profile?)
- Database operations (UPDATE statements, ORM methods)

**Post-Processing:**
- Response construction
- Logging and audit trail
- Event triggers (e.g., notification emails, webhooks)

### Step 3: Identify Global Configurations

- Global components affecting this functionality (middleware, interceptors, filters, decorators)
- Configuration file settings (password policies, field mutability rules)
- Existing global validation, authorization, and security check mechanisms
- Permission policy definitions
- ORM / data model field attributes (nullable, unique, default values, fillable/guarded)

### Step 4: Analyze Design Intent

- What is the original design purpose of this functionality?
- Which fields are intended to be modifiable vs. restricted?
- What security controls were designed into the system?
- Are there special business rules (e.g., email change requires verification code)?

### Step 5: Record Code Snippets

- For each critical step, extract relevant code snippets with full context
- Preserve complete if-else branches, try-catch blocks
- Annotate accurate file paths and line ranges
- Retain original code formatting and comments

---

## Data Flow Tracing by Field Type

For each high-risk field, trace the following path:

1. **Request intake** -- how does the value enter the system?
2. **Validation** -- what checks are applied before processing?
3. **Authorization** -- who is allowed to change this field?
4. **Secondary verification** -- is additional identity confirmation required?
5. **Persistence** -- how is the value written to the database?
6. **Side effects** -- what happens after the change (session invalidation, notifications)?

---

## Output

Write to `{output_dir}/profile_update/business_logic.json`.

Schema: see `@reference/JSON_SCHEMAS.md` § business_logic (Standard Schema).

---

## Analysis Notes

- Keep code snippets complete with 3-5 lines of surrounding context
- Track global components in execution order
- Record business logic steps strictly by actual execution sequence
- Identify implicit logic: framework defaults, AOP aspects, annotation processors
- Mark transaction boundaries and external service calls
- Follow existing project conventions for language-specific patterns
