import os
import sys
import threading
import zipfile
import urllib.request
import urllib.parse
import importlib
import json
import re

# ---------------------------------------------------------
# 1. Safe Dynamic Import for Chaquopy / Standalone Execution
# ---------------------------------------------------------
APP_FILES_DIR = None

try:
    chaquopy_mod = importlib.import_module("com.chaquopy.python")
    Python = getattr(chaquopy_mod, "Python")
    context = Python.getPlatform().getApplication()
    APP_FILES_DIR = str(context.getFilesDir().getAbsolutePath())
except (ImportError, ModuleNotFoundError, AttributeError, Exception):
    APP_FILES_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------
# 2. Configure Storage Paths & Locks
# ---------------------------------------------------------
LOCAL_LIB_DIR = os.path.join(APP_FILES_DIR, "libs")
CACHE_FILE = os.path.join(APP_FILES_DIR, "track_cache.json")
CACHE_LOCK = threading.Lock()

os.makedirs(LOCAL_LIB_DIR, exist_ok=True)

if LOCAL_LIB_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIB_DIR)

INSTALLATION_STATUS = {
    "is_installed": False,
    "is_installing": False,
    "message": "Initializing...",
    "error": None
}

# ---------------------------------------------------------
# 3. Dynamic Package Management for yt-dlp
# ---------------------------------------------------------
def install_ytdlp_background():
    global INSTALLATION_STATUS
    INSTALLATION_STATUS["is_installing"] = True
    INSTALLATION_STATUS["message"] = "Downloading yt-dlp..."

    try:
        import runpy
        sys.argv = ['pip', 'install', '--target', LOCAL_LIB_DIR, 'yt-dlp', '--no-deps', '--quiet']
        runpy.run_module('pip', run_name='__main__')
        
        importlib.invalidate_caches()
        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
        return
    except SystemExit as e:
        if e.code == 0:
            importlib.invalidate_caches()
            INSTALLATION_STATUS["is_installed"] = True
            INSTALLATION_STATUS["is_installing"] = False
            INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
            return
    except Exception as e1:
        print(f"[RUNPY PIP FAILED]: {e1}")

    try:
        INSTALLATION_STATUS["message"] = "Downloading zip archive..."
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        target_zip = os.path.join(LOCAL_LIB_DIR, "yt_dlp_zip.zip")
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response, open(target_zip, 'wb') as out_file:
            out_file.write(response.read())
        
        with zipfile.ZipFile(target_zip, 'r') as zip_ref:
            zip_ref.extractall(LOCAL_LIB_DIR)

        if os.path.exists(target_zip):
            os.remove(target_zip)

        importlib.invalidate_caches()
        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
    except Exception as e2:
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["is_installed"] = False
        INSTALLATION_STATUS["error"] = str(e2)
        INSTALLATION_STATUS["message"] = f"Engine error: {str(e2)}"

def check_or_start_install():
    global INSTALLATION_STATUS
    try:
        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["message"] = "Ready"
        return True
    except ImportError:
        if not INSTALLATION_STATUS["is_installing"]:
            thread = threading.Thread(target=install_ytdlp_background)
            thread.daemon = True
            thread.start()
        return False

def get_install_status(params=None):
    check_or_start_install()
    return {
        "success": True,
        "is_installed": INSTALLATION_STATUS.get("is_installed", False),
        "is_installing": INSTALLATION_STATUS.get("is_installing", False),
        "message": INSTALLATION_STATUS.get("message", "Unknown"),
        "error": INSTALLATION_STATUS.get("error")
    }

# ---------------------------------------------------------
# 4. Thread-Safe Cache Helpers
# ---------------------------------------------------------
def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with CACHE_LOCK:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache_data):
    try:
        with CACHE_LOCK:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CACHE WRITE ERROR]: {e}")

