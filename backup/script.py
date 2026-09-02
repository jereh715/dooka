import json
import re
import urllib.parse
import urllib.request

# Instant ready state to break background thread installation loops
STATUS = {
    "ready": True,
    "installing": False,
    "message": "Engine Ready (Pure API Mode)",
    "error": None
}

def get_install_status(params=None):
    return STATUS

def parse_lrc(lrc_text):
    if not lrc_text:
        return []
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
    if not params or not params.get("query"):
        return {"error": "Search query parameter required."}

    query = params.get("query").strip()
    
    # 1. Direct query to LRCLIB API (Primary provider for synced & plain lyrics)
    try:
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if data and isinstance(data, list) and len(data) > 0:
                # Prioritize entries that contain timestamped lyrics
                best_match = next((item for item in data if item.get('syncedLyrics')), data[0])
                
                synced_lrc = best_match.get('syncedLyrics')
                plain_lrc = best_match.get('plainLyrics')
                
                if synced_lrc:
                    return {
                        "success": True,
                        "query": query,
                        "is_synced": True,
                        "raw": synced_lrc,
                        "parsed": parse_lrc(synced_lrc)
                    }
                elif plain_lrc:
                    return {
                        "success": True,
                        "query": query,
                        "is_synced": False,
                        "raw": plain_lrc,
                        "parsed": []
                    }
    except Exception as e:
        print(f"[DEBUG] LRCLIB Fetch Error: {e}")

    # 2. Secondary Regex Fallback (MegaloBiz search fallback)
    try:
        search_url = f"https://www.megalobiz.com/searchall?qv={urllib.parse.quote(query)}"
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode()
            lrc_matches = re.findall(r'\[\d{2}:\d{2}\.\d{2,3}\].*', html)
            if lrc_matches:
                raw_lrc = "\n".join(lrc_matches)
                return {
                    "success": True,
                    "query": query,
                    "is_synced": True,
                    "raw": raw_lrc,
                    "parsed": parse_lrc(raw_lrc)
                }
    except Exception as e:
        print(f"[DEBUG] Fallback Fetch Error: {e}")

    return {"success": False, "message": "No lyrics found for this search."}
