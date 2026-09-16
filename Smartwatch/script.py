import os
import sys
import threading
import zipfile
import urllib.request
import urllib.parse
import importlib
import json
import re
import asyncio

# 1. Safe Dynamic Import for Chaquopy / Standalone Execution
APP_FILES_DIR = None

try:
    chaquopy_mod = importlib.import_module("com.chaquopy.python")
    Python = getattr(chaquopy_mod, "Python")
    context = Python.getPlatform().getApplication()
    APP_FILES_DIR = str(context.getFilesDir().getAbsolutePath())
except (ImportError, ModuleNotFoundError, AttributeError, Exception):
    APP_FILES_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Configure Storage Paths
LOCAL_LIB_DIR = os.path.join(APP_FILES_DIR, "libs")
os.makedirs(LOCAL_LIB_DIR, exist_ok=True)

if LOCAL_LIB_DIR not in sys.path:
    sys.path.insert(0, LOCAL_LIB_DIR)

INSTALLATION_STATUS = {
    "is_installed": False,
    "is_installing": False,
    "message": "Initializing...",
    "error": None
}

# 3. Dynamic Package Management for Bleak
def install_bleak_background():
    global INSTALLATION_STATUS
    INSTALLATION_STATUS["is_installing"] = True
    INSTALLATION_STATUS["message"] = "Installing bleak BLE library..."

    # Method 1: In-Process Installation via runpy (Chaquopy Safe)
    try:
        import runpy
        sys.argv = ['pip', 'install', '--target', LOCAL_LIB_DIR, 'bleak', '--no-deps', '--quiet']
        runpy.run_module('pip', run_name='__main__')
        
        importlib.invalidate_caches()
        import bleak
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "Bleak BLE Engine Ready!"
        return
    except SystemExit as e:
        if e.code == 0:
            importlib.invalidate_caches()
            INSTALLATION_STATUS["is_installed"] = True
            INSTALLATION_STATUS["is_installing"] = False
            INSTALLATION_STATUS["message"] = "Bleak BLE Engine Ready!"
            return
    except Exception as e1:
        print(f"[RUNPY PIP FAILED]: {e1}")

    # Method 2: Direct Zip Archive Extraction Fallback (PyPI Wheel/Zip)
    try:
        INSTALLATION_STATUS["message"] = "Downloading bleak package archive..."
        url = "https://files.pythonhosted.org/packages/source/b/bleak/bleak-0.22.2.tar.gz"
        target_archive = os.path.join(LOCAL_LIB_DIR, "bleak_archive.tar.gz")
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as response, open(target_archive, 'wb') as out_file:
            out_file.write(response.read())
        
        # Extract archive fallback
        import tarfile
        with tarfile.open(target_archive, 'r:gz') as tar_ref:
            tar_ref.extractall(LOCAL_LIB_DIR)

        if os.path.exists(target_archive):
            os.remove(target_archive)

        importlib.invalidate_caches()
        import bleak
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["message"] = "Bleak BLE Engine Ready!"
    except Exception as e2:
        INSTALLATION_STATUS["is_installing"] = False
        INSTALLATION_STATUS["is_installed"] = False
        INSTALLATION_STATUS["error"] = str(e2)
        INSTALLATION_STATUS["message"] = f"BLE Engine error: {str(e2)}"

def check_or_start_bleak_install():
    global INSTALLATION_STATUS
    try:
        import bleak
        INSTALLATION_STATUS["is_installed"] = True
        INSTALLATION_STATUS["message"] = "Ready"
        return True
    except ImportError:
        if not INSTALLATION_STATUS["is_installing"]:
            thread = threading.Thread(target=install_bleak_background)
            thread.daemon = True
            thread.start()
        return False

def get_bleak_status(params=None):
    check_or_start_bleak_install()
    return {
        "success": True,
        "is_installed": INSTALLATION_STATUS.get("is_installed", False),
        "is_installing": INSTALLATION_STATUS.get("is_installing", False),
        "message": INSTALLATION_STATUS.get("message", "Unknown"),
        "error": INSTALLATION_STATUS.get("error")
    }

# 4. Watch 9 BLE Control & Communications
def scan_for_watches(params=None):
    if not check_or_start_bleak_install():
        return {"success": False, "error": f"BLE engine not ready: {INSTALLATION_STATUS['message']}"}

    from bleak import BleakScanner

    async def _scan():
        devices = await BleakScanner.discover(timeout=5.0)
        found = []
        for d in devices:
            name = d.name or "Unknown Device"
            found.append({"name": name, "address": d.address})
        return found

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(_scan())
        loop.close()
        return {"success": True, "devices": results}
    except Exception as e:
        return {"success": False, "error": f"Scan failed: {str(e)}"}

def send_watch_notification(params=None):
    if not check_or_start_bleak_install():
        return {"success": False, "error": "BLE engine not ready."}

    if not params or not params.get("address") or not params.get("message"):
        return {"success": False, "error": "MAC address and message are required."}

    mac_address = params.get("address")
    message = params.get("message")
    
    # Nordic UART Service TX Characteristic (used by Watch 9 / Ultra 9)
    NUS_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    from bleak import BleakClient

    async def _send():
        async with BleakClient(mac_address) as client:
            if not client.is_connected:
                return False
            
            # Watch 9 Byte Frame: [Header 0xAB, 0x00, 0x03 (Alert Cmd), 0x01, Payload Length] + String
            msg_bytes = message.encode('utf-8')
            payload = bytearray([0xAB, 0x00, 0x03, 0x01, len(msg_bytes)]) + msg_bytes
            await client.write_gatt_char(NUS_TX_UUID, payload)
            return True

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(_send())
        loop.close()
        if success:
            return {"success": True, "message": f"Alert sent to {mac_address}"}
        return {"success": False, "error": "Could not establish BLE GATT connection."}
    except Exception as e:
        return {"success": False, "error": f"BLE transmission failed: {str(e)}"}

