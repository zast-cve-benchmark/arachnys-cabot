---
name: audit-url-access
description: Audit endpoints with url-access capability. Produces ssrf findings.
---

# Role

Specialist for **ssrf**.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `url-access`. (Note: this capability was previously named "http-request"; it was renamed to "url-access" to reflect that the underlying APIs accept many URL schemes — `http(s)://`, `file://`, `ftp://`, `ws(s)://`, `php://filter`, `gopher://`, `jar://`, etc. — so the attack surface includes SSRF + local file disclosure + internal port scanning + JNDI lookup chains.)

# SINK patterns

## Route A — Direct outbound HTTP in this handler

| Language | SINK |
|---|---|
| Java   | `HttpURLConnection.openConnection(new URL(user))`, Apache `HttpClient.execute(new HttpGet(user))`, OkHttp `Request.url(user)`, `RestTemplate.exchange(user, ...)` |
| Python | `requests.get(user)` (and post/put/...), `urllib.request.urlopen(user)`, `httpx.get(user)`, `aiohttp.ClientSession.get(user)` |
| Node   | `fetch(user)`, `http.request(user)`, `axios.get(user)`, `request(user)` |
| Go     | `http.Get(user)`, `http.NewRequest(method, user, ...)` |
| PHP    | `curl_setopt($ch, CURLOPT_URL, $user)`, `file_get_contents($user)` (URL form), `fopen($user, "r")` (URL) |

## Route B — Stored URL → background fetch (do NOT skip this case)

If the handler does **not** itself fetch but **persists a user-controlled URL**
into storage (datastore / DB / file / global config), grep the project for
**downstream readers** of that stored record and check whether they fetch the
URL. Two greps are usually enough:

```bash
# 1. who reads this field off the stored record
grep -rn "<field-name>" src/
# 2. who issues outbound HTTP in this codebase
grep -rn "requests\.\(get\|post\)\|httpx\|urlopen\|fetch(\|http\.\(Get\|NewRequest\)" src/
```

Intersect the two: any reader that flows the stored value into an outbound
fetch is the downstream sink.

If a background worker / scheduled task / sibling endpoint fetches the stored
URL → **that is in-scope SSRF for this endpoint**. The CVE class is identical
to direct fetch; only the trigger path differs.

**Do not exclude on the grounds that "the fetch happens in a worker, outside
this handler's execution context".** That reasoning has caused multiple recall
misses on endpoints that create monitored-URL records, scheduled jobs,
webhook subscriptions, or any other "persist a URL now, fetch it later"
pattern.

## Key check (both routes)

Is the URL host part user-controlled AND missing allowlist / SSRF defenses
(deny private network ranges, deny `file://` protocol)? Common gaps:

- `validators.url()` / `is_safe_valid_url()` / similar only check
  format/protocol, **NOT** IP range. Private IPs (10.x, 172.16/12, 192.168.x,
  127.x, 169.254.169.254, ::1, fd00::/8) get through.
- `simple_host=True` in `validators.url()` allows hosts like `localhost` and
  bare IPs.
- Scheme allowlists that include `ftp://` or `file://` enable LFI pivot.

### Cross-protocol consideration

Many URL-fetching APIs in this capability accept non-HTTP schemes. When the
sink library (e.g. `urllib.request.urlopen` Python, `URL.openStream` Java, PHP
`file_get_contents`, Go `http.Get` is HTTP-only but Java's `URL` is multi-
protocol) does not restrict the scheme, an attacker-controlled URL can pivot
into:
- `file://` — local file disclosure (read /etc/passwd, app config, secrets)
- `ftp://`, `gopher://`, `dict://` — internal service interaction, SMTP smuggling
- `ws(s)://` — long-lived connections, internal websocket abuse
- `php://filter` (PHP) — read-with-filter (base64-encoded source disclosure)
- `jar://` (Java) — fetch JAR + load class, code execution if classloader is permissive
Always check the library docs for which schemes are accepted before declaring
"this is just HTTP" — most java.net.URL-based APIs default to allowing all.

# Safe context (false-positive prevention)

Do NOT report:

- URLs whose host part traces back to a hard-coded constant or system-controlled value
- Outbound calls protected by an allowlist that validates the host (not just the format) AND restricts schemes to `http(s)://`
- Validation that rejects private IP ranges (10.x, 172.16/12, 192.168.x, 127.x, 169.254.169.254, ::1, fd00::/8) before the fetch

Out-of-scope categories belong to other audit skills — open redirection (redirecting the user's
browser) -> `audit-url-redirect`. If you spot them, mention them in your report and let the
orchestrator dispatch the right specialist; do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
