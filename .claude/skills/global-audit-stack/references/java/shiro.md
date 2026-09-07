# Apache Shiro Configuration Audit Reference

Used by audit-stack when LANGUAGE=java, FRAMEWORK=shiro. Covers Shiro's filter chain definitions, anon/authc/roles mapping, rememberMe cookie, authorization model, and session config.

## Enumeration discipline (READ THIS FIRST)

Shiro `filterChainDefinitions` blocks are dense, line-after-line path-pattern mappings. Each line is an independent authorization rule and each line can independently be misconfigured. **When you audit a Shiro project, enumerate EVERY path entry in the block — finding one misconfigured `anon` line is NOT finishing the audit.** A common bug pattern is several path-pattern entries with the same misconfiguration (e.g., multiple admin paths all whitelisted as `anon`) — they are independent vulnerabilities and must be reported independently.

Apply the same exhaustive enumeration to any other framework-configuration list (filter chain bean definitions, custom filter registrations, etc.).

### Workflow for the filterChainDefinitions block

Follow these steps mechanically — do NOT skip ahead:

1. **Locate every chain definition source.** Run these greps and Read every matched file:
   ```
   grep -rn "filterChainDefinitionMap\|setFilterChainDefinitionMap\|setFilterChainDefinitions\|filterChainDefinitions:" <project-root>
   grep -rn "ShiroFilterFactoryBean\|DefaultFilterChainManager" <project-root>
   ```
   Sources can be `application.yml` `shiro:` section, `shiro.ini` files, Java `@Bean` methods returning `ShiroFilterFactoryBean`, or programmatic `chainBuilder.addPathDefinition(...)` calls.

2. **Extract every (path-pattern, filter) entry** from each source. Print them out as a flat list — every line in the block becomes one entry.

3. **For EACH entry**, classify the path:
   - Public surface (login, static, registration with rate limiting, public API documentation) → `anon`/`noSessionCreation` is fine
   - Admin / user-data / state-changing / sensitive-read → `anon` here is a finding
   - Self-registration handlers that take secret tokens or impersonation paths → `anon` is suspicious; trace to confirm

4. **Cross-reference each `anon` path** against `.discovered_endpoints.txt` (if present) to confirm the path actually maps to a routable controller. An `anon` path that doesn't map to anything is theoretical; an `anon` path that maps to a real controller is exploitable.

5. **Report every `anon`-on-sensitive entry as a separate finding.** Do not collapse multiple entries into one finding. If you see five `anon` lines all whitelisting different sensitive paths, that's five `incorrect-authorization` findings, not one.

Same workflow applies to `roles[...]` and `perms[...]` entries — check whether the role/permission gate actually matches the sensitivity of the path.

## Architecture: Filter Chain Mapping

Shiro uses `ShiroFilterFactoryBean` to map URL patterns to filter chains. Each URL matches the first pattern in `filterChainDefinitionMap`. Filter names like `anon` (no auth), `authc` (require login), `perms["user:create"]` (require permission) define the required security level.

Key points to trace:
- How does URL pattern matching work? Does it normalize paths the same way the servlet container does?
- Which URL patterns map to `anon`? Are all of these truly public resources?
- Are there path traversal possibilities (e.g., `/admin;/../dashboard`) where Shiro and the servlet container disagree on what the path is?

## Architecture: rememberMe Cookie

Shiro's "remember me" feature uses a cookie that contains a serialized Java object, encrypted with AES-CBC. The encryption key is configurable via `securityManager.rememberMe.cipherKey`.

Key points to trace:
- Where is the cipher key defined? Is it the default `kPH+bIxk5D2deZiIxcaaaA==` or has it been changed?
- The cookie data is a serialized Java object. If the encryption key is known, an attacker can decrypt, modify the object, re-encrypt, and deserialization will reconstruct it.
- Follow the deserialization path — what happens when the object is deserialized?

## Authorization Model

Shiro supports roles and permissions checked via:
- URL filter chains: `roles["admin"]`, `perms["user:delete"]`
- Annotations: `@RequiresRoles`, `@RequiresPermissions`
- Programmatic: `Subject.hasRole()`, `Subject.isPermitted()`

Key points to trace:
- Are authorization checks applied consistently across all CRUD operations for each resource?
- Which endpoints are missing authorization annotations entirely?

## Custom Shiro filter subclasses

