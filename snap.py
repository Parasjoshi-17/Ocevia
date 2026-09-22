import subprocess
import os

out_path = r"C:\Users\kasha\.gemini\antigravity\brain\281796d2-ccac-4e8d-85b9-838117b46e89\bluemind_screenshot.png"
url = "http://127.0.0.1:5000/?city=Mumbai&day=tomorrow"
chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

subprocess.run([
    chrome,
    "--headless=new",
    "--disable-gpu",
    "--window-size=1200,1350",
    "--user-data-dir=C:\\Users\\kasha\\AppData\\Local\\Temp\\chrome_snap",
    f"--screenshot={out_path}",
    url
], check=True)
print("Screenshot captured successfully!")
