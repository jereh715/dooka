import os
import platform
import sys

def get_sys_info(params=None):
    """
    Returns general operating system and environment diagnostics.
    Triggered via GET/POST to /runner/api/sys_diag/get_sys_info
    """
    return {
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "processor": platform.processor() or "Mobile / ARM Architecture",
        "current_dir": os.getcwd()
    }

def get_storage_stats(params=None):
    """
    Calculates storage usage inside the current execution path.
    Triggered via GET/POST to /runner/api/sys_diag/get_storage_stats
    """
    try:
        # Check storage space on the internal volume
        stats = os.statvfs(".")
        free_bytes = stats.f_bavail * stats.f_frsize
        total_bytes = stats.f_blocks * stats.f_frsize
        used_bytes = total_bytes - free_bytes

        return {
            "total_gb": round(total_bytes / (1024**3), 2),
            "used_gb": round(used_bytes / (1024**3), 2),
            "free_gb": round(free_bytes / (1024**3), 2),
            "used_percent": round((used_bytes / total_bytes) * 100, 1)
        }
    except Exception as e:
        return {"error": f"Storage query unavaliable on platform: {str(e)}"}

def calculate_hash(params=None):
    """
    Demonstrates processing custom input data sent from index.html.
    Triggered via POST to /runner/api/sys_diag/calculate_hash
    """
    import hashlib
    
    text = params.get("input_text", "") if params else ""
    if not text:
        return {"error": "No text provided to hash."}
        
    hashed_value = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return {
        "original": text,
        "sha256": hashed_value
    }
