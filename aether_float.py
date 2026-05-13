"""
Aether Floating Widget — Liquid Glass / Expandable Compact HUD
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
import asyncio
import json
import os
import websocket
from datetime import datetime

WS_URL = "ws://127.0.0.1:8000/ws/chat"

# Liquid Glass Theme
TRANS_COLOR = "#000001"    # Magic key color for true transparency
GLASS_COLOR = "#F8FAFC"    # Soft white for frosted look
BORDER_COLOR = "#E2E8F0"
TEXT_COLOR = "#1E293B"
ACCENT_COLOR = "#3B8BD4"
HOVER_COLOR = "#F1F5F9"

class AetherFloat:
    def __init__(self):
        self.ai_name = os.environ.get("AI_NAME", "Aether")
        self.root = tk.Tk()
        self.root.title(f"{self.ai_name} Widget")
        
        # State
        self.mode = "compact"
        self.target_width = 180
        self.target_height = 60
        self.current_width = 180
        self.current_height = 60
        
        # Window Setup
        self.root.geometry(f"{self.current_width}x{self.current_height}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Liquid Glass Effect (Windows specific)
        self.root.configure(bg=TRANS_COLOR)
        self.root.attributes("-transparentcolor", TRANS_COLOR)
        self.root.attributes("-alpha", 0.95) # Slight translucency
        
        self._reposition()

        self.ws = None
        self.ws_thread = None
        
        self._build_ui()
        self._connect_ws()
        self._animate_size()

    def _reposition(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Keep anchored to the bottom right
        x = sw - self.current_width - 40
        y = sh - self.current_height - 60
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def _build_ui(self):
        # 1. Base Canvas for rounded corners
        self.canvas = tk.Canvas(self.root, bg=TRANS_COLOR, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._update_bg_shape()
        
        # Drag bindings
        self.canvas.bind("<Button-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)

        # 2. Main UI Container
        self.ui_frame = tk.Frame(self.root, bg=GLASS_COLOR)
        self.ui_frame.place(x=10, y=10, width=self.current_width-20, height=self.current_height-20)
        
        # --- STATE: COMPACT (Main Menu) ---
        self.btn_frame = tk.Frame(self.ui_frame, bg=GLASS_COLOR)
        
        self.btn_voice = self._make_btn(self.btn_frame, "🎙", self._to_voice_mode)
        self.btn_voice.pack(side="left", padx=5)
        
        self.btn_text = self._make_btn(self.btn_frame, "💬", self._to_text_mode)
        self.btn_text.pack(side="left", padx=5)
        
        self.btn_close = self._make_btn(self.btn_frame, "✖", self.root.destroy)
        self.btn_close.pack(side="left", padx=5)
        
        # Start in compact mode
        self.btn_frame.place(relx=0.5, rely=0.5, anchor="center")

        # --- STATE: TEXT MODE ---
        self.text_frame = tk.Frame(self.ui_frame, bg=GLASS_COLOR)
        
        t_header = tk.Frame(self.text_frame, bg=GLASS_COLOR)
        t_header.pack(fill="x", pady=(0, 5))
        tk.Label(t_header, text=self.ai_name, font=("Segoe UI", 12, "bold"), bg=GLASS_COLOR, fg=ACCENT_COLOR).pack(side="left")
        tk.Button(t_header, text="↙ Shrink", bg=GLASS_COLOR, fg=TEXT_COLOR, bd=0, cursor="hand2", font=("Segoe UI", 9), command=self._to_compact).pack(side="right")
        
        self.chat = scrolledtext.ScrolledText(self.text_frame, bg="#FFFFFF", fg=TEXT_COLOR, font=("Segoe UI", 10), bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR, state="disabled")
        self.chat.pack(fill="both", expand=True, pady=2)
        self.chat.tag_configure("user", foreground=ACCENT_COLOR, justify="right")
        self.chat.tag_configure("aether", foreground=TEXT_COLOR)

        inp_f = tk.Frame(self.text_frame, bg=GLASS_COLOR)
        inp_f.pack(fill="x", pady=(5,0))
        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(inp_f, textvariable=self.input_var, bg="#FFFFFF", fg=TEXT_COLOR, font=("Segoe UI", 10), bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR)
        self.input_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0,5))
        self.input_entry.bind("<Return>", self._send)
        tk.Button(inp_f, text="Send", bg=ACCENT_COLOR, fg="white", bd=0, cursor="hand2", padx=10, command=self._send).pack(side="right", fill="y")

        # --- STATE: VOICE MODE ---
        self.voice_frame = tk.Frame(self.ui_frame, bg=GLASS_COLOR)
        
        v_header = tk.Frame(self.voice_frame, bg=GLASS_COLOR)
        v_header.pack(fill="x")
        tk.Label(v_header, text="Voice Control", font=("Segoe UI", 11, "bold"), bg=GLASS_COLOR, fg=TEXT_COLOR).pack(side="left")
        tk.Button(v_header, text="↙ Shrink", bg=GLASS_COLOR, fg=TEXT_COLOR, bd=0, cursor="hand2", font=("Segoe UI", 9), command=self._to_compact).pack(side="right")
        
        v_btns = tk.Frame(self.voice_frame, bg=GLASS_COLOR)
        v_btns.pack(expand=True)
        self.mic_muted = False
        self.vis_active = False
        
        self.btn_mic = tk.Button(v_btns, text="🎙 Mute Mic", bg="#FFFFFF", fg=TEXT_COLOR, bd=1, relief="solid", cursor="hand2", command=self._toggle_mic)
        self.btn_mic.pack(side="left", padx=5, ipady=4, ipadx=8)
        self.btn_vis = tk.Button(v_btns, text="👁 Screen Vision", bg="#FFFFFF", fg=TEXT_COLOR, bd=1, relief="solid", cursor="hand2", command=self._toggle_vis)
        self.btn_vis.pack(side="left", padx=5, ipady=4, ipadx=8)

    def _make_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, font=("Segoe UI", 14), bg=GLASS_COLOR, fg=TEXT_COLOR,
                         bd=0, cursor="hand2", activebackground=HOVER_COLOR, command=cmd,
                         width=2, height=1)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1,
            x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r,
            x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r,
            x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _update_bg_shape(self):
        self.canvas.delete("all")
        # Draw the rounded "Glass" background
        self._create_rounded_rect(0, 0, self.current_width, self.current_height, 24, fill=GLASS_COLOR, outline=BORDER_COLOR, width=1)

    # --- UI STATE TRANSITIONS ---
    def _to_compact(self):
        self.mode = "compact"
        self.target_width = 180
        self.target_height = 60
        self.text_frame.place_forget()
        self.voice_frame.place_forget()
        
    def _to_text_mode(self):
        self.mode = "text"
        self.target_width = 320
        self.target_height = 400
        self.btn_frame.place_forget()
        self.voice_frame.place_forget()
        
    def _to_voice_mode(self):
        self.mode = "voice"
        self.target_width = 240
        self.target_height = 100
        self.btn_frame.place_forget()
        self.text_frame.place_forget()
        
    def _animate_size(self):
        # Smooth interpolation
        step_w = (self.target_width - self.current_width) * 0.25
        step_h = (self.target_height - self.current_height) * 0.25
        
        if abs(step_w) > 0.5 or abs(step_h) > 0.5:
            self.current_width += step_w
            self.current_height += step_h
            self.root.geometry(f"{int(self.current_width)}x{int(self.current_height)}")
            self._reposition()
            self._update_bg_shape()
            self.ui_frame.place(width=self.current_width-20, height=self.current_height-20)
        else:
            self.current_width = self.target_width
            self.current_height = self.target_height
            
            # Show the correct inner frame when the window finishes expanding
            if self.mode == "compact":
                self.btn_frame.place(relx=0.5, rely=0.5, anchor="center")
            elif self.mode == "text":
                self.text_frame.place(x=0, y=0, relwidth=1, relheight=1)
            elif self.mode == "voice":
                self.voice_frame.place(x=0, y=0, relwidth=1, relheight=1)

        self.root.after(16, self._animate_size) # ~60fps

    # --- ACTIONS ---
    def _toggle_mic(self):
        self.mic_muted = not self.mic_muted
        self.btn_mic.config(text="🎙 Unmute" if self.mic_muted else "🎙 Mute", bg="#FEE2E2" if self.mic_muted else "#FFFFFF")
        if self.ws:
            try:
                self.ws.send(json.dumps({"type": "control", "action": "toggle_mic", "state": self.mic_muted}))
            except Exception:
                pass

    def _toggle_vis(self):
        self.vis_active = not self.vis_active
        self.btn_vis.config(text="👁 Stop Vis" if self.vis_active else "👁 Screen Vision", bg="#DCFCE7" if self.vis_active else "#FFFFFF")
        if self.ws:
            try:
                self.ws.send(json.dumps({"type": "control", "action": "toggle_vis", "state": self.vis_active}))
            except Exception:
                pass

    def _start_drag(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _drag(self, e):
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _add_message(self, sender: str, text: str, tag: str):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{sender}  ", "time")
        self.chat.insert("end", f"{text}\n\n", "aether" if tag == "aether" else "user")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _send(self, event=None):
        text = self.input_var.get().strip()
        if not text or not self.ws:
            return
        self._add_message("You", text, "user")
        self.input_var.set("")
        try:
            self.ws.send(json.dumps({"message": text}))
        except Exception as e:
            self._add_message("System", f"Send failed: {e}", "aether")

    # --- WEBSOCKET LOGIC ---
    def _connect_ws(self):
        def run():
            try:
                self.ws = websocket.WebSocketApp(
                    WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever()
            except Exception:
                pass

        self.ws_thread = threading.Thread(target=run, daemon=True)
        self.ws_thread.start()

    def _on_open(self, ws):
        pass # Could add a subtle green indicator

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data["type"] == "chunk":
                if not hasattr(self, "_current_response"):
                    self._current_response = ""
                self._current_response += data["content"]
            elif data["type"] == "done":
                response = getattr(self, "_current_response", "")
                self._current_response = ""
                if response:
                    self.root.after(0, lambda r=response: self._add_message("Ather", r, "aether"))
        except Exception:
            pass

    def _on_error(self, ws, error):
        pass

    def _on_close(self, ws, code, msg):
        self.root.after(3000, self._connect_ws)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AetherFloat()
    app.run()
