---
name: expand-endpoint-context
description: For a given HTTP endpoint, walk the codebase to produce an ordered list of business-relevant source regions, a short endpoint summary, and a step-by-step workflow narrative. Use when asked to "expand endpoint context", "find business code for endpoint X", or analyze a single API endpoint's implementation in depth.
---

# Expand Endpoint Context

## Task

Given a free-text identifier for ONE HTTP endpoint (URL path, controller method name, or pasted snippet), walk the codebase and produce:

1. A short one-sentence `description` of what the endpoint does.
2. A step-by-step `workflow` narrative tracing the request from entry to response, at the granularity of "call X to fetch Y, if A == B branch to C".
3. An ordered list of `regions` (file_path + line range) covering every piece of source code referenced by the workflow — controller handler, request DTO, response DTO, service implementations, validators, auth/middleware, config-driven branches, exception handlers.

Output exactly one ` ```json ``` ` fenced block as your final message. No prose outside the fence.

---

## Arguments

- **FREE_TEXT** — A string identifying the endpoint. Examples:
  - `GET /api/users/{id}`
  - `/api/users`
  - `UserController.getUser`
  - A pasted code snippet that includes a method definition.

If FREE_TEXT is empty or you cannot identify a specific endpoint from it, ASK the user which endpoint to analyze before doing anything else. Do not guess.

---

## Workflow

### 1. Resolve the endpoint to a controller location

Try in this order:

1. **Check `./webapp_sources.json`** (or path from `ZAST_WEBAPP_SOURCES_FILE` env var). If present, use `jq` or Grep to find the matching entry:

   ```bash
   jq '.[] | select(.endpoint == "/api/users/{id}" and .method == "GET")' webapp_sources.json
   ```

   Each entry has `endpoint`, `method`, `region: {file_path, start_line, end_line}`. Use the region as your starting point.

2. **Grep / Glob the source tree directly** if `webapp_sources.json` is missing or has no match. Look for the route declaration (decorator / annotation / router registration).

3. If still ambiguous (multiple endpoints match), pick the most specific match by exact path + method; if still ambiguous, ASK the user.

### 2. Walk the implementation

Starting from the controller handler:

- Read the handler with `Read` to get its exact line range.
- Follow each call to a non-stdlib symbol — request validation, services, repositories, auth filters, middleware, anything that runs in the request path.
- For each piece of code you reference in the `workflow`, record its actual line range in `regions`.

**Coverage targets** (don't skip any):

- **Request body / parameter structure**: DTO classes, validation annotations, query-param parsing.
- **Response body structure**: response DTOs, status code branches, exception → error response mappings.
- **Business logic**: every conditional and external call relevant to the endpoint's behavior.

### 3. Critical rules

- **Don't hallucinate line numbers.** Every region's `start_line` / `end_line` must be from a range you actually opened with `Read`. If a file is too long to fully read, read the relevant slice — but never write a line number you haven't seen.
- **Order regions by business execution order**, not by file or import order. The first region should be the entry handler; the last is wherever the response is finally constructed or the request terminates.
- **No region cap** — include as many or as few as the endpoint actually needs.
- **Granularity for `workflow`**: "1. extract id from path → 2. AuthFilter.preHandle checks session role → 3. UserService.findById(id) queries DB, filters deleted=true → 4. UserDTO.from(entity) returns 200, else 404."

### 4. Output format

Final message MUST be exactly one JSON fence, nothing else:

````
```json
{
  "endpoint": "GET /api/users/{id}",
  "description": "Returns a user profile with role-based access check and soft-delete filtering.",
  "workflow": "1. Extract id from path → 2. AuthFilter checks session role; non-admin can only access self → 3. UserService.findById(id) queries DB, deleted=true rows filtered out → 4. UserDTO.from(entity) returns 200; null returns 404.",
  "regions": [
    {"file_path": "src/controllers/UserController.java", "start_line": 42, "end_line": 78},
    {"file_path": "src/filters/AuthFilter.java", "start_line": 18, "end_line": 44},
    {"file_path": "src/services/UserService.java", "start_line": 14, "end_line": 38},
    {"file_path": "src/dto/UserDTO.java", "start_line": 1, "end_line": 22}
  ]
}
```
````

The downstream parser is strict — extra prose, multiple fences, or schema deviations will cause the endpoint to be marked failed.
