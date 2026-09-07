# API Base URL

## Why ZAST Needs API Base URL

ZAST extracts all API endpoints from source code during code audit (e.g., `@RequestMapping("/user/delete")`), but these are only "relative paths" at code level. To make PoC actually access the remote server, you need the root path's internet address to construct the "absolute path".

```
Code perspective:  /user/delete                   (extracted by detector)
Real perspective:  https://prod-server.com/api/user/delete  (full URL for PoC)
```

API Base URL completes the protocol, domain, and gateway prefix, enabling ZAST-generated PoCs to precisely access target endpoints and verify vulnerabilities.

## Definition

**API Base URL** is the prefix that, when combined with code-level endpoint paths, produces the internet-accessible address:

```
[API Base URL] + [Endpoint Path] = [Real Accessible URL]
```

## Common Questions

### Is API Base URL the service domain?

**Not necessarily.** It depends on whether your service is directly mounted under the root domain.

In production, reverse proxies like Nginx often change the API Base URL. Suppose your backend source defines endpoint: `/internal/config`, local access: `http://localhost:8080/internal/config`

But in Nginx config:

```nginx
location /api/v1/ {
    proxy_pass http://localhost:8080/;
}
```

External access becomes: `https://public-domain.com/api/v1/internal/config`

In this case, API Base URL must include the Nginx prefix:
- **Correct**: `https://public-domain.com/api/v1`
- **Wrong**: `https://public-domain.com`

**Principle**: ZAST can only detect `/internal/config` from code. For PoC to reach the remote endpoint, API Base URL must satisfy:

```
[API Base URL] + /internal/config = Internet-accessible real address
```

### Is API Base URL the login URL?

**No.** Login URL is a specific business endpoint. API Base URL is the common prefix for all endpoints.

### Is API Base URL a specific endpoint URL?

**No.** It should not contain any specific business endpoint (like `/getUser` or `/upload`). It's a "prefix" URL, the common starting point for accessing all endpoints defined in source code.

## Examples

| Scenario | API Base URL |
|----------|--------------|
| Direct deployment | `https://api.example.com` |
| With gateway prefix | `https://api.example.com/v1` |
| Internal service | `http://192.168.1.100:8080` |
| Nginx mapped | `https://public-domain.com/api/v1` |
