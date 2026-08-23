import os
import sys
import zipfile
import urllib.request
import importlib

# 1. Store temporary libraries directly in the script's local folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_LIBS_DIR = os.path.join(CURRENT_DIR, "libs")

# Ensure target directory exists
os.makedirs(TEMP_LIBS_DIR, exist_ok=True)

if TEMP_LIBS_DIR not in sys.path:
    sys.path.insert(0, TEMP_LIBS_DIR)

def download_and_extract(url, target_dir):
    """
    Downloads a pure-Python package archive (wheel/zip) and extracts it directly into target_dir.
    """
    try:
        archive_path = os.path.join(target_dir, "package.zip")
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req) as response, open(archive_path, "wb") as out_file:
            out_file.write(response.read())

        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)

        if os.path.exists(archive_path):
            os.remove(archive_path)

        importlib.invalidate_caches()
        return True
    except Exception as e:
        print(f"[DOWNLOAD FAILED]: {e}")
        return False

def ensure_dependencies():
    """
    Ensures 'requests' and its required dependencies (urllib3, idna, chardet, certifi) 
    are extracted into the local libs directory.
    """
    try:
        import requests
    except ModuleNotFoundError:
        print("[SCRIPT] 'requests' missing. Downloading wheels to local libs folder...")
        
        deps = [
            "https://files.pythonhosted.org/packages/b2/b0/cd80327f17105a396417772346761184a1e94119d554a7375a02ad9d9354/certifi-2024.7.4-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/63/81/c465d0b05f0a1e05d97f2277d7f78c85741630b91e1beed85c9ec60a95ff/idna-3.8-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/c8/2d/e05b5832a514d1f2e46b96b3a0335759166fbc4b24e6503c15d487f87a87/charset_normalizer-3.3.2-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/ca/1c/7700a0b019f396e9447dd0a61ef87a4df1465bf1aa907ee6416bfb43ddac/urllib3-2.2.2-py3-none-any.whl",
            "https://files.pythonhosted.org/packages/f9/9b/335f943883391b01d5964f434b9d0739c0fa46487e47ef66ef0d84d1fa34/requests-2.32.3-py3-none-any.whl"
        ]
        
        for dep_url in deps:
            download_and_extract(dep_url, TEMP_LIBS_DIR)

ensure_dependencies()
import requests

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