Projects often subclass Shiro filters to plug in JWT auth, stateless sessions, etc. These subclasses sit in the same filter chain enforced by `filterChainDefinitionMap` and are the place where the project's own auth logic actually runs. **You MUST read every such subclass against Shiro's filter contract, not just check that "auth-looking code exists".** A `return true` in the wrong override silently turns the filter into a no-op for entire HTTP methods or paths.

### How to find them

```
grep -rn "extends AccessControlFilter\|extends AdviceFilter\|extends PathMatchingFilter\|extends AuthenticatingFilter\|extends FormAuthenticationFilter\|extends BasicHttpAuthenticationFilter" <project-root>/src
```

For each match, Read the class and walk through the contract semantics below.

### Contract semantics that trip up reviewers

| Class | Override | Returning `true` means | Common bug |
|---|---|---|---|
| `AccessControlFilter` | `isAccessAllowed` | "request is already allowed; skip `onAccessDenied`" | Returning `false` unconditionally is intentional only when you then enforce auth in `onAccessDenied` |
| `AccessControlFilter` | `onAccessDenied` | **"grant access — let the request continue down the filter chain"** | Returning `true` for a whole HTTP method (most commonly `OPTIONS`) lets attackers reach every protected controller without any token |
| `AdviceFilter` | `preHandle` | "continue the chain" | Returning `true` early on a category of requests (by path, header, method) bypasses everything after the filter, including downstream `executeChain` work |
| `PathMatchingFilter` | `onPreHandle(req, res, mappedValue)` | "continue the chain" | Same bug class — early `return true` for a method/path skips auth |
| `AuthenticatingFilter` | `createToken` | constructs the token used by `subject.login(...)` | Building a token from a header that may be absent (no null check) crashes the filter — leaks via 500 timing; building from an attacker-supplied claim without verification chains into JWT misuse |

### Specific traps to verify in every subclass you read

1. **HTTP-method short-circuit.** A check like `if (request.getMethod().equals("OPTIONS")) return true` in `onAccessDenied` / `preHandle` does NOT mean "this is a CORS preflight". A real CORS preflight requires `Origin` AND `Access-Control-Request-Method` headers. Bare method match is bypassable with `curl -X OPTIONS`. Preflight handling belongs in a dedicated `CorsFilter` ordered ahead of the Shiro chain, not inside an auth filter's grant decision.

2. **Path-prefix short-circuit.** `if (uri.startsWith("/public"))` is path-normalization-naive: `/public/../admin/users`, `/public;foo=bar/admin`, URL-encoded slashes, and trailing-dot variants can collide with the early-return branch but resolve to a protected controller. Cross-reference against the servlet container's normalization rules.

3. **Exception handler that swallows auth failure.** `try { subject.login(token); } catch (Exception e) { log.error(...); return true; }` — catching and returning `true` is "I logged the failure AND let the request through". Should be `return false` (or invoke `unionFailResponse`) on every error path.

4. **`isAccessAllowed` returns user-controlled truthiness.** `return tokenValue != null` (any token, even invalid, allows access) instead of actually validating the token. Auth filters often defer validation to `onAccessDenied`, but if both methods are written naively the request gets through without ever being verified.

5. **Custom realm called from a custom filter.** When the filter calls a custom `Realm.doGetAuthenticationInfo`, follow the realm too — a realm that decodes-without-verifying a JWT (see `global-audit-auth/SKILL.md` JWT Pattern 1) makes the filter's `subject.login()` trivially forgeable regardless of how careful the filter is.

## Output

- `anon` / `noSessionCreation` rule applied to a sensitive path (admin, user data, registration endpoints) → `incorrect-authorization`
- Custom Shiro filter subclass whose `onAccessDenied` / `preHandle` / `isAccessAllowed` grants access for a whole HTTP method, path prefix, or exception path (see "Custom Shiro filter subclasses" above) → `incorrect-authorization`
- Hardcoded `cipherKey` / `rememberMe.cipherKey` / `securityManager.rememberMeManager.cipherKey` → `static-key-leak`
- Deserialization of attacker-controlled cookie content via known or weak cipherKey → `insecure-deserialization`
- Session cookie config without `HttpOnly` or with eternal timeout → `business-logic-flaw`
- CORS-style cross-origin enabled in `crossDomainSessionSecurity=false` or equivalent → `cors-misconfiguration`
