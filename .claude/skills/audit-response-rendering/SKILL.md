---
name: audit-response-rendering
description: Audit endpoints that render user-controlled data in the response. Produces xss / http-response-splitting findings.
---

# Role

Specialist for `xss` and `http-response-splitting`.

Your job is to look at what the response carries, then **trace each field back
to its real source**. A field's source is "user-controlled" if it ultimately
comes from request input — directly, OR via a DB / file / cache that other
endpoints write user input into. You audit **the rendering end**, not the
storage end: an endpoint that reads a stored user-supplied string and emits
it raw into an HTML / SPA-rendered context is the vulnerability site.

# Trigger recap

Dispatched when identify-business-scenarios returns response-rendering.
"Rendering" includes:
- Returning HTML / strings the browser interprets as HTML
- Returning JSON / GraphQL responses whose **string-typed** fields are known to
  be rendered raw by a single-page frontend (dashboard / management UI / CMS)
- Returning JSON the caller proxies to an HTML page

# How to trace a field's source

For each value that flows into the response, walk it backwards until you reach
one of:

1. **Request input** (`request.args`, `req.body`, `@RequestParam`, GraphQL
   resolver args, path/query/header). → user-controlled, reflected.
2. **A DB / persisted store read** (Django ORM `.get()`/`.filter()`, JPA
   `findById()`, DAO calls, Redis `GET`, file read). → check whether **any
   other endpoint writes user input into that same field/key**. If yes, treat
   it as user-controlled — this is **stored XSS**. If no, it's safe.
3. **A constant / framework-injected value** (settings, env, ID counters). →
   safe.

Stored-XSS reasoning rule: if a model field / DB column / GraphQL type field
is written by ANY mutation / admin / CRUD endpoint that accepts user-supplied
strings, then EVERY read of that field that lands in HTML / SPA-rendered
context is XSS unless it's escaped on the read side. The data taking a trip
through the DB does **not** sanitize it.

The corollary: report stored XSS **at the render-side endpoint**, not at the
endpoint that wrote the data. The writer's job is persistence; the reader's
job is to encode for its output context, and the reader is where the bug
lives.

# SINK patterns

**HTML / template / JS-execution-capable contexts** — emit `xss`:

| Language | SINK |
|---|---|
| Java   | `response.getWriter().write(user)`, JSP `<%= user %>` unescaped, Thymeleaf `th:utext`, FreeMarker `?no_esc`, Spring `@ResponseBody` returning user-controlled HTML directly. **GraphQL `String`-typed resolver fields** that a SPA (dashboard / admin / management console) renders into the DOM — treat each such field as a SINK unless it's HTML-encoded at write *or* read time. |
| Python | Flask `render_template_string(user)` (mixed -- both SSTI and XSS), Django `mark_safe(user)`, custom template tags / filters that emit DB strings without `escape()` (e.g. tags that return a raw string from a tag function — anything other than passing through Django's autoescaped variable path), FastAPI `Response(content=user, media_type="text/html")`. |
| Node   | Express `res.send("<html>" + user + "</html>")`, EJS `<%- user %>` (vs safe `<%= %>`), React `dangerouslySetInnerHTML`, GraphQL resolvers returning `String` fields that the SPA renders. |
| PHP    | `echo $user`, `print $user` (without `htmlspecialchars`). |

**Flask bare-string / f-string responses — HIGH PRIORITY, frequently missed:**

A Flask view that `return`s a plain string (or a `(string, status)` tuple)
sends it with `Content-Type: text/html` by default. If that string is built
from request input without escaping, it is reflected XSS:

```python
return f"Item with ID {item_id} not found", 404     # item_id = path param -> reflected XSS
return "Error: " + request.args.get("q"), 400        # query param         -> reflected XSS
```

Check **every `return` statement of the view, including error / 404 / 400
branches** — not just the success path. The bug is the absence of
`markupsafe.escape()` (or returning JSON / `text/plain`). A path or query
parameter echoed into a bare-string return is the single most common reflected
XSS in Flask apps; do not overlook it.

**HTTP response splitting:**

- `response.addHeader("X-Foo", user)` where user contains `\r\n`
- `setHeader("Location", user)` with CRLF injection
- raw `res.write("X-Custom: " + user + "\r\n")`

Allowed `category_id` values for this skill: `xss`, `http-response-splitting`.

# Misleading "sanitizers" — these do NOT make the data safe

A surprising number of functions look like sanitizers but don't HTML-encode.
Treat the output as still-tainted when you see only one of these guarding a
sink:

- **Django `strip_tags()` / `bleach.clean(strip=True)`** — strips complete
  tag *syntax* but does not HTML-encode. Attribute-context payloads,
  unclosed tags, JS-URI handlers, and other vectors survive. If a field
  flows through `strip_tags()` alone before reaching HTML, it's still XSS.
  Safe only when paired with `escape()` or used in an
  already-autoescaped Jinja2/Django variable.
- **`bleach.clean()` without an allow-list lock-down**, or with
  `strip_comments=False` — partial mitigation; treat as still-tainted unless
  you can read its config and confirm an HTML-safe allowlist.
- **Length truncation / character filters** (`re.sub(r"[^a-zA-Z0-9]", "")`
  on the surface) — confirm the regex actually removes `<`, `>`, `"`, `'`,
  `&`. Otherwise still-tainted.
- **JSON.stringify embedded in `<script>`** — not safe by default for
  `</script>` injection; needs explicit escaping of `<`.

# Safe context (false-positive prevention)

XSS requires an HTML (or HTML content-sniffable) execution context. Do NOT
report XSS when the data lands in a non-HTML context:

- **XML / RSS / Atom feeds.** Data placed into a feed via a feed-generator
  library (`feedgen`, `feedgenerator`, etc.) and served as
  `application/rss+xml` / `application/atom+xml` is XML-escaped by the library
  and is not rendered as HTML by browsers — not XSS.
- **Plain `application/json` API consumed only by machine clients.** No XSS.
  But if the producer is a GraphQL / REST endpoint whose String fields are
  rendered raw by a known SPA (dashboards, CMS admin, management consoles),
  the JSON serialization does NOT save you — the SPA renders the string as
  HTML. That is XSS.
- **Already-escaped output.** Data passed through `markupsafe.escape()`,
  `html.escape()`, `django.utils.html.escape()`, an auto-escaping template
  variable (`{{ x }}` in Jinja2 with autoescape on), or `htmlspecialchars()`
  is safe. (Note: `strip_tags()` is NOT in this list — see above.)

XSS is for data reaching an HTML / SPA-rendered response body unescaped.
Confirm the content-type **and** the escaping before reporting.

- SSTI (the template string itself is user-controlled) → `audit-template-render`, not in scope here.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
