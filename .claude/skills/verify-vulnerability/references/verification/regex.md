# Regex Verification

Use for vulnerabilities that leak data (file read, command output). The verification checks if PoC output matches a regex pattern.

## How It Works

1. Execute PoC
2. Capture stdout/stderr
3. Match output against regex pattern

## PoC Example

```python
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "https://example.vulnerable.web.app.com"

    response = requests.post(
        url=f"{base_url}/api/read_file",
        json={"file": "/etc/passwd"},
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method regex --pattern "root:\S:0:0:[^:]*:[^:]*:[^:]*"
```

## Parameters

| Parameter    | Description                                                        | Required |
|--------------|--------------------------------------------------------------------|----------|
| `--method`   | Use `regex` for this verification                                  | Yes      |
| `--pattern`  | Regex pattern to match in output                                   | Yes      |
| `--env-file` | Path to environment file (default: `~/.config/zast-verifier/.env`) | No       |

## Common Patterns

| Target       | Pattern                         |
|--------------|---------------------------------|
| /etc/passwd  | `root:\S:0:0:[^:]*:[^:]*:[^:]*` |
| Command `id` | `uid=\d{1,5}\([\w-]+\)`         |
