import os
import sys
import tempfile

# Use system temp/internal data directory instead of os.getcwd()
LOCAL_LIB_DIR = os.path.join(tempfile.gettempdir(), "libs")

if not os.path.exists(LOCAL_LIB_DIR):
    os.makedirs(LOCAL_LIB_DIR, exist_ok=True)

if LOCAL_LIB_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIB_DIR)

def ensure_ytdlp_installed():
    try:
        import yt_dlp
        return True
    except ImportError:
        try:
            import pip
            # Install into writable temp/data folder
            pip.main(['install', '--target', LOCAL_LIB_DIR, 'yt-dlp', '--no-deps'])
            
            if LOCAL_LIB_DIR not in sys.path:
                sys.path.insert(0, LOCAL_LIB_DIR)

            import yt_dlp
            return True
        except Exception as e:
            print(f"Failed to auto-install yt-dlp: {e}")
            return False

def search_and_stream(params=None):
    if not ensure_ytdlp_installed():
        return {"error": "Failed to install or load yt-dlp on device."}

    import yt_dlp

    if not params or not params.get("query"):
        return {"error": "No search query provided."}

    query = params.get("query")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'default_search': 'ytsearch1',
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
                return {"error": "Could not extract audio stream URL."}

            return {
                "success": True,
                "title": title,
                "artist": uploader,
                "thumbnail": thumbnail,
                "duration": duration,
                "stream_url": stream_url
            }

    except Exception as e:
        return {"error": f"Failed to fetch stream: {str(e)}"}
