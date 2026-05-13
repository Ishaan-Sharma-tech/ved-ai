import { useState, useEffect, useRef, useCallback } from "react"
import ReactMarkdown from "react-markdown"
import { Room, RoomEvent, Track } from "livekit-client"
import FileUpload from "./components/FileUpload"

const HOST = window.location.hostname || "127.0.0.1"
const WS_URL = `ws://${HOST}:8000/ws/chat`
const API_URL = `http://${HOST}:8000`

function formatTime() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function Message({ msg }) {
  const isUser = msg.role === "user"
  return (
    <div style={{
      display: "flex", justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: 16, gap: 12, width: "100%",
    }}>
      {!isUser && (
        <div style={{
          width: 28, height: 28, borderRadius: "50%",
          background: "linear-gradient(135deg, #7C5CBF, #3B8BD4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 12, fontWeight: 700, color: "#fff", flexShrink: 0, marginTop: 4
        }}>V</div>
      )}
      <div style={{ maxWidth: "85%" }}>
        {msg.file && (
          <div style={{
            marginBottom: 8, borderRadius: 12, overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.1)", background: "rgba(0,0,0,0.2)"
          }}>
            {msg.file.type === "image"
              ? <img src={`data:${msg.file.mime_type};base64,${msg.file.base64}`}
                  alt={msg.file.name}
                  style={{ maxWidth: "100%", maxHeight: 200, display: "block" }} />
              : <div style={{ padding: "8px 12px", fontSize: 13, color: "#A0A0B0" }}>
                  📄 {msg.file.name}
                </div>
            }
          </div>
        )}
        <div style={{
          background: isUser ? "rgba(124, 92, 191, 0.15)" : "transparent",
          color: "#E0E0E8",
          padding: isUser ? "10px 16px" : "4px 0",
          borderRadius: isUser ? "16px 16px 4px 16px" : "0",
          fontSize: 15, lineHeight: 1.6,
          border: isUser ? "1px solid rgba(124, 92, 191, 0.3)" : "none",
        }}>
          {isUser ? (
            <span style={{ whiteSpace: "pre-wrap" }}>{msg.content}</span>
          ) : (
            <ReactMarkdown components={{
              code: ({ children }) => (
                <code style={{
                  background: "rgba(20,20,25,0.8)", padding: "2px 6px", borderRadius: 4,
                  fontSize: 13, color: "#E59F1E", fontFamily: "monospace",
                  border: "1px solid rgba(255,255,255,0.05)"
                }}>{children}</code>
              ),
              pre: ({ children }) => (
                <pre style={{
                  background: "rgba(10,10,15,0.8)", padding: 16, borderRadius: 12,
                  overflowX: "auto", fontSize: 13, margin: "12px 0",
                  fontFamily: "monospace", color: "#C2C2CE",
                  border: "1px solid rgba(255,255,255,0.05)"
                }}>{children}</pre>
              ),
              p: ({ children }) => <p style={{ margin: "6px 0" }}>{children}</p>,
            }}>{msg.content}</ReactMarkdown>
          )}
          {msg.streaming && (
            <span style={{
              display: "inline-block", width: 8, height: 14,
              background: "#7C5CBF", marginLeft: 4, borderRadius: 2,
              animation: "blink 1s step-end infinite",
            }} />
          )}
        </div>
        <div style={{
          fontSize: 11, color: "#666680", marginTop: 6,
          textAlign: isUser ? "right" : "left", paddingLeft: isUser ? 0 : 4,
        }}>
          {msg.time}
          {msg.meta && <span style={{ marginLeft: 8, color: "#3B8BD4", opacity: 0.8 }}>{msg.meta}</span>}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState([
    { id: 0, role: "assistant", content: "System ready. Welcome to your Personal AI Assistant.", time: formatTime() }
  ])
  const [input, setInput] = useState("")
  const [connected, setConnected] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [tierMode, setTierMode] = useState("free") // 'free' or 'paid'
  const [settings, setSettings] = useState({})
  const [setupRequired, setSetupRequired] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)
  const [settingsMsg, setSettingsMsg] = useState("")
  const [voiceActive, setVoiceActive] = useState(false)
  const [visionActive, setVisionActive] = useState(false)
  const [muted, setMuted] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState("")
  const [pendingFile, setPendingFile] = useState(null)
  const [showLogs, setShowLogs] = useState(false)
  
  const ws = useRef(null)
  const bottomRef = useRef(null)
  const streamingId = useRef(null)
  const roomRef = useRef(null)
  const heartbeatRef = useRef(null)
  const reconnectTimerRef = useRef(null)

  useEffect(() => {
    // Check for setup mode in URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'setup') {
      setShowSettings(true);
    }

    fetch(API_URL + "/api/settings")
      .then(res => res.json())
      .then(data => {
        setSettings(data)
        if (data.TIER_MODE) setTierMode(data.TIER_MODE)
        // Check if basic setup is done
        if (!data.GROQ_FREE_1 && !data.OPENAI_API_KEY) {
          setSetupRequired(true)
        }
      })
      .catch(err => console.error("Failed to load settings:", err))
  }, [])

  const saveSettings = async (e) => {
    e.preventDefault()
    setSavingSettings(true)
    setSettingsMsg("")
    try {
      // Include tier mode in the save payload
      const settingsToSave = { ...settings, TIER_MODE: tierMode }
      const res = await fetch(API_URL + "/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: settingsToSave })
      })
      const data = await res.json()
      if (data.status === "success") {
        setSettingsMsg("Settings saved successfully!")
        setSetupRequired(false)
        
        // If in setup mode, show professional confirmation
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('mode') === 'setup') {
          alert("🌌 You are all set, Boss! Your environment is configured. \n\nNow, please close this browser window and double-click 'start_ved.bat' to launch Aether.");
        }
        
        setTimeout(() => setShowSettings(false), 1500)
      } else {
        setSettingsMsg("Error: " + data.error)
      }
    } catch (err) {
      console.error("Settings save error:", err)
      setSettingsMsg("Cannot reach backend server. Make sure the backend is running (check the Aether Setup Backend window for errors).")
    } finally {
      setSavingSettings(false)
    }
  }

  const connect = useCallback(() => {
    if (ws.current) ws.current.close()
    if (heartbeatRef.current) clearInterval(heartbeatRef.current)

    ws.current = new WebSocket(WS_URL)
    ws.current.onopen = () => {
      console.log("WebSocket Connected to:", WS_URL)
      setConnected(true)
      // Heartbeat to keep connection alive
      heartbeatRef.current = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ type: "ping" }))
        }
      }, 30000)
    }
    ws.current.onclose = (event) => { 
      setConnected(false)
      if (heartbeatRef.current) clearInterval(heartbeatRef.current)
      
      console.log(`WebSocket Closed (code: ${event.code}, reason: ${event.reason})`)
      
      // Prevent overlapping reconnect timers
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = setTimeout(() => {
        console.log("Attempting to reconnect...")
        connect()
      }, 3000) 
    }
    ws.current.onerror = (e) => {
      console.error("WebSocket Error Detected. Check network tab for details.")
      ws.current.close()
    }
    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === "pong") return
      if (data.type === "ready") {
        console.log("Ved Session Ready:", data.session_id)
        return
      }
      if (data.type === "start") {
        setThinking(true)
        const id = Date.now()
        streamingId.current = id
        setMessages(prev => [...prev, { id, role: "assistant", content: "", time: formatTime(), streaming: true }])
      }
      if (data.type === "chunk") {
        setMessages(prev => prev.map(m =>
          m.id === streamingId.current ? { ...m, content: m.content + data.content } : m
        ))
      }
      if (data.type === "done") {
        setThinking(false)
        setMessages(prev => prev.map(m =>
          m.id === streamingId.current
            ? { ...m, streaming: false, meta: `${data.model} · ${data.task_type}` }
            : m
        ))
        streamingId.current = null
      }
      if (data.type === "error") {
        setThinking(false)
        setMessages(prev => [...prev, {
          id: Date.now(), role: "assistant",
          content: `Error: ${data.message}`, time: formatTime()
        }])
      }
      if (data.type === "control") {
        if (data.action === "toggle_mic" && roomRef.current) {
          const micMuted = data.state
          roomRef.current.localParticipant.setMicrophoneEnabled(!micMuted).catch(console.error)
          setMuted(micMuted)
        }
        if (data.action === "toggle_vis" && roomRef.current) {
          const visActive = data.state
          roomRef.current.localParticipant.setScreenShareEnabled(visActive).catch(console.error)
          setVisionActive(visActive)
        }
      }
    }
  }, [])


  useEffect(() => { 
    connect() 
    return () => {
      // Cleanup on unmount/re-render to prevent Zombie connections
      if (ws.current) {
        console.log("Cleaning up WebSocket on unmount...")
        ws.current.close()
      }
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (heartbeatRef.current) clearInterval(heartbeatRef.current)
      
      // Cleanup Voice session if active
      if (roomRef.current) {
        console.log("Cleaning up Voice session on unmount...")
        roomRef.current.disconnect()
        roomRef.current = null
      }
    }
  }, [connect])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, showLogs])

  const send = () => {
    const text = input.trim()
    if (!text && !pendingFile) return
    
    // Direct readyState check is more reliable than React state 'connected'
    const isSocketOpen = ws.current?.readyState === WebSocket.OPEN
    
    if (!isSocketOpen) {
      console.warn("Attempted to send but WebSocket is not OPEN. State:", ws.current?.readyState)
      setMessages(prev => [...prev, { 
        id: Date.now(), role: "assistant", 
        content: "⚠️ **Connection Offline.** I'm attempting to re-establish a link with the local backend. Please wait a moment or ensure `main.py` is running.", 
        time: formatTime() 
      }])
      setConnected(false) // Sync React state back if it got out of alignment
      return
    }

    if (thinking) return

    setMessages(prev => [...prev, {
      id: Date.now(), role: "user", content: text,
      time: formatTime(), file: pendingFile || null
    }])

    ws.current.send(JSON.stringify({
      message: text,
      file_data: pendingFile || null,
    }))

    setInput("")
    setPendingFile(null)
    setShowLogs(true) 
  }

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() }
  }

  // ── Voice ──────────────────────────────────────────────────────────────────
  const startVoice = async () => {
    try {
      setVoiceStatus("Connecting...")
      const res = await fetch(`${API_URL}/voice/token`)
      const { token, url } = await res.json()
      const room = new Room()
      roomRef.current = room
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) track.attach()
      })
      room.on(RoomEvent.Disconnected, () => { setVoiceActive(false); setVoiceStatus("") })
      await room.connect(url, token)
      await room.localParticipant.setMicrophoneEnabled(true)
      setVoiceActive(true)
      setVoiceStatus("Listening...")
      setShowLogs(false) // Hide logs to focus on Voice Orb
    } catch (err) {
      setVoiceStatus("")
      setMessages(prev => [...prev, {
        id: Date.now(), role: "assistant",
        content: `Voice error: ${err.message}`, time: formatTime()
      }])
      setShowLogs(true)
    }
  }

  const toggleVision = async () => {
    if (!roomRef.current) return
    try {
      const isNowActive = !visionActive
      await roomRef.current.localParticipant.setScreenShareEnabled(isNowActive)
      setVisionActive(isNowActive)
    } catch (err) {
      console.error("Failed to toggle screen share:", err)
      // If user denied permission, ensure state stays consistent
      setVisionActive(false)
      if (err.name === "NotAllowedError") {
        // User clicked "Cancel" on browser's screen share dialog — not an error
        console.log("Screen share permission denied by user")
      }
    }
  }

  const stopVoice = async () => {
    if (roomRef.current) { await roomRef.current.disconnect(); roomRef.current = null }
    setVoiceActive(false)
    setVisionActive(false)
    setVoiceStatus("")
    setMuted(false)
  }

  const toggleMute = async () => {
    if (!roomRef.current) return
    const isMuted = !muted
    await roomRef.current.localParticipant.setMicrophoneEnabled(!isMuted)
    setMuted(isMuted)
  }

  // Determine Orb State
  const orbState = voiceActive 
    ? (muted ? "muted" : "listening") 
    : (thinking ? "thinking" : "idle")

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: "#08080C", color: "#EEEEF4", fontFamily: "system-ui, -apple-system, sans-serif",
      overflow: "hidden", position: "relative"
    }}>
      
      {/* ── Background Ambient Glow ── */}
      <div style={{
        position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
        width: "80vw", height: "80vw", maxHeight: "800px", maxWidth: "800px",
        background: "radial-gradient(circle, rgba(124,92,191,0.05) 0%, rgba(0,0,0,0) 70%)",
        pointerEvents: "none", zIndex: 0
      }} />

      {/* ── Header ── */}
      <div style={{
        padding: "20px 32px", display: "flex", alignItems: "center", justifyContent: "space-between",
        zIndex: 10, background: "linear-gradient(180deg, rgba(8,8,12,0.9) 0%, rgba(8,8,12,0) 100%)"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-0.5px" }}>{settings.AI_NAME || "Ved"}.</div>
          <div style={{ 
            padding: "4px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
            background: connected ? "rgba(29, 185, 123, 0.1)" : "rgba(229, 159, 30, 0.1)",
            color: connected ? "#1DB97B" : "#E59F1E", border: `1px solid ${connected ? "rgba(29,185,123,0.3)" : "rgba(229,159,30,0.3)"}`
          }}>
            {voiceStatus || (connected ? "Sys Online" : "Connecting...")}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => setShowSettings(!showSettings)} style={{
            background: "rgba(124, 92, 191, 0.1)", border: "1px solid rgba(124, 92, 191, 0.3)",
            color: "#7C5CBF", padding: "8px 16px", borderRadius: 20, fontSize: 13, fontWeight: 600,
            cursor: "pointer", transition: "all 0.2s"
          }}>
            ⚙ Settings
          </button>
          <button onClick={() => setShowLogs(!showLogs)} style={{
            background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
            color: "#A0A0B0", padding: "8px 16px", borderRadius: 20, fontSize: 13, fontWeight: 600,
            cursor: "pointer", transition: "all 0.2s"
          }}>
            {showLogs ? "Hide Transcript" : "View Transcript"}
          </button>
        </div>
      </div>

      {/* ── Core Layout (Orb or Transcript) ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", position: "relative", zIndex: 1, overflow: "hidden" }}>
        
        {/* Voice Orb Area (Visible when logs are hidden OR always in background) */}
        <div style={{
          position: "absolute", inset: 0, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", pointerEvents: "none",
          opacity: showLogs ? 0.1 : 1, transition: "opacity 0.5s ease-in-out", transform: showLogs ? "scale(0.9)" : "scale(1)"
        }}>
          <div className={`voice-orb ${orbState}`} />
          {!voiceActive && !thinking && (
            <div style={{ marginTop: 40, color: "#666680", fontSize: 14, fontWeight: 500, letterSpacing: "1px", textTransform: "uppercase" }}>
              Waiting for command
            </div>
          )}
          {voiceActive && (
            <div style={{ marginTop: 40, color: muted ? "#E59F1E" : "#1DB97B", fontSize: 15, fontWeight: 600 }}>
              {muted ? "Microphone Muted" : "Active & Listening"}
            </div>
          )}
        </div>

        {/* ── Settings Overlay ── */}
        {showSettings && (
          <div style={{
            position: "absolute", inset: 0, zIndex: 100, 
            background: "rgba(5,5,10,0.85)", backdropFilter: "blur(20px)",
            display: "flex", flexDirection: "column", padding: 40, overflowY: "auto"
          }}>
            <div style={{ maxWidth: 800, margin: "0 auto", width: "100%" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                <div>
                  <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Aether Settings</h2>
                  <p style={{ fontSize: 12, opacity: 0.5 }}>Configure your identity and multi-tier API brain.</p>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                   <div style={{ 
                     display: "flex", background: "rgba(255,255,255,0.05)", borderRadius: 12, padding: 4,
                     border: "1px solid rgba(255,255,255,0.1)"
                   }}>
                     <button type="button" onClick={() => setTierMode("free")} style={{
                       padding: "8px 20px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600,
                       background: tierMode === "free" ? "#7C5CBF" : "transparent",
                       color: tierMode === "free" ? "#fff" : "#888", cursor: "pointer", transition: "0.2s"
                     }}>FREE TIER</button>
                     <button type="button" onClick={() => setTierMode("paid")} style={{
                       padding: "8px 20px", borderRadius: 8, border: "none", fontSize: 12, fontWeight: 600,
                       background: tierMode === "paid" ? "#7C5CBF" : "transparent",
                       color: tierMode === "paid" ? "#fff" : "#888", cursor: "pointer", transition: "0.2s"
                     }}>PRO TIER (PAID)</button>
                   </div>
                   <button onClick={() => setShowSettings(false)} style={{ background: "none", border: "none", color: "#666", cursor: "pointer", fontSize: 24, marginLeft: 10 }}>×</button>
                </div>
              </div>
              
              <form onSubmit={saveSettings}>
                <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
                  
                  {/* Category: Personalization */}
                  <div>
                    <h3 style={{ fontSize: 13, color: "#7C5CBF", textTransform: "uppercase", marginBottom: 15, borderBottom: "1px solid rgba(124,92,191,0.2)", paddingBottom: 5 }}>
                      Personalization & Identity
                    </h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 15 }}>
                      {[
                        { key: "USER_NAME", label: "Your Name", placeholder: "e.g. Ishaan" },
                        { key: "AI_NAME", label: "AI Name", placeholder: "e.g. Ved" },
                        { key: "USER_LOCATION", label: "Location", placeholder: "e.g. Pilani, India" },
                        { key: "USER_BIO", label: "Brief Bio", placeholder: "e.g. Developer & Student" },
                      ].map(f => (
                        <div key={f.key} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                          <label style={{ fontSize: 10, opacity: 0.6 }}>{f.label}</label>
                          <input value={settings[f.key] || ""} placeholder={f.placeholder} onChange={e => setSettings({...settings, [f.key]: e.target.value})} 
                            style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Category: AI Channels (Conditional) */}
                  <div>
                    <h3 style={{ fontSize: 13, color: "#7C5CBF", textTransform: "uppercase", marginBottom: 15, borderBottom: "1px solid rgba(124,92,191,0.2)", paddingBottom: 5 }}>
                      {tierMode === "free" ? "Free Inference Swarm (Rotation)" : "Professional Inference (Single Key)"}
                    </h3>
                    
                    {tierMode === "free" ? (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 15 }}>
                        {["GEMINI_FREE_1", "GEMINI_FREE_2", "GEMINI_FREE_3"].map(k => (
                          <div key={k} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                            <label style={{ fontSize: 10, opacity: 0.6 }}>Gemini Free {k.split("_").pop()}</label>
                            <input type="password" value={settings[k] || ""} onChange={e => setSettings({...settings, [k]: e.target.value})} 
                              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                          </div>
                        ))}
                        {["GROQ_FREE_1", "GROQ_FREE_2", "GROQ_FREE_3"].map(k => (
                          <div key={k} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                            <label style={{ fontSize: 10, opacity: 0.6 }}>Groq Free {k.split("_").pop()}</label>
                            <input type="password" value={settings[k] || ""} onChange={e => setSettings({...settings, [k]: e.target.value})} 
                              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                          </div>
                        ))}
                        {["OR_FREE_1", "OR_FREE_2", "OR_FREE_3"].map(k => (
                          <div key={k} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                            <label style={{ fontSize: 10, opacity: 0.6 }}>OpenRouter Free {k.split("_").pop()}</label>
                            <input type="password" value={settings[k] || ""} onChange={e => setSettings({...settings, [k]: e.target.value})} 
                              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 15 }}>
                        {[
                          { key: "OPENAI_API_KEY", label: "OpenAI API Key (Brain)" },
                          { key: "CLAUDE_API_KEY", label: "Anthropic Claude Key (Brain)" },
                          { key: "GEMINI_PAID_KEY", label: "Google Paid Key (Voice/Vision)" },
                        ].map(f => (
                          <div key={f.key} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                            <label style={{ fontSize: 10, opacity: 0.6 }}>{f.label}</label>
                            <input type="password" value={settings[f.key] || ""} onChange={e => setSettings({...settings, [f.key]: e.target.value})} 
                              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Category: System & Credentials */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 30 }}>
                    <div>
                      <h3 style={{ fontSize: 13, color: "#7C5CBF", textTransform: "uppercase", marginBottom: 15, borderBottom: "1px solid rgba(124,92,191,0.2)", paddingBottom: 5 }}>
                        Platform & Voice
                      </h3>
                      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                        {[
                          { key: "LIVEKIT_URL", label: "LiveKit URL" },
                          { key: "LIVEKIT_API_KEY", label: "LiveKit API Key" },
                          { key: "LIVEKIT_API_SECRET", label: "LiveKit Secret", type: "password" },
                          { key: "TAVILY_API_KEY", label: "Tavily (Search)", type: "password" },
                        ].map(f => (
                          <div key={f.key}>
                            <label style={{ fontSize: 10, opacity: 0.6 }}>{f.label}</label>
                            <input type={f.type || "text"} value={settings[f.key] || ""} onChange={e => setSettings({...settings, [f.key]: e.target.value})} 
                              style={{ width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <h3 style={{ fontSize: 13, color: "#7C5CBF", textTransform: "uppercase", marginBottom: 15, borderBottom: "1px solid rgba(124,92,191,0.2)", paddingBottom: 5 }}>
                        Telegram & Path
                      </h3>
                      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                        {[
                          { key: "TELEGRAM_BOT_TOKEN", label: "Bot Token", type: "password" },
                          { key: "TELEGRAM_ALLOWED_ID", label: "Your Telegram User ID" },
                          { key: "AETHER_WORKSPACE", label: "Workspace Folder", placeholder: "D:\\assistant_work" },
                        ].map(f => (
                          <div key={f.key}>
                            <label style={{ fontSize: 10, opacity: 0.6 }}>{f.label}</label>
                            <input type={f.type || "text"} value={settings[f.key] || ""} placeholder={f.placeholder} onChange={e => setSettings({...settings, [f.key]: e.target.value})} 
                              style={{ width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: 10, color: "#fff", outline: "none", fontSize: 12 }} />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                </div>

                <div style={{ marginTop: 40, display: "flex", alignItems: "center", gap: 20 }}>
                  <button type="submit" disabled={savingSettings} style={{
                    background: "#7C5CBF", color: "#fff", border: "none", borderRadius: 30,
                    padding: "14px 40px", fontSize: 15, fontWeight: 700, cursor: "pointer",
                    boxShadow: "0 10px 20px rgba(124, 92, 191, 0.3)"
                  }}>
                    {savingSettings ? "Saving..." : "Save Configuration"}
                  </button>
                  {settingsMsg && <span style={{ color: settingsMsg.includes("Error") ? "#FF4D4D" : "#1DB97B", fontSize: 14 }}>{settingsMsg}</span>}
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Transcript Drawer / Overlay array */}
        <div style={{
          flex: 1, width: "100%", maxWidth: 900, margin: "0 auto",
          overflowY: "auto", padding: "20px 32px",
          display: showLogs ? "block" : "none",
          maskImage: "linear-gradient(to bottom, transparent, black 5%, black 95%, transparent)",
          WebkitMaskImage: "-webkit-linear-gradient(top, transparent, black 10%, black 95%, transparent)",
        }}>
          <div style={{ height: 40 }} /> {/* Top padding for mask */}
          {messages.map(m => <Message key={m.id} msg={m} />)}
          <div ref={bottomRef} style={{ height: 100 }} /> {/* Bottom padding */}
        </div>
      </div>

      {/* ── Floating Controls Dock ── */}
      <div style={{
        position: "absolute", bottom: 40, left: "50%", transform: "translateX(-50%)",
        width: "90%", maxWidth: 800, zIndex: 20,
        background: "rgba(20, 20, 28, 0.75)", backdropFilter: "blur(20px)",
        border: "1px solid rgba(255,255,255,0.08)", borderRadius: 30,
        padding: "12px 16px", display: "flex", alignItems: "center", gap: 12,
        boxShadow: "0 20px 40px rgba(0,0,0,0.5)"
      }}>
        
        {/* Voice Toggle Container */}
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => voiceActive ? stopVoice() : startVoice()}
            title={voiceActive ? "Stop voice" : "Start voice"}
            style={{
              width: 50, height: 50, borderRadius: "50%", border: "none",
              background: voiceActive ? "rgba(217, 87, 58, 0.2)" : "rgba(124, 92, 191, 0.2)",
              color: voiceActive ? "#D9573A" : "#7C5CBF",
              cursor: "pointer", fontSize: 22,
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.2s"
            }}>
            {voiceActive ? "⏹" : "🎙"}
          </button>
          
          {voiceActive && (
            <button onClick={toggleMute}
              title={muted ? "Unmute" : "Mute"}
              style={{
                width: 50, height: 50, borderRadius: "50%", border: "none",
                background: muted ? "rgba(229, 159, 30, 0.2)" : "rgba(255, 255, 255, 0.05)",
                color: muted ? "#E59F1E" : "#fff",
                cursor: "pointer", fontSize: 20,
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.2s"
              }}>
              {muted ? "🔇" : "🎤"}
            </button>
          )}
          
          {voiceActive && (
            <button onClick={toggleVision}
              title={visionActive ? "Stop Screen Share" : "Share Screen"}
              style={{
                width: 50, height: 50, borderRadius: "50%", border: "none",
                background: visionActive ? "rgba(29, 185, 123, 0.2)" : "rgba(255, 255, 255, 0.05)",
                color: visionActive ? "#1DB97B" : "#fff",
                cursor: "pointer", fontSize: 20,
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.2s"
              }}>
              {visionActive ? "👁️" : "🖥️"}
            </button>
          )}
        </div>

        <div style={{ width: 1, height: 30, background: "rgba(255,255,255,0.1)", margin: "0 4px" }} />

        {/* Text Input Container */}
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10 }}>
          <FileUpload
            onFileReady={(f) => setPendingFile(f)}
            onClear={() => setPendingFile(null)}
          />
          {pendingFile && (
            <div style={{ fontSize: 13, color: "#7C5CBF", background: "rgba(124,92,191,0.1)", padding: "4px 10px", borderRadius: 12 }}>
               {pendingFile.name}
            </div>
          )}
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message Ved..."
            style={{
              flex: 1, background: "transparent", border: "none",
              color: "#EEEEF4", fontSize: 16, outline: "none",
            }}
          />
          {(input.trim() || pendingFile) && (
            <button onClick={send} 
              style={{
                background: (!connected || thinking) ? "rgba(124, 92, 191, 0.4)" : "#7C5CBF", 
                border: "none", borderRadius: "50%",
                width: 38, height: 38, color: "#fff", fontSize: 18,
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.2s",
                boxShadow: "0 4px 10px rgba(0,0,0,0.2)",
                zIndex: 30
              }}>
              ↑
            </button>
          )}
        </div>
      </div>

      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        
        /* ── Advanced Glowing Orb CSS ── */
        .voice-orb {
          width: 240px; height: 240px;
          border-radius: 50%;
          transition: all 0.5s ease-in-out;
          filter: blur(10px);
        }
        .voice-orb.idle {
          background: radial-gradient(circle at 30% 30%, rgba(60,60,80,0.8), rgba(20,20,30,0.9));
          box-shadow: 0 0 60px rgba(255,255,255,0.02);
          animation: breathe-idle 4s infinite ease-in-out alternate;
        }
        .voice-orb.listening {
          background: radial-gradient(circle at 30% 30%, rgba(59,139,212,0.9), rgba(124,92,191,0.9));
          box-shadow: 0 0 80px rgba(124,92,191,0.4), inset 0 0 40px rgba(59,139,212,0.6);
          animation: pulse-listen 1.5s infinite alternate;
        }
        .voice-orb.thinking {
          background: radial-gradient(circle at 50% 50%, rgba(124,92,191,0.9), rgba(217,87,58,0.8));
          box-shadow: 0 0 100px rgba(217,87,58,0.3);
          animation: spin-think 3s linear infinite;
        }
        .voice-orb.muted {
          background: radial-gradient(circle at 50% 50%, rgba(229,159,30,0.5), rgba(40,30,10,0.9));
          box-shadow: 0 0 40px rgba(229,159,30,0.1);
        }

        @keyframes breathe-idle {
          0% { transform: scale(1); opacity: 0.8; }
          100% { transform: scale(1.05); opacity: 1; }
        }
        @keyframes pulse-listen {
          0% { transform: scale(1) translateY(0); filter: blur(8px); }
          100% { transform: scale(1.1) translateY(-5px); filter: blur(14px); }
        }
        @keyframes spin-think {
          0% { transform: rotate(0deg) scale(1); }
          50% { transform: rotate(180deg) scale(1.05); }
          100% { transform: rotate(360deg) scale(1); }
        }
      `}</style>
    </div>
  )
}
