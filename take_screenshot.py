"""
take_screenshot.py - Automates headless Chrome/Edge to load BlueMindAI, trigger inquiry, and capture screenshot.
"""

import subprocess
import time
import json
import urllib.request
import base64
import os

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER_EXE = CHROME_EXE if os.path.exists(CHROME_EXE) else EDGE_EXE

ARTIFACT_DIR = r"C:\Users\kasha\.gemini\antigravity\brain\281796d2-ccac-4e8d-85b9-838117b46e89"
SCREENSHOT_PATH = os.path.join(ARTIFACT_DIR, "bluemind_screenshot.png")
DEBUG_PORT = 9223

def capture():
    target_url = "http://127.0.0.1:5000/?auto=true&city=Mumbai&day=tomorrow"
    cmd = [
        BROWSER_EXE,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",
        "--window-size=1200,1000",
        "--disable-gpu",
        target_url
    ]
    proc = subprocess.Popen(cmd)
    # Allow 4 seconds of real time for page load and live Open-Meteo fetch
    time.sleep(4)

    try:
        targets_url = f"http://127.0.0.1:{DEBUG_PORT}/json"
        with urllib.request.urlopen(targets_url, timeout=5) as resp:
            targets = json.loads(resp.read().decode())
        ws_url = targets[0]["webSocketDebuggerUrl"]

        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)

        # Call Page.captureScreenshot directly
        payload = {"id": 1, "method": "Page.captureScreenshot", "params": {"format": "png"}}
        ws.send(json.dumps(payload))
        
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                img_data = base64.b64decode(msg["result"]["data"])
                with open(SCREENSHOT_PATH, "wb") as f:
                    f.write(img_data)
                print(f"Screenshot successfully saved to {SCREENSHOT_PATH}")
                break

        ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    capture()
