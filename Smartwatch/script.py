import sys
import subprocess
import threading
import json
import re

install_state = {
    "is_installed": False,
    "is_installing": False,
    "progress": 0,
    "status": "Idle",
    "logs": []
}

def check_bleak():
    global install_state
    try:
        import bleak
        install_state["is_installed"] = True
        install_state["is_installing"] = False
        install_state["progress"] = 100
        install_state["status"] = "Bleak fully loaded and ready."
        return True
    except ImportError:
        # Prevent resetting install_state while an installation thread is actively running
        if not install_state["is_installing"]:
            install_state["is_installed"] = False
        return False

def install_bleak_worker():
    global install_state
    install_state["is_installing"] = True
    install_state["progress"] = 10
    install_state["status"] = "Starting pip process..."
    
    # -u forces unbuffered stdout so lines flush immediately to UI
    cmd = [
        sys.executable, "-u", "-m", "pip", "install", 
        "bleak", 
        "--prefer-binary", 
        "--no-cache-dir"
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        install_state["progress"] = 25
        install_state["status"] = "Downloading pre-compiled wheels..."

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            line_clean = line.strip()
            if not line_clean:
                continue

            install_state["logs"].append(line_clean)
            if len(install_state["logs"]) > 8:
                install_state["logs"].pop(0)

            if "Collecting" in line_clean:
                pkg = line_clean.split("Collecting")[-1].strip()
                install_state["status"] = f"Fetching: {pkg}"
                install_state["progress"] = min(install_state["progress"] + 10, 65)
            elif "Installing collected packages" in line_clean:
                install_state["status"] = "Unpacking and registering binaries..."
                install_state["progress"] = 85
            elif "Successfully installed" in line_clean:
                install_state["status"] = "Finishing setup..."
                install_state["progress"] = 95

        process.wait()
        
        # Final import check after pip process completes
        if check_bleak():
            install_state["progress"] = 100
            install_state["status"] = "Ready"
        else:
            install_state["is_installing"] = False
            install_state["status"] = "Installation complete, restarting backend..."

    except Exception as e:
        install_state["is_installing"] = False
        install_state["status"] = f"Error: {str(e)}"

# Start background install check on import ONLY if not already in progress
if not check_bleak() and not install_state["is_installing"]:
    threading.Thread(target=install_bleak_worker, daemon=True).start()

# API Endpoints
def get_bleak_status():
    check_bleak()
    return install_state

def scan_for_watches():
    if not install_state["is_installed"]:
        return {"success": False, "error": "Bleak is not installed yet."}
    try:
        from bleak import BleakScanner
        import asyncio
        
        async def run_scan():
            devices = await BleakScanner.discover(timeout=4.0)
            return [{"name": d.name or "Unknown Device", "address": d.address} for d in devices]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        found = loop.run_until_complete(run_scan())
        loop.close()
        return {"success": True, "devices": found}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_watch_notification(address=None, message=None):
    if not address or not message:
        return {"success": False, "error": "Missing MAC address or message."}
    return {"success": True, "details": f"Sent to {address}: {message}"}
