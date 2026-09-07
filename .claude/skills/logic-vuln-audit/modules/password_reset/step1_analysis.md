# Password Reset Business Logic Analysis Guide

## Purpose

Guide the Password Reset Agent through a systematic analysis of forgot/reset password business logic in web applications. The agent must understand the original design intent, trace all data flows, and document the complete workflow before vulnerability detection begins.

---

## Task

1. Perform deep analysis of the **password reset functionality** (also known as "forgot password", "reset password", "retrieve password") to understand its original design
2. Understand framework-specific characteristics across languages (Java, PHP, Python, Golang, Node.js)
3. Trace global configurations (filters, interceptors, middleware, decorators, AOP)
4. Analyze the complete business logic flow, design rationale, and security control mechanisms
5. Record key code snippets for every step in the business logic workflow
6. Output results as structured JSON to the designated output path

### Global Components to Examine (Cross-Language)

| Language | Components to Trace |
|----------|-------------------|
| Java | Filter, Interceptor, AOP, @Transactional, config files (application.yml/properties) |
| PHP | Middleware, Event Listener, Service Provider, config files (.env/config/) |
| Python | Middleware, Decorator, Signal, config files (settings.py/config.py) |
| Golang | Middleware, Interceptor, config files (yaml/json/toml) |
| Node.js | Middleware, Hook, Plugin, config files (config.js/.env) |

---

## Analysis Requirements

### 1. Entry Point Discovery Strategy

Search for all routes and endpoints related to password reset using the following approach:

- **Keyword matching**: Search for `forgot`, `reset`, `retrieve`, `password`, `recover`, `restore` in route definitions, method names, and class names
- **Common endpoints**: `/forgot-password`, `/reset-password`, `/password/reset`, `/auth/reset`, `/verify-code`, `/password/recover`
- **Module locations**: Search within `auth`, `user`, `account`, `security` modules and directories
- **Route configuration**: Check centralized route configuration files for related definitions
- **Controller/Handler identification**: Locate the corresponding controller or handler methods
- **HTTP method and parameter recording**: Document the HTTP verb, URL parameters, and request body schema for each endpoint

### 2. Complete Business Flow Tracking

Trace the following stages in chronological order of user interaction:

1. **Request Reset**: User submits a reset request (via email, phone number, or username)
2. **Identity Verification**: Verification code generation and delivery, security question validation, CAPTCHA checks
3. **Credential Generation**: Reset token or link generation logic, including randomness, length, and encoding
4. **Token Validation**: How the reset credential is verified on the server side
5. **Password Update**: New password setting, hashing, storage, and post-reset session handling

### 3. Key Code Snippet Extraction

For each business logic step, extract:

- Core processing code (including critical conditional branches)
- Data validation code (input sanitization, format checks)
- State change code (database updates, cache mutations)
- Called service/utility methods
- Database operation statements (SQL or ORM calls)

### 4. Global Impact Factor Analysis

Identify all global components that may affect the password reset flow:

- **Auth interceptors/filters**: Special handling for reset endpoints (e.g., bypass rules)
- **Rate limiting configuration**: Request frequency limits, IP-based throttling
- **Session management**: Session/Token handling approach
- **Permission configuration**: Access control rules (Spring Security, Shiro, Passport.js, etc.)
- **Global exception handling**: How error messages are returned to the client
- **Configuration files**: Token expiration, verification code length, retry limits (application.yml, web.xml, .env, etc.)
- **Service middleware**: Email service, SMS service, cache service configurations

### 5. Analysis Depth Requirements

- **Logic flow**: Trace the complete business flow, including cross-service calls
- **Data flow**: Record the full lifecycle of data: reception, validation, transformation, storage
- **Permission checks**: Identify authorization logic at every step
- **Exception handling**: Document how each error condition is handled
- **Dependencies**: Identify dependent services (email, SMS, cache, queue)
- **Third-party libraries**: Analyze call relationships and configuration only, do not deep-dive into library internals
- **Database**: Analyze SQL statements and ORM mappings, do not analyze stored procedure internals

### 6. Design Rationale Summary

Summarize the security design philosophy of the implementation:

- Security mechanisms used (token encryption, verification code type, expiration design)
- Protective measures (brute force prevention, user enumeration prevention, rate limiting)
- Potential design weaknesses identified during analysis

---

## Output

Write to `{output_dir}/password_reset/business_logic.json`.

Schema: see `@reference/JSON_SCHEMAS.md` § business_logic (Standard Schema).

---

## Entry Point Discovery Checklist

Before moving to analysis, confirm that all of the following have been searched:

- [ ] Route/endpoint definitions containing password reset keywords
- [ ] Controller or handler classes in auth/user/account/security modules
- [ ] API gateway or reverse proxy route configurations
- [ ] Frontend form action URLs and AJAX endpoints for reset flows
- [ ] Background job or queue definitions for email/SMS delivery
- [ ] Admin panel endpoints for manual password reset (if exposed)

---

## Analysis Notes

### Code Extraction Principles
- Each `code_snippet` must be complete with surrounding context (3-5 lines before and after)
- Include complete if-else branches and try-catch blocks
- Annotate accurate `file_path` and `line_range`
- Preserve original code formatting and comments
- If a snippet exceeds 50 lines, extract the core logic and note the omission

### Global Component Tracking
- Identify ALL global components that affect the password reset flow
- Mark `execution_order` to reflect actual processing sequence
- Describe each component's actual role (authentication, authorization, logging, parameter validation)

### Business Logic Chain
- Record `workflow_id` and `step_id` in strict execution order
- Annotate key operations at each step
- Identify implicit logic: framework default behaviors, AOP aspects, annotation processors
- Flag transaction control presence
- Flag external service calls

### Cross-Language Adaptation
- **Java**: Focus on @Transactional, @RequestMapping, Filter chains, Spring Security config
- **PHP**: Focus on Middleware, Events, Eloquent ORM transactions, Laravel guards
- **Python**: Focus on decorators, middleware, ORM sessions, Django/Flask auth
- **Golang**: Focus on middleware chains, defer-based transaction rollback, Gin/Echo handlers
- **Node.js**: Focus on middleware stacks, Promise/async transactions, Passport.js strategies
