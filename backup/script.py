import os
import sys
import re
import threading
import importlib

# Setup local storage directory for dependencies
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(BASE_DIR, "lyrics_libs")

os.makedirs(LIB_DIR, exist_ok=True)
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

STATUS = {
    "ready": False,
    "installing": False,
    "error": None
}

def _install_syncedlyrics():
    global STATUS
    STATUS["installing"] = True
    try:
        import runpy
        sys.argv = ['pip', 'install', '--target', LIB_DIR, 'syncedlyrics', '--no-deps', '--quiet']
        runpy.run_module('pip', run_name='__main__')
        importlib.invalidate_caches()
        STATUS["ready"] = True
    except Exception as e:
        STATUS["error"] = str(e)
    finally:
        STATUS["installing"] = False

def check_engine():
    try:
        import syncedlyrics
        STATUS["ready"] = True
        return True
    except ImportError:
        if not STATUS["installing"]:
            threading.Thread(target=_install_syncedlyrics, daemon=True).start()
        return False

def parse_lrc(lrc_text):
    """Converts raw LRC string format into structured time/text records."""
    if not lrc_text:
        return []
    
    parsed = []
    pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')
    
    for line in lrc_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            minutes, seconds, millis, text = match.groups()
            time_sec = int(minutes) * 60 + int(seconds) + int(millis) / (1000 if len(millis) == 3 else 100)
            if text.strip():
                parsed.append({"time": time_sec, "text": text.strip()})
    return parsed

def get_lyrics(params=None):
    if not check_engine():
        return {"error": "Engine initializing. Please try again shortly."}

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
        return {"error": f"Search failed: {str(e)}"}
