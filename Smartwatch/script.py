import sys
import subprocess
import threading
import json
import re

# Installation state tracker
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
        install_state["is_installed"] = False
        return False

def install_bleak_worker():
    global install_state
    install_state["is_installing"] = True
    install_state["progress"] = 5
    install_state["status"] = "Initializing installer engine..."
    
    # Run pip install with stdout piped line-by-line
    process = subprocess.Popen(
        [sys.executable, "-m", "pip", "install", "bleak", "--no-cache-dir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in iter(process.stdout.readline, ''):
        line_clean = line.strip()
        if not line_clean:
            continue
            
        install_state["logs"].append(line_clean)
        if len(install_state["logs"]) > 10:
            install_state["logs"].pop(0)

        # Parse progress stages from stdout
        if "Collecting" in line_clean:
            pkg = line_clean.split("Collecting")[-1].strip()
            install_state["status"] = f"Downloading requirement: {pkg}"
            install_state["progress"] = min(install_state["progress"] + 15, 60)
            
        elif "Downloading" in line_clean or "%" in line_clean:
            install_state["status"] = "Downloading binaries..."
            match = re.search(r'(\d+)%', line_clean)
            if match:
                pct = int(match.group(1))
                install_state["progress"] = 20 + int(pct * 0.4)
                
        elif "Building wheels" in line_clean:
            install_state["status"] = "Compiling C extensions (this may take a minute)..."
            install_state["progress"] = 70
            
        elif "Installing collected packages" in line_clean:
            install_state["status"] = "Unpacking and linking packages..."
            install_state["progress"] = 85
            
        elif "Successfully installed" in line_clean:
            install_state["status"] = "Finalizing dependencies..."
            install_state["progress"] = 98

    process.wait()
    
    if process.returncode == 0 and check_bleak():
        install_state["progress"] = 100
        install_state["status"] = "Installation complete!"
    else:
        install_state["is_installing"] = False
        install_state["status"] = "Installation failed. Check logs."

# Initial check on startup
if not check_bleak():
    threading.Thread(target=install_bleak_worker, daemon=True).start()

# API Endpoints exposed to Operat
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
        return {"success": False, "error": "Missing target MAC address or message text."}
    return {"success": True, "details": f"Alert target set for {address}: {message}"}
