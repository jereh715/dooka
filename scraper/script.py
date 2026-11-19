import os
import sys
import json
import requests
from bs4 import BeautifulSoup


def scrape_jumia(payload=None):
    """
    Fetches raw HTML source code from jumia.co.ke using requests and parses/prettifies
    it with BeautifulSoup while preserving the original return structure.
    """
    url = "https://www.jumia.co.ke/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        # Timeout set to 12 seconds
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()

        soup = BeautifulSoup(response.content.decode("utf-8", errors="ignore"), "html.parser")
        html_content = soup.prettify()

        return {
            "status_code": response.status_code,
            "url": response.url,
            "length": len(html_content),
            "html": html_content
        }

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 500
        reason = e.response.reason if e.response is not None else str(e)
        return {
            "status_code": status_code,
            "error": f"HTTP Error: {reason}"
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": 500,
            "error": f"Request Error: {str(e)}"
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
