import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = "http://localhost:8450/py"

    payload_b64 = "%OBJ_BASE64%"

    response = requests.post(
        url=f"{base_url}/api/pickle",
        data=payload_b64,
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
