---
name: audit-file-upload
description: Audit file-upload endpoints. Produces insecure-file-upload findings.
---

# Role

Specialist for `insecure-file-upload` (file-type/MIME bypass, path traversal in storage, SVG/HTML script content, etc.).

**The core proposition is NOT "can the uploaded filename path-traverse"**
(mainstream frameworks like Django MultiPartParser / Express busboy / Spring MultipartResolver
already strip the `Content-Disposition` filename down to basename, so the
"upload-time path-traversal" on that path is mostly a framework FP).

**The real proposition is**: the content uploaded + how it is subsequently processed = whether remote exploitation is achievable.
Two concrete main tracks:

**Track 1: uploadable file type -> server-side code execution**
**Track 2: uploadable file type + the file can be fetched by a browser -> browser-side attack (stored XSS / SVG payload / HTML phishing)**

# Trigger recap

Dispatched when identify-business-scenarios returns file-upload.

# SINK patterns

## Track 1 — Server-side code execution (highest priority)

**The issue**: if the uploaded file is some "server-executable" format and lands in a location that can be triggered for execution by the web server / interpreter / container engine, the attacker gets RCE with a single upload.

**Decision conditions (report only when **both** hold)**:

a) **Missing dangerous-suffix rejection list**: the handler does not validate suffixes, uses a blacklist (easy to bypass), or uses a loose whitelist.
   The following suffixes should all be strictly rejected (selected per runtime stack):

   | Runtime stack | Dangerous suffixes |
   |---|---|
   | PHP | `.php` `.php3` `.php4` `.php5` `.phtml` `.phar` `.inc` `.pht` |
   | Java (Tomcat/Jetty) | `.jsp` `.jspx` `.jspf` `.tag` `.tagx` `.war` |
   | ASP.NET | `.asp` `.aspx` `.asax` `.ascx` `.ashx` `.config` `.cs` `.vb` |
   | Python (misconfigured cgi/uwsgi) | `.py` `.pyc` `.cgi` |
   | Perl/CGI | `.pl` `.cgi` |
   | Shell/system | `.sh` `.bash` `.bat` `.ps1` |
   | Server config | `.htaccess` `.htpasswd` `web.config` |
   | Container | `Dockerfile` `.dockerignore` (rare but if it triggers a build) |

   **Bypass patterns**: double suffix `evil.php.jpg`, null byte `evil.jpg\0.php`, casing
   `.PhP`, Apache multi-extension parsing (`.php.unknown` is still parsed as PHP),
   Windows `::$DATA`.

b) **Storage location can be triggered by the runtime**:
   - Written to the `webroot` directory of a PHP/JSP project, and that directory is parsed by Apache/Nginx/Tomcat
   - Written to a Node `static` directory — no RCE on its own, but combined with SSRF may pull a remote RCE chain
   - Written to an archive that the application later extracts via `tarfile.extract` / `unzip` and executes hooks inside (zip-slip + RCE)

c) **A publicly/guessable access path exists**: after upload the handler returns path / id so the client can re-request to trigger execution, or the filename pattern is known (no random UUID prefix).

If a + b hold (or a + a guessable filename pattern), report `insecure-file-upload`; description must clearly state "which suffix category + which directory it lands in + who will execute it".

## Track 2 — Browser-side attack (stored XSS / phishing / CSRF)

**The issue**: even if the server side does not execute the uploaded file, as long as it can be **fetched by a browser**, the attacker can upload
"content that executes when rendered by the browser", achieving stored XSS.

**Dangerous browser-renderable types**:

| Type | Attack |
|---|---|
| `.svg` | SVG containing `<script>` / `onload` executes when the browser loads it as an image |
| `.html` / `.htm` / `.xhtml` | Rendered directly as a page, arbitrary JS |
| `.xml` / `.xsl` | XSL template / external entity / can be rendered when containing inline script |
| `.pdf` | Old Adobe PDF contains JS; modern browsers are safer but it can serve as a phishing carrier |
| `.swf` | Flash (EOL but still rendered by some systems) |
| `.docx` / `.xlsx` | Opened in browser may trigger office protocol / link vulnerabilities |
| `.eml` / `.mht` | Mail archive formats are rendered by some browsers |

**Trigger conditions (report only when **both** hold)**:

a) **The handler accepts these renderable types** (whitelist missing/loose, or only validates by Content-Type
   — the attacker forges `image/png` while uploading a real SVG payload).

b) **The upload is browser-accessible via URL after upload** — typically manifested as:
   - The handler response body contains the uploaded file's relative path / id, and the frontend builds a URL to re-request
   - The upload directory is a public mapping like `MEDIA_URL` / `static/`
   - The system has a download endpoint like `/files/<id>` without a `Content-Disposition: attachment`
     header (missing this header makes the browser render in place instead of downloading)

If a + b hold, report `insecure-file-upload`; description must clearly state "which file type +
how the access URL is built + what the browser will execute".
**Extra credit**: check whether the response header has `Content-Disposition: attachment` to force download and `X-Content-Type-Options: nosniff` to block MIME sniffing — missing these two enlarges the attack surface.

Allowed `category_id` values for this skill: `insecure-file-upload`.

# Safe context (false-positive prevention)

Safe patterns already handled by the framework (just recognize these; no further drill-down needed):

- **path-separators in multipart filename**: Django `MultiPartParser.sanitize_file_name` (`rsplit("/")[-1]` + `rsplit("\\")[-1]` + reject
  plain `.`/`..`), Express `busboy`, Spring `MultipartFile.getOriginalFilename`
  (combined with `Hibernate Validator`'s `@SafeHtml`/`@Pattern`) all strip
  the `Content-Disposition` filename down to basename.
  If the handler consumes the filename attribute of the framework's upload object (rather than a manually parsed
  raw header), the filename **will not** contain path separators or `..` — the
  "upload path-traversal" on this path is a safe pattern already reasonably handled by the framework.

  **The sub-case that is still problematic**: the handler further concatenates + decodes this basename
  (e.g. URL-decode, Base64-decode and then uses it as a filename), which may restore path separators —
  that is a new sink and requires separate examination.

- Pure path-traversal (no upload scenario) → `audit-file-ops`, not here.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
