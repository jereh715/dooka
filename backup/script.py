import os
import sys
import threading
import zipfile
import urllib.request
import importlib

print("[DEBUG] Initializing script.py execution...")

# 1. Safe Dynamic Import for Chaquopy / Standalone Execution
APP_FILES_DIR = None

try:
    chaquopy_mod = importlib.import_module("com.chaquopy.python")
    Python = getattr(chaquopy_mod, "Python")
    context = Python.getPlatform().getApplication()
    APP_FILES_DIR = str(context.getFilesDir().getAbsolutePath())
    print(f"[DEBUG] Chaquopy environment detected. Files dir: {APP_FILES_DIR}")
except Exception as e:
    APP_FILES_DIR = os.path.dirname(os.path.abspath(__file__))
    print(f"[DEBUG] Standard environment fallback. Directory: {APP_FILES_DIR} (Reason: {e})")

LIB_DIR = os.path.join(APP_FILES_DIR, "lyrics_libs")
os.makedirs(LIB_DIR, exist_ok=True)

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
    print(f"[DEBUG] Added {LIB_DIR} to sys.path")

STATUS = {
    "ready": False,
    "installing": False,
    "message": "Initializing...",
    "error": None,
    "lib_dir": LIB_DIR
}

def install_dependencies():
    global STATUS
    STATUS["installing"] = True
    STATUS["message"] = "Installing syncedlyrics..."
    print("[DEBUG] Starting background installation worker...")

    # Method 1: Standard runpy pip
    try:
        import runpy
        print("[DEBUG] Attempting pip install via runpy module...")
        sys.argv = ['pip', 'install', '--target', LIB_DIR, 'syncedlyrics', 'rapidfuzz', 'requests', '--quiet']
        runpy.run_module('pip', run_name='__main__')
        importlib.invalidate_caches()

        import syncedlyrics
        STATUS["ready"] = True
        STATUS["installing"] = False
        STATUS["message"] = "Engine Ready via PIP"
        print("[DEBUG] PIP installation succeeded. syncedlyrics imported successfully.")
        return
    except Exception as e1:
        print(f"[DEBUG] PIP method failed: {e1}")

    # Method 2: Direct Zip Extract Fallback
    try:
        print("[DEBUG] Attempting fallback zip archive download...")
        STATUS["message"] = "Downloading package zip..."
        url = "https://github.com/moezx/syncedlyrics/archive/refs/heads/main.zip"
        target_zip = os.path.join(LIB_DIR, "syncedlyrics.zip")

        urllib.request.urlretrieve(url, target_zip)
        print(f"[DEBUG] Downloaded zip to {target_zip}")

        with zipfile.ZipFile(target_zip, 'r') as zip_ref:
            zip_ref.extractall(LIB_DIR)

        if os.path.exists(target_zip):
            os.remove(target_zip)

        # Move extracted package into LIB_DIR root
        extracted_folder = os.path.join(LIB_DIR, "syncedlyrics-main")
        if os.path.exists(extracted_folder):
            src_pkg = os.path.join(extracted_folder, "syncedlyrics")
            dest_pkg = os.path.join(LIB_DIR, "syncedlyrics")
            if os.path.exists(src_pkg) and not os.path.exists(dest_pkg):
                import shutil
                shutil.move(src_pkg, dest_pkg)
                print(f"[DEBUG] Moved package from {src_pkg} to {dest_pkg}")

        importlib.invalidate_caches()
        import syncedlyrics
        STATUS["ready"] = True
        STATUS["installing"] = False
        STATUS["message"] = "Engine Ready via Zip Extraction"
        print("[DEBUG] Zip extraction method succeeded.")
    except Exception as e2:
        print(f"[DEBUG] Zip fallback failed: {e2}")
        STATUS["installing"] = False
        STATUS["error"] = str(e2)
        STATUS["message"] = f"Failed: {str(e2)}"

def check_or_start_engine():
    global STATUS
    try:
        import syncedlyrics
        STATUS["ready"] = True
        STATUS["message"] = "Ready"
        return True
    except ImportError as ie:
        print(f"[DEBUG] syncedlyrics import check failed: {ie}")
        if not STATUS["installing"]:
            thread = threading.Thread(target=install_dependencies, daemon=True)
            thread.start()
        return False

check_or_start_engine()

def get_install_status(params=None):
    print(f"[DEBUG] get_install_status endpoint invoked. Params: {params}")
    check_or_start_engine()
    return STATUS

def parse_lrc(lrc_text):
    if not lrc_text:
        return []
    import re
    parsed = []
    pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')
    for line in lrc_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            m, s, ms, text = match.groups()
            time_sec = int(m) * 60 + int(s) + int(ms) / (1000 if len(ms) == 3 else 100)
            if text.strip():
                parsed.append({"time": time_sec, "text": text.strip()})
    return parsed

def get_lyrics(params=None):
    print(f"[DEBUG] get_lyrics endpoint invoked. Params: {params}")
    if not check_or_start_engine():
        return {"error": f"Engine not ready: {STATUS['message']}"}

    if not params or not params.get("query"):
        return {"error": "Search query parameter required."}

    query = params.get("query")

    try:
        import syncedlyrics
        print(f"[DEBUG] Searching lyrics via syncedlyrics for query: {query}")
        lrc_raw = syncedlyrics.search(query)

        if not lrc_raw:
            return {"success": False, "message": "No lyrics found for this song."}

        is_synced = "[" in lrc_raw and "]" in lrc_raw

        return {
            "success": True,
            "query": query,
            "is_synced": is_synced,
            "raw": lrc_raw,
            "parsed": parse_lrc(lrc_raw) if is_synced else []
        }
    except Exception as e:
        print(f"[DEBUG] Error during lyrics extraction: {e}")
        return {"error": f"Extraction error: {str(e)}"}
