import os
import sys
import importlib

# 1. Setup local vendor path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_LIBS_DIR = os.path.join(CURRENT_DIR, "libs")

if LOCAL_LIBS_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIBS_DIR)

def install_via_pip(package_name):
    """
    Programmatic pip installer designed for cross-platform (Desktop + Android/Chaquopy).
    """
    os.makedirs(LOCAL_LIBS_DIR, exist_ok=True)
    
    # Method 1: Subprocess (Desktop / Linux / macOS)
    try:
        import subprocess
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--target", LOCAL_LIBS_DIR,
            package_name
        ]
        subprocess.check_call(cmd)
        importlib.invalidate_caches()
        return True
    except Exception as e:
        print(f"[PIP SUBPROCESS FAILED]: {e}")

    # Method 2: In-Process Fallback via runpy (Android / Chaquopy safe)
    try:
        import runpy
        # Prevents sys.exit() from killing the Python runtime
        sys.argv = ['pip', 'install', '--target', LOCAL_LIBS_DIR, package_name]
        runpy.run_module('pip', run_name='__main__')
        
        importlib.invalidate_caches()
        return True
    except SystemExit as e:
        # pip run_module will trigger SystemExit(0) on success
        if e.code == 0:
            importlib.invalidate_caches()
            return True
        print(f"[PIP RUNPY SYSTEMEXIT]: Failed with code {e.code}")
    except Exception as e:
        print(f"[PIP IN-PROCESS FAILED]: {e}")

    return False


# Safe import execution
try:
    import requests
except ModuleNotFoundError:
    print("[SCRIPT] 'requests' not found. Attempting local installation...")
    if install_via_pip("requests"):
        import requests
    else:
        raise ModuleNotFoundError("Could not auto-install 'requests' via local pip.")


def scrape_jumia(payload=None):
    """
    Fetches raw HTML source code from jumia.co.ke.
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
