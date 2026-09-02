import os
import sys
import threading
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(BASE_DIR, "lyrics_libs")

os.makedirs(LIB_DIR, exist_ok=True)
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

STATUS = {
    "ready": False,
    "installing": False,
    "message": "Initializing...",
    "error": None
}

def install_dependencies():
    global STATUS
    STATUS["installing"] = True
    STATUS["message"] = "Installing syncedlyrics & dependencies..."
    
    try:
        import runpy
        # Install with full dependencies so required packages like rapidfuzz/requests are available
        sys.argv = ['pip', 'install', '--target', LIB_DIR, 'syncedlyrics', '--quiet']
        runpy.run_module('pip', run_name='__main__')
        
        importlib.invalidate_caches()
        STATUS["ready"] = True
        STATUS["installing"] = False
        STATUS["message"] = "Engine Ready"
    except Exception as e:
        STATUS["installing"] = False
        STATUS["error"] = str(e)
        STATUS["message"] = f"Install failed: {str(e)}"

def check_or_start_engine():
    global STATUS
    try:
        import syncedlyrics
        STATUS["ready"] = True
        STATUS["message"] = "Ready"
        return True
    except ImportError:
        if not STATUS["installing"]:
            thread = threading.Thread(target=install_dependencies, daemon=True)
            thread.start()
        return False

# Trigger background check/install on load
check_or_start_engine()

def get_install_status(params=None):
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
    if not check_or_start_engine():
        return {"error": f"Engine not ready: {STATUS['message']}"}

    if not params or not params.get("query"):
        return {"error": "Search query parameter required."}

    query = params.get("query")
    
    try:
        import syncedlyrics
        lrc_raw = syncedlyrics.search(query)
        
        if not lrc_raw:
            return {"success": False, "message": "No lyrics found."}

        is_synced = "[" in lrc_raw and "]" in lrc_raw
        
        return {
            "success": True,
            "query": query,
            "is_synced": is_synced,
            "raw": lrc_raw,
            "parsed": parse_lrc(lrc_raw) if is_synced else []
        }
    except Exception as e:
        return {"error": f"Extraction error: {str(e)}"}
