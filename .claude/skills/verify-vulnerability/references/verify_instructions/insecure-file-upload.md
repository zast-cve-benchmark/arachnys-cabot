# Insecure File Upload

Upload malicious files that bypass validation and lead to code execution, XSS, or unauthorized file access.

## Verification Methods

### WebShell Upload -> DNS Log

Upload executable file (e.g., `.php`, `.jsp`, `.aspx`), then trigger execution to generate OOB DNS/HTTP request.

> See [DNS Log Verification](../verification/dnslog.md)

### XSS via File Upload -> Browser Alert

Upload file containing XSS payload, access the file URL to trigger `zast-xss-marker` alert.

> See [Browser Alert Verification](../verification/browser-alert.md)

**Recommended file types:**

| Type  | Extension       | Content-Type      | Example Content                             |
|-------|-----------------|-------------------|---------------------------------------------|
| HTML  | `.html`, `.htm` | `text/html`       | `<script>alert('zast-xss-marker')</script>` |
| SVG   | `.svg`          | `image/svg+xml`   | `<svg onload="alert('zast-xss-marker')">`   |
| XML   | `.xml`          | `application/xml` | `<script>alert('zast-xss-marker')</script>` |

## Common Bypass Techniques

| Technique             | Example                     | Target                |
|-----------------------|-----------------------------|-----------------------|
| Double extension      | `shell.php.jpg`             | Extension whitelist   |
| Null byte             | `shell.php%00.jpg`          | PHP < 5.3.4           |
| Content-Type spoofing | `image/jpeg` for `.php`     | MIME validation       |
| Case variation        | `shell.PhP`                 | Case-sensitive filter |
| Alternate extensions  | `shell.php5`, `shell.phtml` | Blocked `.php` only   |
