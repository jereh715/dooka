import json

def scrape_jumia(payload=None):
    """
    Fetches the raw HTML source code from jumia.co.ke using the requests library.
    Sets standard headers to mimic a valid web browser request.
    """
    import requests  # Dynamic dependency handled by runner.py

    url = "https://www.jumia.co.ke/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        
        return {
            "status_code": response.status_code,
            "url": response.url,
            "length": len(response.text),
            "html": response.text
        }
    except Exception as e:
        return {
            "status_code": 500,
            "error": str(e)
        }

def handle_request(action, payload=None):
    """
    Fallback request router for runner.py execution.
    """
    if action == "scrape":
        return scrape_jumia(payload)
    return {"error": f"Action '{action}' not recognized."}
