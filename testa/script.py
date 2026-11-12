import os
import sys
import threading
import tarfile
import urllib.request
import urllib.parse
import importlib
import json
import re

# ---------------------------------------------------------
# 1. Chaquopy Native Android Context & Storage Paths
# ---------------------------------------------------------
APP_FILES_DIR = None
ANDROID_CONTEXT = None

try:
    chaquopy_mod = importlib.import_module("com.chaquopy.python")
    Python = getattr(chaquopy_mod, "Python")
    ANDROID_CONTEXT = Python.getPlatform().getApplication()
    APP_FILES_DIR = str(ANDROID_CONTEXT.getFilesDir().getAbsolutePath())
except (ImportError, ModuleNotFoundError, AttributeError, Exception):
    APP_FILES_DIR = os.path.dirname(os.path.abspath(__file__))

LOCAL_LIB_DIR = os.path.join(APP_FILES_DIR, "libs")
CACHE_FILE = os.path.join(APP_FILES_DIR, "track_cache.json")
CACHE_LOCK = threading.Lock()

os.makedirs(LOCAL_LIB_DIR, exist_ok=True)

if LOCAL_LIB_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIB_DIR)

# Also dynamically add any extracted yt-dlp subfolders if already present
for d in os.listdir(LOCAL_LIB_DIR):
    if d.startswith("yt-dlp-"):
        inner = os.path.join(LOCAL_LIB_DIR, d, "yt_dlp")
        if os.path.exists(inner) and inner not in sys.path:
            sys.path.insert(0, inner)

INSTALLATION_STATUS = {
    "is_installed": False,
    "is_installing": False,
    "message": "Initializing...",
    "error": None
}

