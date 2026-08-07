import os
import sys
import tempfile
import threading
import zipfile
import urllib.request

LOCAL_LIB_DIR = os.path.join(tempfile.gettempdir(), "libs")
if not os.path.exists(LOCAL_LIB_DIR):
    os.makedirs(LOCAL_LIB_DIR, exist_ok=True)

if LOCAL_LIB_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIB_DIR)

INSTALLATION_STATUS = {
    "is_installed": False,
    "is_installing": False,
    "message": "Initializing...",
    "error": None
}

def install_ytdlp_background():
    global INSTALLATION_STATUS
    INSTALLATION_STATUS["is_installing"] = True
    INSTALLATION_STATUS["message"] = "Downloading yt-dlp..."

    try:
        import pip
        pip.main(['install', '--target', LOCAL_LIB_DIR, 'yt-dlp', '--no-deps', '--quiet'])
        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
        return
    except Exception:
        INSTALLATION_STATUS["message"] = "Pip failed. Downloading wheel archive..."

    try:
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        target_zip = os.path.join(LOCAL_LIB_DIR, "yt_dlp_zip.zip")
        urllib.request.urlretrieve(url, target_zip)
        
        with zipfile.ZipFile(target_zip, 'r') as zip_ref:
            zip_ref.extractall(LOCAL_LIB_DIR)

        if LOCAL_LIB_DIR not in sys.path:
            sys.path.insert(0, LOCAL_LIB_DIR)

        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp Ready!"
    except Exception as e2:
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["error"] = f"Installation error: {str(e2)}"

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
    return INSTALLATION_STATUS

def search_and_stream(params=None):
    if not check_or_start_install():
        return {"error": f"yt-dlp not ready: {INSTALLATION_STATUS['message']}"}

    import yt_dlp

    if not params or not params.get("query"):
        return {"error": "No query provided."}

    query = params.get("query")

    # Request low-bitrate format to keep stream sizes under ~1.5MB
    ydl_opts = {
        'format': 'worstaudio[ext=webm]/worstaudio[ext=m4a]/worstaudio/worst',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            video = info['entries'][0] if 'entries' in info and info['entries'] else info

            stream_url = video.get('url')
            if not stream_url:
                return {"error": "No streamable audio found."}

            return {
                "success": True,
                "title": video.get('title', 'Unknown Title'),
                "artist": video.get('uploader', 'Unknown Artist'),
                "thumbnail": video.get('thumbnail', ''),
                "duration": video.get('duration', 0),
                "stream_url": stream_url
            }

    except Exception as e:
        return {"error": f"Stream error: {str(e)}"}
