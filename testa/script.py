import os
import sys
import tempfile
import threading
import zipfile
import urllib.request

# Setup writable directory
LOCAL_LIB_DIR = os.path.join(tempfile.gettempdir(), "libs")
if not os.path.exists(LOCAL_LIB_DIR):
    os.makedirs(LOCAL_LIB_DIR, exist_ok=True)

if LOCAL_LIB_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIB_DIR)

# Global status tracking
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
        # Attempt 1: Standard pip install
        import pip
        pip.main(['install', '--target', LOCAL_LIB_DIR, 'yt-dlp', '--no-deps', '--quiet'])
        
        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp successfully installed!"
        return
    except Exception as e1:
        INSTALLATION_STATUS["message"] = "Pip failed. Falling back to direct wheel download..."

    try:
        # Attempt 2: Fallback download directly from PyPI/GitHub if pip module fails
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        target_zip = os.path.join(LOCAL_LIB_DIR, "yt_dlp_zip.zip")
        
        urllib.request.urlretrieve(url, target_zip)
        
        # Extract zip/tar package into libs directory
        with zipfile.ZipFile(target_zip, 'r') as zip_ref:
            zip_ref.extractall(LOCAL_LIB_DIR)

        if LOCAL_LIB_DIR not in sys.path:
            sys.path.insert(0, LOCAL_LIB_DIR)

        import yt_dlp
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "yt-dlp downloaded and loaded successfully!"
    except Exception as e2:
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["error"] = f"Installation error: {str(e2)}"
        INSTALLATION_STATUS["message"] = "Installation failed."

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
    """API endpoint to query installation status from JS"""
    check_or_start_install()
    return INSTALLATION_STATUS

def search_and_stream(params=None):
    if not check_or_start_install():
        return {
            "error": f"yt-dlp is not ready. Current status: {INSTALLATION_STATUS['message']}"
        }

    import yt_dlp

    if not params or not params.get("query"):
        return {"error": "No search query provided."}

    query = params.get("query")

    # Mobile-optimized YoutubeDL options
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
            else:
                video = info

            stream_url = video.get('url')
            title = video.get('title', 'Unknown Title')
            uploader = video.get('uploader', 'Unknown Artist')
            thumbnail = video.get('thumbnail', '')
            duration = video.get('duration', 0)

            if not stream_url:
                return {"error": "No streamable audio found for this query."}

            return {
                "success": True,
                "title": title,
                "artist": uploader,
                "thumbnail": thumbnail,
                "duration": duration,
                "stream_url": stream_url
            }

    except Exception as e:
        return {"error": f"Stream error: {str(e)}"}
