import os
import json
import threading
import sys
from flask import Flask, request, jsonify

app = Flask(__name__)

CACHE_FILE = "stream_cache.json"
CACHE_LOCK = threading.Lock()

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def _load_cache():
    """Load cached audio metadata and stream info from disk."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with CACHE_LOCK:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[CACHE ERROR]: Failed to read cache: {e}")
        return {}

def _save_cache(cache_data):
    """Save audio metadata to local disk cache safely."""
    try:
        with CACHE_LOCK:
            with open(CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"[CACHE ERROR]: Failed to write cache: {e}")

def check_or_start_install():
    """Ensure yt-dlp is available in the environment."""
    try:
        import yt_dlp
        return True
    except ImportError:
        print("[ENGINE ERROR]: yt-dlp engine not available in environment.")
        return False

# ---------------------------------------------------------
# Core Extraction Engine
# ---------------------------------------------------------

def stream_and_trigger_download(params=None):
    """
    Extract direct audio stream URL and metadata.
    Accepts either a direct video ID, YouTube URL, or search query.
    """
    if not params or not params.get("query"):
        return {"success": False, "error": "Query or video ID parameter required."}

    query = params.get("query").strip()

    if not check_or_start_install():
        return {"success": False, "error": "yt-dlp engine not ready."}

    import yt_dlp

    cache = _load_cache()

    # If query is a raw video ID and already cached, return immediately
    if query in cache and cache[query].get("stream_url"):
        res = cache[query]
        res["from_cache"] = True
        return res

    # Standardize search query format
    if not (query.startswith("http://") or query.startswith("https://") or len(query) == 11):
        target = f"ytsearch1:{query}"
    else:
        target = query

    ydl_opts = {
        'format': 'ba[ext=m4a]/ba[ext=webm]/ba/worst',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'skip_download': True,
        'socket_timeout': 10,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target, download=False)

            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            vid_id = info.get('id')
            
            # Cache lookup post-resolution
            if vid_id in cache and cache[vid_id].get("stream_url"):
                res = cache[vid_id]
                res["from_cache"] = True
                return res

            title = info.get('title', 'Unknown Title')
            artist = info.get('uploader') or info.get('channel') or 'Unknown Artist'
            stream_url = info.get('url')
            duration = info.get('duration', 0)

            thumbnails = info.get('thumbnails', [])
            thumbnail_url = thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

            result = {
                "success": True,
                "id": vid_id,
                "title": title,
                "artist": artist,
                "thumbnail": thumbnail_url,
                "stream_url": stream_url,
                "duration": duration,
                "from_cache": False
            }

            if vid_id:
                cache[vid_id] = result
                _save_cache(cache)

            return result

    except Exception as e:
        print(f"[EXTRACTION ERROR]: {e}")
        return {"success": False, "error": f"Failed to extract media: {str(e)}"}


# ---------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------

def get_recommendations(params=None):
    """
    Find related tracks instantly using flat search extraction.
    Lazy-loads stream URLs to prevent blocking Android main threads.
    """
    if not params or not (params.get("id") or params.get("query")):
        return {"success": False, "error": "Track ID or Query required."}

    track_id = params.get("id")
    query = params.get("query", "").strip()

    if not check_or_start_install():
        return {"success": False, "error": "yt-dlp engine not ready."}

    import yt_dlp

    cache = _load_cache()

    # Determine fast search target query
    if query:
        search_target = f"ytsearch6:{query} music"
    elif track_id and track_id in cache:
        track_info = cache[track_id]
        search_target = f"ytsearch6:{track_info.get('title', '')} {track_info.get('artist', '')} music"
    else:
        search_target = f"ytsearch6:{track_id} music"

    ydl_opts = {
        'format': 'ba[ext=m4a]/ba[ext=webm]/ba/worst',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',  # Rapid metadata retrieval without full parsing
        'socket_timeout': 6,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=False)

            entries = info.get('entries', []) if info else []
            recommendations = []

            for entry in entries:
                vid_id = entry.get('id')

                # Filter out invalid entries or self-referential track
                if not vid_id or vid_id == track_id:
                    continue

                # Leverage cache if track details exist
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
                    "stream_url": None,  # Lazy loading: resolved when track is selected
                    "duration": entry.get('duration', 0),
                    "from_cache": False
                }

                recommendations.append(rec_result)

                if len(recommendations) >= 5:
                    break

            return {"success": True, "recommendations": recommendations}

    except Exception as e:
        print(f"[RECOMMENDATION ERROR]: {e}")
        return {"success": False, "error": f"Failed to fetch recommendations: {str(e)}"}

# ---------------------------------------------------------
# Flask API Routes
# ---------------------------------------------------------

@app.route('/api/stream', methods=['GET', 'POST'])
def api_stream():
    data = request.get_json(silent=True) or request.args.to_dict()
    res = stream_and_trigger_download(data)
    return jsonify(res), 200 if res.get("success") else 400

@app.route('/api/recommendations', methods=['GET', 'POST'])
def api_recommendations():
    data = request.get_json(silent=True) or request.args.to_dict()
    res = get_recommendations(data)
    return jsonify(res), 200 if res.get("success") else 400

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "yt_dlp_ready": check_or_start_install()}), 200

# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------

if __name__ == '__main__':
    # Local development server on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
