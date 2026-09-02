import os
import sys
import threading
import zipfile
import urllib.request
import importlib

# 1. Safe Dynamic Import for Chaquopy / Standalone Execution
APP_FILES_DIR = None

try:
    chaquopy_mod = importlib.import_module("com.chaquopy.python")
    Python = getattr(chaquopy_mod, "Python")
    context = Python.getPlatform().getApplication()
    APP_FILES_DIR = str(context.getFilesDir().getAbsolutePath())
except (ImportError, ModuleNotFoundError, AttributeError, Exception):
    # Fallback when running inside standard Python web host or app runner environment
    APP_FILES_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Configure Storage Paths
LOCAL_LIB_DIR = os.path.join(APP_FILES_DIR, "libs")
DOWNLOAD_DIR = os.path.join(APP_FILES_DIR, "audio_downloads")

for folder in [LOCAL_LIB_DIR, DOWNLOAD_DIR]:
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

    # Method 1: In-Process Installation via runpy (Chaquopy Safe)
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

    # Method 2: Direct Zip Archive Extraction Fallback
    try:
        INSTALLATION_STATUS["message"] = "Downloading zip archive..."
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        target_zip = os.path.join(LOCAL_LIB_DIR, "yt_dlp_zip.zip")
        urllib.request.urlretrieve(url, target_zip)
        
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
    if not check_or_start_install():
        return {"error": f"yt-dlp not ready: {INSTALLATION_STATUS['message']}"}

    import yt_dlp

    if not params or not params.get("query"):
        return {"error": "No query provided."}

    query = params.get("query")

    ydl_opts = {
        'format': 'worstaudio[ext=m4a]/worstaudio[ext=webm]/worstaudio/worst',
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
            ext = video.get('ext', 'm4a')
            file_name = f"{video_id}.{ext}"
            file_path = os.path.join(DOWNLOAD_DIR, file_name)

            is_saved = os.path.exists(file_path)

            if not stream_url and not is_saved:
                return {"error": "No playable stream found."}

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
    import yt_dlp
    ydl_opts = {
        'format': 'worstaudio[ext=m4a]/worstaudio[ext=webm]/worstaudio/worst',
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
    if not params or not params.get("file_name"):
        return {"is_saved": False}
    file_path = os.path.join(DOWNLOAD_DIR, params.get("file_name"))
    return {"is_saved": os.path.exists(file_path)}

def get_local_audio(params=None):
    if not params or not params.get("file_name"):
        return {"error": "No file name provided."}
    file_name = params.get("file_name")
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if os.path.exists(file_path):
        return {"file_path": file_path, "is_saved": True}
    return {"error": "File not found.", "is_saved": False}

def delete_local_file(params=None):
    if not params or not params.get("file"):
        return {"error": "No file name provided."}
    
    file_path = os.path.join(DOWNLOAD_DIR, params.get("file"))
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"success": True}
        except Exception as e:
            return {"error": f"Failed to delete file: {str(e)}"}
    return {"error": "File not found."}
