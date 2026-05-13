import keyboard
import pyperclip
import requests
import os
from plyer import notification

def on_hotkey():
    try:
        text = pyperclip.paste()
        if not text or not text.strip():
            return
            
        print(f"Triggered for: {text[:50]}...")
        
        ai_name = os.environ.get("AI_NAME", "Aether")
        notification.notify(
            title=ai_name,
            message="Analyzing clipboard...",
            app_name="Aether Magic Clipboard",
            timeout=2
        )
        
        resp = requests.post(
            "http://127.0.0.1:8000/api/quick-explain", 
            json={"text": text},
            timeout=15
        )
        
        if resp.status_code == 200:
            result = resp.json().get("explanation", "Could not analyze text.")
            
            # plyer notifications have message length limits on Windows (typically ~256 chars)
            if len(result) > 250:
                result = result[:247] + "..."
                
            notification.notify(
                title="Aether Explanation",
                message=result,
                app_name="Aether Magic Clipboard",
                timeout=10
            )
        else:
            print(f"Failed with {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Magic Clipboard Listener active. Press Ctrl+Shift+Space anywhere to summon Aether.")
    # Register global hotkey
    keyboard.add_hotkey('ctrl+shift+space', on_hotkey)
    # Block forever waiting for hotkey
    keyboard.wait()
