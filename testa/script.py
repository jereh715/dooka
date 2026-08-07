import os
import sys
import tempfile
import threading
import zipfile
import urllib.request

# Setup writable storage paths
BASE_TEMP = tempfile.gettempdir()
LOCAL_LIB_DIR = os.path.join(BASE_TEMP, "libs")
DOWNLOAD_DIR = os.path.join(BASE_TEMP, "audio_downloads")

for folder in [LOCAL_LIB_DIR, DOWNLOAD_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

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
        INSTALLATION_STATUS["message"] = "Downloading wheel archive..."

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

def stream_and_trigger_download(params=None):
    """
    Returns immediate stream URL for playback AND triggers 
    a silent background thread to download the low-quality track.
    """
    if not check_or_start_install():
        return {"error": f"yt-dlp not ready: {INSTALLATION_STATUS['message']}"}

    import yt_dlp

    if not params or not params.get("query"):
        return {"error": "No query provided."}

    query = params.get("query")

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

            video_id = video.get('id')
            stream_url = video.get('url')
            ext = video.get('ext', 'webm')
            file_name = f"{video_id}.{ext}"
            file_path = os.path.join(DOWNLOAD_DIR, file_name)

            # Check if file already exists locally
            is_saved = os.path.exists(file_path)

            if not stream_url and not is_saved:
                return {"error": "No playable stream found."}

            # Trigger silent download in background if not already saved
            if not is_saved:
                thread = threading.Thread(target=_silent_download_worker, args=(query, file_path))
                thread.daemon = True
                thread.start()

            return {
                "success": True,
                "id": video_id,
                "title": video.get('title', 'Unknown Title'),
                "artist": video.get('uploader', 'Unknown Artist'),
                "thumbnail": video.get('thumbnail', ''),
                "stream_url": stream_url,
                "file_name": file_name,
                "is_saved": is_saved
            }

    except Exception as e:
        return {"error": f"Extraction error: {str(e)}"}

def _silent_download_worker(query, target_path):
    """Worker function for silent background downloading."""
    import yt_dlp
    ydl_opts = {
        'format': 'worstaudio[ext=webm]/worstaudio[ext=m4a]/worstaudio/worst',
        'outtmpl': target_path,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])
    except Exception as e:
        print(f"Background download failed for {query}: {e}")

def check_file_status(params=None):
    """Polls whether the silent background download completed."""
    if not params or not params.get("file_name"):
        return {"is_saved": False}
    file_path = os.path.join(DOWNLOAD_DIR, params.get("file_name"))
    return {"is_saved": os.path.exists(file_path)}

def delete_local_file(params=None):
    """Deletes the locally downloaded file."""
    if not params or not params.get("file"):
        return {"error": "No file name provided."}
    
    file_path = os.path.join(DOWNLOAD_DIR, params.get("file"))
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"success": True}
    return {"error": "File not found."}