# ---------------------------------------------------------
# 2. Dynamic Package Management for yt-dlp (Fixed via PyPI Tarball)
# ---------------------------------------------------------
def install_ytdlp_background():
    global INSTALLATION_STATUS
    INSTALLATION_STATUS["is_installing"] = True
    INSTALLATION_STATUS["message"] = "Fetching yt-dlp package info..."

    try:
        pypi_url = "https://pypi.org/pypi/yt-dlp/json"
        req = urllib.request.Request(pypi_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            releases = data.get("releases", {})
            latest_version = data.get("info", {}).get("version")
            
            tar_url = None
            for file_info in releases.get(latest_version, []):
                if file_info.get("packagetype") == "sdist":
                    tar_url = file_info.get("url")
                    break
            
            if not tar_url:
                urls = [f["url"] for f in releases.get(latest_version, []) if f.get("url")]
                tar_url = urls[0] if urls else None

            if not tar_url:
                raise Exception("Could not find yt-dlp download link on PyPI.")

        INSTALLATION_STATUS["message"] = "Downloading yt-dlp source..."
        target_tar = os.path.join(LOCAL_LIB_DIR, "yt_dlp.tar.gz")
        
        req_tar = urllib.request.Request(tar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_tar, timeout=30) as response, open(target_tar, 'wb') as out_file:
            out_file.write(response.read())

        INSTALLATION_STATUS["message"] = "Extracting package..."
        with tarfile.open(target_tar, "r:gz") as tar_ref:
            tar_ref.extractall(LOCAL_LIB_DIR)

        extracted_dirs = [os.path.join(LOCAL_LIB_DIR, d) for d in os.listdir(LOCAL_LIB_DIR) if d.startswith("yt-dlp-")]
        if extracted_dirs:
            inner_pkg = os.path.join(extracted_dirs[0], "yt_dlp")
            if os.path.exists(inner_pkg) and inner_pkg not in sys.path:
                sys.path.insert(0, inner_pkg)

        if os.path.exists(target_tar):
            os.remove(target_tar)

        importlib.invalidate_caches()
        import yt_dlp
        
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
        print("[YT-DLP]: Successfully installed via PyPI tarball.")

    except Exception as e:
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["is_installed"] = False
        INSTALLATION_STATUS["error"] = str(e)
        INSTALLATION_STATUS["message"] = f"Engine error: {str(e)}"
        print(f"[YT-DLP INSTALL FAILED]: {e}")

def check_or_start_install():
    global INSTALLATION_STATUS
    if INSTALLATION_STATUS.get("is_installed"):
        return True
        
    try:
        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
        return True
    except ImportError:
        if not INSTALLATION_STATUS.get("is_installing", False):
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
# 3. Thread-Safe Cache Helpers
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
# 4. Audio Streaming & Caching
# ---------------------------------------------------------
def stream_and_trigger_download(params=None):
    if not params or not params.get("query"):
        return {"success": False, "error": "No query provided."}

    query = params.get("query").strip().lower()
    cache = _load_cache()

    result = None

    if query in cache and cache[query].get("stream_url"):
        result = cache[query]
        result["from_cache"] = True
    elif not check_or_start_install():
        return {"success": False, "error": f"yt-dlp not ready: {INSTALLATION_STATUS['message']}"}
    else:
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

        except Exception as e:
            return {"success": False, "error": f"Extraction error: {str(e)}"}

    return result

# ---------------------------------------------------------
# 5. Recommendation Engine (Diversified & Filtered)
# ---------------------------------------------------------
def _clean_title(title):
    title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', title)
    return title.strip().lower()

def get_recommendations(params=None):
    if not params or not (params.get("id") or params.get("query")):
        return {"success": False, "error": "Track ID or Query required."}

    track_id = params.get("id")
    query = params.get("query", "").strip()

    if not check_or_start_install():
        return {"success": False, "error": "yt-dlp engine not ready."}

    import yt_dlp

    cache = _load_cache()
    artist = ""
    current_title = ""

    if track_id and track_id in cache:
        t_info = cache[track_id]
        artist = t_info.get('artist', '')
        current_title = _clean_title(t_info.get('title', ''))
    elif query:
        current_title = _clean_title(query)

    if artist and artist.lower() != "unknown artist":
        search_target = f"ytsearch15:{artist} top tracks music"
    elif query:
        parts = query.split(" - ")
        base_artist = parts[0] if len(parts) > 1 else query.split()[0]
        search_target = f"ytsearch15:{base_artist} songs music"
    else:
        search_target = f"ytsearch15:{query} music"

    ydl_opts = {
        'format': 'ba[ext=m4a]/ba[ext=webm]/ba/worst',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'socket_timeout': 6,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=False)
            entries = info.get('entries', []) if info else []

            recommendations = []
            seen_titles = set()

            if current_title:
                seen_titles.add(current_title)

            for entry in entries:
                vid_id = entry.get('id')

                if not vid_id or vid_id == track_id:
                    continue

                raw_title = entry.get('title') or 'Unknown Title'
                clean_t = _clean_title(raw_title)

                if clean_t in seen_titles or (current_title and current_title in clean_t):
                    continue

                seen_titles.add(clean_t)

                if vid_id in cache:
                    recommendations.append(cache[vid_id])
                else:
                    artist_name = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'
                    thumbnails = entry.get('thumbnails', [])
                    thumbnail_url = thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

                    rec_result = {
                        "success": True,
                        "id": vid_id,
                        "title": raw_title,
                        "artist": artist_name,
                        "thumbnail": thumbnail_url,
                        "stream_url": None,
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
    cache = _load_cache()
    unique_tracks = {}
    for key, item in cache.items():
        if isinstance(item, dict) and "id" in item:
            unique_tracks[item["id"]] = item
    return {"success": True, "tracks": list(unique_tracks.values())}

def clear_cache(params=None):
    if os.path.exists(CACHE_FILE):
        try:
            with CACHE_LOCK:
                os.remove(CACHE_FILE)
            return {"success": True, "message": "Cache cleared successfully."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "message": "Cache was already empty."}

# ---------------------------------------------------------
# 6. Synchronized Lyrics Fetcher
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
