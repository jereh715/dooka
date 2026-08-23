import os
import sys
import json
import urllib.request
import urllib.error

def scrape_jumia(payload=None):
    """
    Fetches raw HTML source code from jumia.co.ke using standard library urllib.
    No external dependencies (like 'requests') required!
    """
    url = "https://www.jumia.co.ke/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        # Timeout set to 12 seconds
        with urllib.request.urlopen(req, timeout=12) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
            return {
                "status_code": response.getcode(),
                "url": response.geturl(),
                "length": len(html_content),
                "html": html_content
            }

    except urllib.error.HTTPError as e:
        return {
            "status_code": e.code,
            "error": f"HTTP Error: {e.reason}"
        }
    except urllib.error.URLError as e:
        return {
            "status_code": 500,
            "error": f"URL Error: {e.reason}"
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
