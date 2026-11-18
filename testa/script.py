"""
Audio Streamer miniapp backend.

Called by the page through:
    POST /api/audio_streamer/search   {"query": "..."}
    POST /api/audio_streamer/resolve  {"url": "..."}

`log(...)` is injected by runner.py, so messages show up in the debug console.
yt_dlp is imported lazily inside each function so a missing package returns
the runner's "requires_installation" response instead of crashing on load.
"""
import time

AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio/best"   # no ffmpeg on Android: never ask for merges

# YouTube clients to try in order. None = yt-dlp's default selection.
CLIENT_ATTEMPTS = [None, ["android_vr"], ["ios"], ["tv"]]


def _fmt_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def search(payload):
    import yt_dlp

    query = (payload.get("query") or "").strip()
    if not query:
        return {"error": "Empty search"}

    log(f"search: {query!r}")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 15,
    }
    t0 = time.time()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch8:{query}", download=False)

    results = []
    for e in (info or {}).get("entries", []) or []:
        if not e:
            continue
        vid = e.get("id")
        thumbs = e.get("thumbnails") or []
        results.append({
            "title": e.get("title") or "(untitled)",
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": _fmt_duration(e.get("duration")),
            "url": e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else ""),
            "thumbnail": thumbs[-1]["url"] if thumbs else "",
        })
    log(f"search: {len(results)} results in {time.time() - t0:.1f}s")
    return {"results": results}


def resolve(payload):
    """Turn a page URL into a direct audio stream URL the <audio> tag can play."""
    import yt_dlp

    url = (payload.get("url") or "").strip()
    if not url:
        return {"error": "No URL"}

    last_error = None
    for clients in CLIENT_ATTEMPTS:
        label = ",".join(clients) if clients else "default"
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": AUDIO_FORMAT,
            "skip_download": True,
            "socket_timeout": 15,
        }
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}

        t0 = time.time()
        try:
            log(f"resolve: {url} (client={label})")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            stream = info.get("url")
            if not stream and info.get("requested_formats"):
                stream = info["requested_formats"][0].get("url")
            if not stream:
                raise RuntimeError("no direct stream URL in result")

            took = time.time() - t0
            log(f"resolve OK via {label} in {took:.1f}s "
                f"(ext={info.get('ext')}, abr={info.get('abr')})")
            return {
                "title": info.get("title"),
                "channel": info.get("channel") or info.get("uploader") or "",
                "duration": _fmt_duration(info.get("duration")),
                "thumbnail": info.get("thumbnail") or "",
                "stream_url": stream,
                "ext": info.get("ext"),
                "abr": info.get("abr"),
                "client": label,
                "resolve_seconds": round(took, 1),
            }
        except ModuleNotFoundError:
            raise   # let the runner offer to install the missing package
        except Exception as e:
            last_error = str(e)
            log(f"resolve failed via {label}: {last_error[:300]}")

    return {"error": last_error or "Could not resolve this URL"}
