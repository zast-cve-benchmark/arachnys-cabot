# Browser Alert Verification

Use for XSS vulnerabilities. The verification checks if a browser alert is triggered when rendering the response.

## How It Works

1. Send request that injects malicious content
2. Browser renders the response
3. Check if alert with expected message appears

## PoC Example

```python
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "https://example.vulnerable.web.app.com"

    response = requests.get(
        url=f"{base_url}/api/xss",
        params={"name": "<script>alert('zast-xss-marker')</script>"},
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method browser-alert --alert-msg zast-xss-marker
```

## Parameters

| Parameter     | Description                                                        | Required |
|---------------|--------------------------------------------------------------------|----------|
| `--method`    | Use `browser-alert` for this verification                          | Yes      |
| `--alert-msg` | Expected alert message (e.g., `zast-xss-marker`)                   | Yes      |
| `--env-file`  | Path to environment file (default: `~/.config/zast-verifier/.env`) | No       |
