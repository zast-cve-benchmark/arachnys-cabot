---
name: audit-file-ops
description: Audit endpoints with file-read / file-write / file-rename / file-delete / archive-extract capabilities. Produces insecure-file-read / insecure-file-write / insecure-file-delete / insecure-archive-extract / insecure-file-upload / path-traversal findings.
---

# Role

Specialist for file-operation vulnerabilities: path traversal, unauthorized file reads/writes/deletes,
archive extraction escapes, and dangerous file uploads.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `file-read`, `file-write`,
`file-rename`, `file-delete`, or `archive-extract`.

# SINK patterns

## Application-level sinks (path constructed by handler code)

| Action | Java | Python | Node | PHP |
|---|---|---|---|---|
| read   | `new FileInputStream(userPath)`, `Files.readAllBytes(Paths.get(userPath))`, `getResourceAsStream(user)` | `open(user)`, `Path(user).read_text()` | `fs.readFile(user, ...)` | `file_get_contents(user)`, `fopen(user, "r")`, `include`/`require`(user) |
| write  | `new FileOutputStream(user)`, `Files.write(...)` | `open(user, "w")` | `fs.writeFile(user, ...)` | `file_put_contents(user, ...)`, `fopen(user, "w")` |
| delete | `Files.delete(user)`, `File.delete()` | `os.remove(user)`, `os.unlink(user)` | `fs.unlink(user)` | `unlink(user)` |
| extract | `ZipInputStream.getNextEntry()` without validating `..` in `entry.getName()` | `tarfile.extract(user, ...)` without filter | `tar.extract(user, ...)` | `ZipArchive::extractTo(user)` |

Key judgment: **is the path validation sufficient**. `..` filtering, `canonicalize` +
`startsWith(basedir)`, and allowlists are valid mitigations; raw string concatenation into a path is a vulnerability.

**Pick category by DIRECTION of the file operation:**
- File read (open for reading, `getResourceAsStream`, `file_get_contents`) → `insecure-file-read`
- File write (open for writing, `file_put_contents`, `Files.write`) → `insecure-file-write`
- File delete (`Files.delete`, `os.remove`, `unlink`) → `insecure-file-delete`
- Archive extraction (Zip/Tar without entry-name sanitization, Tar-Slip) → `insecure-archive-extract`
- Unrestricted upload of dangerous file types (webshell, executable, SSRF-trigger) → `insecure-file-upload`
- Direction unknown, a single flaw spans multiple directions, or the primary harm is path enumeration → `path-traversal`

PHP `include`/`require` taking a user-controlled string: if the included file is **executed as code**
(the classic PHP include-as-eval pattern) → `code-injection`; if the file is merely **read** (e.g. via
`file_get_contents` or a non-PHP-executing include equivalent) → `insecure-file-read`.

Allowed `category_id` values for this skill: `insecure-file-read`, `insecure-file-write`, `insecure-file-delete`, `insecure-archive-extract`, `insecure-file-upload`, `path-traversal`, `code-injection`.

## Framework-level static-file mounts (do NOT skip)

Web frameworks expose **static-file mount helpers** that route an entire URL
subtree to a directory on disk. Each one is a path-traversal candidate
because the URL path becomes (after framework normalization) the path
resolved against the mount root:

| Stack | Sink shape |
|---|---|
| Go / Echo | `e.Static(prefix, root)`, `e.StaticFS(prefix, fs)`, `e.File(path, file)`, `e.FileFS(path, file, fs)` |
| Go / Gin | `r.Static(prefix, root)`, `r.StaticFS(prefix, fs)`, `r.StaticFile(path, file)`, `r.StaticFileFS(path, file, fs)` |
| Go / Fiber | `app.Static(prefix, root, ...)`, v3 `filesystem.New(filesystem.Config{Root: ...})` |
| Go / Chi / net/http / Gorilla | `mux.Handle(prefix, http.FileServer(http.Dir(root)))`, with or without `http.StripPrefix(...)` wrapping; `r.PathPrefix(prefix).Handler(http.FileServer(http.Dir(root)))` |
| Node / Express | `app.use(express.static(root))`, `app.use(prefix, express.static(root))` |
| Java / Spring | `WebMvcConfigurer.addResourceHandlers(...).addResourceLocations(...)`, XML `<mvc:resources mapping="/x/**" location="..."/>` |
| Java / Servlet | `DefaultServlet`-mapped paths serving from `WebContent/` or similar |
| Python / Flask | `Flask(static_folder=...)` default `/static/` mount; `send_from_directory(directory, user_filename)` (path argument is application-controlled but `user_filename` is attacker input) |
| Python / Django | `django.views.static.serve(request, path, document_root=...)` in URL conf |

