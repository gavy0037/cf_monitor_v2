import urllib.request
import json
import logging

logger = logging.getLogger(__name__)

def fetch_cf_api(endpoint: str) -> dict:
    url = f"https://codeforces.com/api/{endpoint}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"Error fetching from Codeforces API {endpoint}: {e}")
        return {"status": "FAILED", "comment": str(e)}

def get_user_info(handle: str) -> dict:
    data = fetch_cf_api(f"user.info?handles={handle}")
    if data.get("status") == "OK" and len(data.get("result", [])) > 0:
        return data["result"][0]
    return {}

def get_user_status(handle: str, count: int = 100) -> list:
    data = fetch_cf_api(f"user.status?handle={handle}&from=1&count={count}")
    if data.get("status") == "OK":
        return data.get("result", [])
    return []
