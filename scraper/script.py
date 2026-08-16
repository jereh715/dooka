import os
import sys
import subprocess

# Define a local vendor directory for packages relative to this miniapp
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_LIBS_DIR = os.path.join(CURRENT_DIR, "libs")

# Ensure the local library path is added to sys.path
if LOCAL_LIBS_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIBS_DIR)

def ensure_requests_installed():
    """
    Checks if requests is importable. If missing, installs it 
    directly into the local 'libs' directory.
    """
    try:
        import requests
    except ModuleNotFoundError:
        os.makedirs(LOCAL_LIBS_DIR, exist_ok=True)
        # Run pip install targeting the local relative directory
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--target", LOCAL_LIBS_DIR,
            "requests"
        ]
        subprocess.check_call(cmd)

# Auto-run self-installation on script load
ensure_requests_installed()

import requests  # Now safe to import globally inside this script


def scrape_jumia(payload=None):
    """
    Fetches the raw HTML source code from jumia.co.ke using the requests library.
    """
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