A static-file mount is a **path-traversal** finding when **any** of these
conditions hold:

1. **The framework version is known-vulnerable** for its static handler's
   path normalization (e.g. older Echo, older Gin, older Express
   serve-static, etc.). When you can see a `go.mod` / `package.json` /
   `pom.xml` pinning a version, prefer reporting if you cannot confirm
   the version is patched.
2. **The mount root is a relative or CWD-dependent path** (e.g.
   `filepath.Join(os.Getwd(), "app")`, `"./public"`, `"frontend"`) — a
   traversal that escapes the mount root reaches arbitrary paths above
   it, not just intended assets.
3. **The mount root contains application-internal data** (source files,
   config, secrets) that the public should not read — i.e. the mount
   root is the application code directory rather than an isolated assets
   directory.
4. **`send_from_directory` / equivalent helper is called with an
   attacker-controlled filename** without `os.path.basename` or
   safe-join normalization in front of it.

When emitting the finding for a static mount, the `data_flow` should
include the mount-registration line (e.g. the `e.Static(...)` call site).
The "request parameter that carries the payload" for `record-vulnerabilities`
step 1 is **the URL path itself** — the attacker controls the path of the
request that reaches this mount.

Use `category_id = path-traversal`.

Defenses that make a static mount safe:

- Mount root is a dedicated assets directory containing only intended
  public files, AND the framework's static handler is on a patched
  version (no known traversal CVE).
- A custom handler wraps the static lookup with `filepath.Clean` +
  `strings.HasPrefix(absoluteResolved, mountRoot)` containment check
  (this is the pattern `safejoin` libraries implement; recognize it as
  a real defense).

# Safe context (false-positive prevention)

## Patterns already handled by the framework (safe)

If the input being concatenated into the path comes from a **mainstream web framework's upload-object
filename attribute** (Django `UploadedFile.name`, Express `req.file.originalname` / busboy-parsed
filename, Spring `MultipartFile.getOriginalFilename()`), the filename **has already been stripped to a
basename by the framework** by the time it reaches the handler -- the `MultiPartParser
.sanitize_file_name` equivalent does `rsplit("/")[-1]` + `rsplit("\\")[-1]` and rejects bare
`.`/`..`. Path-traversal along this path is a safe pattern already handled by the framework.

**Sub-cases that are still problematic**: after the handler obtains the basename, it continues to
URL-decode / Base64-decode it / concatenates it into another path (e.g. using the uploaded filename
as a key written to a second directory) -- decoding can produce path separators. That is a new sink
and must be checked independently.

## Other safe patterns

Do NOT report:

- Paths whose user-controlled segment is filtered for `..` AND `/` (and `\\` on Windows-aware
  code) before use
- Paths run through `canonicalize` / `realpath` then verified with `startsWith(basedir)` or
  equivalent containment check. **Order matters:** a `startsWith(prefix)` /
  `getPath().startsWith(...)` / prefix check applied to a **non-canonicalized** path is NOT a
  mitigation — `../` segments survive a raw string-prefix test, so the check is bypassable. The
  canonicalize / `realpath` / `Path.normalize()` step MUST run *before* the containment check;
  if it does not, the path is still traversable — report it.
- Paths resolved against a fixed allowlist of basenames / IDs (e.g. `{"avatar": "/srv/...", ...}`)
- Paths whose user-controlled segment traces back to a hard-coded constant or
  system-controlled value

Out-of-scope: unsafe file-write in upload scenarios (insecure-file-upload by the business axis
rather than the capability axis) may overlap with file-write here; mention it in your report
and let the orchestrator decide whether to also dispatch the upload-specialist. Do not
double-file the same finding.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
