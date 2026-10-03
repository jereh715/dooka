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
# 1. Chaquopy Native Android Imports & Global Context
# ---------------------------------------------------------
APP_FILES_DIR = None
ANDROID_CONTEXT = None
MEDIA_NOTIF_MANAGER = None

try:
    chaquopy_mod = importlib.import_module("com.chaquopy.python")
    Python = getattr(chaquopy_mod, "Python")
    ANDROID_CONTEXT = Python.getPlatform().getApplication()
    APP_FILES_DIR = str(ANDROID_CONTEXT.getFilesDir().getAbsolutePath())
except (ImportError, ModuleNotFoundError, AttributeError, Exception):
    APP_FILES_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------
# 2. Pure-Python Android Media Notification Engine
# ---------------------------------------------------------
class PurePythonMediaNotification:
    """
    Directly invokes Android's Java NotificationManager, MediaSession,
    and MediaMetadata APIs via Chaquopy without native Java source files.
    """
    def __init__(self, context):
        self.context = context
        self.channel_id = "chaquopy_media_channel"
        self.notif_id = 1001
        self.session = None
        self.notification_manager = None
        
        if self.context:
            try:
                # Import Android Java Classes dynamically via Chaquopy
                from android.app import NotificationManager, NotificationChannel
                from android.os import Build
                from android.media.session import MediaSession, PlaybackState
                from android.media import MediaMetadata

                self.NotificationManagerClass = NotificationManager
                self.NotificationChannelClass = NotificationChannel
                self.MediaSessionClass = MediaSession
                self.PlaybackStateClass = PlaybackState
                self.MediaMetadataClass = MediaMetadata
                self.BuildClass = Build

                self.notification_manager = self.context.getSystemService(Context.NOTIFICATION_SERVICE)
                
                # Create Media Session
                self.session = self.MediaSessionClass(self.context, "ChaquopyAudioSession")
                self.session.setActive(True)

                self._create_channel()
            except Exception as e:
                print(f"[ANDROID NOTIF INIT ERROR]: {e}")

    def _create_channel(self):
        try:
            if self.BuildClass.VERSION.SDK_INT >= 26:  # Android 8.0 OREO
                channel = self.NotificationChannelClass(
                    self.channel_id,
                    "Audio Playback Controls",
                    self.NotificationManagerClass.IMPORTANCE_LOW
                )
                channel.setDescription("Shows active track, artwork, and progression")
                self.notification_manager.createNotificationChannel(channel)
        except Exception as e:
            print(f"[CHANNEL CREATION ERROR]: {e}")

    def update_notification(self, title, artist, thumbnail_url, duration_sec, is_playing=True, position_sec=0):
        if not self.context or not self.notification_manager:
            return

        def _bg_post():
            try:
                from android.graphics import BitmapFactory
                from androidx.core.app import NotificationCompat
                from android.media import MediaMetadata
                from android.media.session import PlaybackState

                # Fetch bitmap artwork from thumbnail URL
                album_art = None
                if thumbnail_url:
                    try:
                        req = urllib.request.Request(thumbnail_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            img_bytes = resp.read()
                            album_art = BitmapFactory.decodeByteArray(img_bytes, 0, len(img_bytes))
                    except Exception as ie:
                        print(f"[ARTWORK FETCH ERROR]: {ie}")

                # Update Media Metadata
                meta_builder = self.MediaMetadataClass.Builder()
                meta_builder.putString(self.MediaMetadataClass.METADATA_KEY_TITLE, title)
                meta_builder.putString(self.MediaMetadataClass.METADATA_KEY_ARTIST, artist)
                meta_builder.putLong(self.MediaMetadataClass.METADATA_KEY_DURATION, int(duration_sec * 1000))
                
                if album_art:
                    meta_builder.putBitmap(self.MediaMetadataClass.METADATA_KEY_ALBUM_ART, album_art)
                
                self.session.setMetadata(meta_builder.build())

                # Update Playback State & Progress Bar
                state_code = self.PlaybackStateClass.STATE_PLAYING if is_playing else self.PlaybackStateClass.STATE_PAUSED
                state_builder = self.PlaybackStateClass.Builder()
                state_builder.setState(state_code, int(position_sec * 1000), 1.0)
                state_builder.setActions(
                    self.PlaybackStateClass.ACTION_PLAY | 
                    self.PlaybackStateClass.ACTION_PAUSE | 
                    self.PlaybackStateClass.ACTION_SEEK_TO
                )
                self.session.setPlaybackState(state_builder.build())

                # Construct Android Notification
                builder = NotificationCompat.Builder(self.context, self.channel_id)
                builder.setContentTitle(title)
                builder.setContentText(artist)
                builder.setSmallIcon(17301540)  # android.R.drawable.ic_media_play
                
                if album_art:
                    builder.setLargeIcon(album_art)

                # Bind MediaSession Token to Notification Style
                style = NotificationCompat.MediaStyle()
                style.setMediaSession(self.session.getSessionToken())
                builder.setStyle(style)
                
                builder.setOngoing(is_playing)
                builder.setOnlyAlertOnce(True)

                self.notification_manager.notify(self.notif_id, builder.build())
            except Exception as ex:
                print(f"[NOTIFICATION POST ERROR]: {ex}")

        threading.Thread(target=_bg_post, daemon=True).start()

    def update_progress(self, position_sec, is_playing=True):
        if not self.context or not self.session:
            return
        try:
            state_code = self.PlaybackStateClass.STATE_PLAYING if is_playing else self.PlaybackStateClass.STATE_PAUSED
            state_builder = self.PlaybackStateClass.Builder()
            state_builder.setState(state_code, int(position_sec * 1000), 1.0)
            state_builder.setActions(
                self.PlaybackStateClass.ACTION_PLAY | 
                self.PlaybackStateClass.ACTION_PAUSE | 
                self.PlaybackStateClass.ACTION_SEEK_TO
            )
            self.session.setPlaybackState(state_builder.build())
        except Exception as e:
            print(f"[PROGRESS UPDATE ERROR]: {e}")

    def dismiss(self):
        if self.notification_manager:
            try:
                self.notification_manager.cancel(self.notif_id)
            except Exception as e:
                print(f"[DISMISS ERROR]: {e}")

if ANDROID_CONTEXT:
    MEDIA_NOTIF_MANAGER = PurePythonMediaNotification(ANDROID_CONTEXT)

# ---------------------------------------------------------
# 3. Storage Paths & Thread Locks
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
# 4. Dynamic Package Management for yt-dlp
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
# 5. Thread-Safe Cache Helpers
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
# 6. Audio Streaming, Caching & Notification Invocation
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

    # Post native media notification
    if result and result.get("success") and MEDIA_NOTIF_MANAGER:
        MEDIA_NOTIF_MANAGER.update_notification(
            title=result.get("title", "Unknown"),
            artist=result.get("artist", "Unknown"),
            thumbnail_url=result.get("thumbnail"),
            duration_sec=result.get("duration", 0),
            is_playing=True,
            position_sec=0
        )

    return result

def update_playback_progress(params=None):
    """
    Call this periodically from your Python/Toga audio timer loop 
    to update the notification slider and state.
    """
    if not params:
        return {"success": False, "error": "No parameters provided."}

    position = params.get("position", 0)
    is_playing = params.get("is_playing", True)

    if MEDIA_NOTIF_MANAGER:
        MEDIA_NOTIF_MANAGER.update_progress(position, is_playing)
    return {"success": True}

def dismiss_media_notification(params=None):
    if MEDIA_NOTIF_MANAGER:
        MEDIA_NOTIF_MANAGER.dismiss()
    return {"success": True}

# ---------------------------------------------------------
# 7. Recommendation Engine (Flat Extraction)
# ---------------------------------------------------------
def get_recommendations(params=None):
    if not params or not (params.get("id") or params.get("query")):
        return {"success": False, "error": "Track ID or Query required."}

    track_id = params.get("id")
    query = params.get("query", "").strip()

    if not check_or_start_install():
        return {"success": False, "error": "yt-dlp engine not ready."}

    import yt_dlp

    cache = _load_cache()

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
        'extract_flat': 'in_playlist',
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
# 8. Synchronized Lyrics Fetcher
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