# ---------------------------------------------------------
# 5. Fast Audio Streaming & Caching
# ---------------------------------------------------------
def stream_and_trigger_download(params=None):
    if not params or not params.get("query"):
        return {"success": False, "error": "No query provided."}

    query = params.get("query").strip().lower()
    cache = _load_cache()

    # Fast path: return cached track metadata directly
    if query in cache and cache[query].get("stream_url"):
        cached_item = cache[query]
        cached_item["from_cache"] = True
        return cached_item

    if not check_or_start_install():
        return {"success": False, "error": f"yt-dlp not ready: {INSTALLATION_STATUS['message']}"}

    import yt_dlp

    ydl_opts = {
        'format': 'ba[ext=m4a]/ba[ext=webm]/ba/worst',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
        'skip_download': True,
        'extract_flat': False,
        'socket_timeout': 8,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            target = query if (query.startswith("http") or len(query) == 11) else f"ytsearch1:{query}"
            info = ydl.extract_info(target, download=False)
            video = info['entries'][0] if 'entries' in info and info['entries'] else info

            video_id = video.get('id')
            stream_url = video.get('url')

            if not stream_url:
                return {"success": False, "error": "No stream URL extracted."}

            title = video.get('title', 'Unknown Title')
            artist = video.get('uploader') or video.get('channel') or 'Unknown Artist'
            
            thumbnails = video.get('thumbnails', [])
            thumbnail_url = video.get('thumbnail') or (thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")

            result = {
                "success": True,
                "id": video_id,
                "title": title,
                "artist": artist,
                "thumbnail": thumbnail_url,
                "stream_url": stream_url,
                "duration": video.get('duration', 0),
                "from_cache": False
            }

            cache[query] = result
            if video_id:
                cache[video_id] = result
            _save_cache(cache)

            return result

    except Exception as e:
        return {"success": False, "error": f"Extraction error: {str(e)}"}

# ---------------------------------------------------------
# 6. Fixed Recommendation Engine (Fast Flat Extraction)
# ---------------------------------------------------------
def get_recommendations(params=None):
    """
    Finds related tracks instantly using flat search extraction.
    Returns metadata immediately and leaves stream_url as None to avoid network timeouts.
    """
    if not params or not (params.get("id") or params.get("query")):
        return {"success": False, "error": "Track ID or Query required."}

    track_id = params.get("id")
    query = params.get("query", "").strip()

    if not check_or_start_install():
        return {"success": False, "error": "yt-dlp engine not ready."}

    import yt_dlp

    cache = _load_cache()

    # Build smart search target based on track metadata or query
    if query:
        search_target = f"ytsearch6:{query} music"
    elif track_id and track_id in cache:
        t_info = cache[track_id]
        search_target = f"ytsearch6:{t_info.get('title', '')} {t_info.get('artist', '')} music"
    else:
        search_target = f"ytsearch6:{track_id} music"

    ydl_opts = {
        'format': 'ba[ext=m4a]/ba[ext=webm]/ba/worst',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',  # Instant metadata fetch without downloading full video info
        'socket_timeout': 6,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=False)
            entries = info.get('entries', []) if info else []

            recommendations = []
            for entry in entries:
                vid_id = entry.get('id')

                if not vid_id or vid_id == track_id:
                    continue

                # Return cached track directly if available
                if vid_id in cache:
                    recommendations.append(cache[vid_id])
                    continue

                title = entry.get('title') or 'Unknown Title'
                artist = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'

                thumbnails = entry.get('thumbnails', [])
                thumbnail_url = thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

                rec_result = {
                    "success": True,
                    "id": vid_id,
                    "title": title,
                    "artist": artist,
                    "thumbnail": thumbnail_url,
                    "stream_url": None,  # Resolved on-demand when clicked via stream_and_trigger_download
                    "duration": entry.get('duration', 0),
                    "from_cache": False
                }

                recommendations.append(rec_result)

                if len(recommendations) >= 5:
                    break

            return {"success": True, "recommendations": recommendations}

    except Exception as e:
        return {"success": False, "error": f"Failed to get recommendations: {str(e)}"}

def get_cached_tracks(params=None):
    """Retrieve all previously searched and saved track details."""
    cache = _load_cache()
    unique_tracks = {}
    for key, item in cache.items():
        if isinstance(item, dict) and "id" in item:
            unique_tracks[item["id"]] = item
    return {"success": True, "tracks": list(unique_tracks.values())}

def clear_cache(params=None):
    """Clear local cached track details."""
    if os.path.exists(CACHE_FILE):
        try:
            with CACHE_LOCK:
                os.remove(CACHE_FILE)
            return {"success": True, "message": "Cache cleared successfully."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "message": "Cache was already empty."}

# ---------------------------------------------------------
# 7. Lyrics Parsing and Fetching
# ---------------------------------------------------------
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
        return {"success": False, "error": "Search query parameter required."}

    query = params.get("query").strip()
    
    # Provider 1: LRCLIB API
    try:
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode())
            if data and isinstance(data, list) and len(data) > 0:
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

    # Provider 2: MegaloBiz
    try:
        search_url = f"https://www.megalobiz.com/searchall?qv={urllib.parse.quote(query)}"
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as response:
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
        print(f"[DEBUG] MegaloBiz Fetch Error: {e}")

    # Provider 3: Fallback Plaintext Scraper
    try:
        genius_url = f"https://genius.com/api/search/multi?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(genius_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as response:
            res_json = json.loads(response.read().decode())
            sections = res_json.get('response', {}).get('sections', [])
            song_path = None
            for sec in sections:
                if sec.get('type') == 'song' and sec.get('hits'):
                    song_path = sec['hits'][0]['result']['path']
                    break
            
            if song_path:
                song_url = f"https://genius.com{song_path}"
                req_page = urllib.request.Request(song_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_page, timeout=6) as page_res:
                    page_html = page_res.read().decode()
                    raw_text = re.sub(r'<br\s*/?>', '\n', page_html)
                    raw_text = re.sub(r'<[^>]+>', '', raw_text)
                    lyrics_match = re.search(r'\[Lyrics.*?\n([\s\S]*?)(?=\n\[|\Z)', raw_text)
                    if lyrics_match:
                        cleaned_lyrics = lyrics_match.group(1).strip()
                        return {
                            "success": True,
                            "query": query,
                            "is_synced": False,
                            "raw": cleaned_lyrics,
                            "parsed": []
                        }
    except Exception as e:
        print(f"[DEBUG] Fallback Plaintext Scraper Error: {e}")

    return {"success": False, "message": "No lyrics found for this search."}
