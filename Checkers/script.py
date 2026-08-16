import json

def scrape_jumia(payload=None):
    """
    Fetches the HTML source code from jumia.co.ke using the requests library.
    Includes proper User-Agent headers to avoid getting blocked by anti-bot rules.
    """
    import requests  # Triggers dynamic installation if missing

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
    Fallback entry point router required by runner.py
    """
    if action == "scrape":
        return scrape_jumia(payload)
    return {"error": f"Action '{action}' not recognized."}
