import { useState, useEffect, useRef } from "react"
import { getCurrentWindow, LogicalSize } from "@tauri-apps/api/window"

const WS_URL = "ws://127.0.0.1:8000/ws/chat"

export default function Widget() {
  const [mode, setMode] = useState("compact")
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState([])
  const [connected, setConnected] = useState(false)
  const [micMuted, setMicMuted] = useState(false)
  const [visActive, setVisActive] = useState(false)
  
  const ws = useRef(null)
  const chatRef = useRef(null)

  useEffect(() => {
    connect()
    return () => ws.current?.close()
  }, [])

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [messages])

  const connect = () => {
    try {
      ws.current = new WebSocket(WS_URL)
      ws.current.onopen = () => setConnected(true)
      ws.current.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000)
      }
      ws.current.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.type === "chunk") {
           // simplified feedback
        }
      }
    } catch (e) {
      console.error("WS Connect Error", e)
    }
  }

  const updateSize = async (m) => {
    try {
      const appWindow = getCurrentWindow()
      if (m === "compact") {
        await appWindow.setSize(new LogicalSize(180, 70))
      } else if (m === "text") {
        await appWindow.setSize(new LogicalSize(320, 480))
      } else if (m === "voice") {
        await appWindow.setSize(new LogicalSize(280, 140))
      }
      setMode(m)
    } catch (e) {
      console.error("Resize Error", e)
      // Fallback for dev
      setMode(m)
    }
  }

  const sendControl = (action, value) => {
    if (action === "toggle_mic") {
      setMicMuted(value)
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: "control", action: "toggle_mic", state: value }))
      }
    }
    if (action === "toggle_vis") {
      setVisActive(value)
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: "control", action: "toggle_vis", state: value }))
      }
    }
  }

  const sendText = () => {
    if (!input.trim() || ws.current?.readyState !== WebSocket.OPEN) return
    ws.current.send(JSON.stringify({ message: input }))
    setMessages(prev => [...prev, { role: "user", content: input }])
    setInput("")
  }

  const startDrag = async (e) => {
    // Only drag if the click is directly on the background or header, not inside inputs or buttons
    if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      try {
        const appWindow = getCurrentWindow()
        await appWindow.startDragging()
      } catch (err) {
        console.error("Drag Error:", err)
      }
    }
  }

  return (
    <div style={containerStyle} onPointerDown={startDrag}>
      {/* --- GLASS BACKGROUND --- */}
      <div 
        style={{
          ...glassBgStyle,
          cursor: mode === "compact" ? "grab" : "default"
        }}
      >
        
        {/* COMPACT MODE */}
        {mode === "compact" && (
          <div style={compactInnerStyle}>
            <button onClick={() => updateSize("voice")} style={actionBtnStyle}>🎙️</button>
            <button onClick={() => updateSize("text")} style={actionBtnStyle}>💬</button>
            <div style={{...statusDotStyle, background: connected ? "#10b981" : "#f59e0b"}} />
          </div>
        )}

        {/* TEXT MODE */}
        {mode === "text" && (
          <div style={expandedContainerStyle}>
            <div style={headerStyle}>
              <span style={titleStyle}>ATHER ENGINE</span>
              <button onClick={() => updateSize("compact")} style={shrinkBtnStyle}>↙ SHRINK</button>
            </div>
            
            <div ref={chatRef} style={chatAreaStyle}>
              {messages.length === 0 && <div style={emptyChatStyle}>Awaiting commands...</div>}
              {messages.map((m, i) => (
                <div key={i} style={{ marginBottom: 12, textAlign: m.role === "user" ? "right" : "left" }}>
                  <div style={{
                    ...msgBubbleStyle,
                    background: m.role === "user" ? "rgba(59, 139, 212, 0.8)" : "rgba(0, 0, 0, 0.05)",
                    color: m.role === "user" ? "#fff" : "#334155"
                  }}>
                    {m.content}
                  </div>
                </div>
              ))}
            </div>

            <div style={inputContainerStyle}>
              <input 
                value={input} 
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendText()}
                placeholder="Secure Link..."
                style={inputStyle}
              />
              <button onClick={sendText} style={sendBtnStyle}>↑</button>
            </div>
          </div>
        )}

        {/* VOICE MODE */}
        {mode === "voice" && (
          <div style={expandedContainerStyle}>
            <div data-tauri-drag-region style={headerStyle}>
              <span data-tauri-drag-region style={titleStyle}>VOICE LINK</span>
              <button onClick={() => updateSize("compact")} style={shrinkBtnStyle}>↙ SHRINK</button>
            </div>
            <div style={voiceControlsStyle}>
               <button 
                 onClick={() => sendControl("toggle_mic", !micMuted)} 
                 style={{...ctrlBtnStyle, background: micMuted ? "#ef4444" : "#fff", color: micMuted ? "#fff" : "#1e293b"}}
               >
                 {micMuted ? "🔇 MUTED" : "🎙️ MIC ON"}
               </button>
               <button 
                 onClick={() => sendControl("toggle_vis", !visActive)} 
                 style={{...ctrlBtnStyle, background: visActive ? "#3b82f6" : "#fff", color: visActive ? "#fff" : "#1e293b"}}
               >
                 {visActive ? "👁️ VISION ON" : "👁️ VISION OFF"}
               </button>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

// --- ELITE STYLES ---

const containerStyle = {
  width: "100vw",
  height: "100vh",
  padding: "5px",
  boxSizing: "border-box",
  position: "relative",
  overflow: "hidden"
}

const glassBgStyle = {
  position: "relative",
  width: "100%",
  height: "100%",
  background: "rgba(255, 255, 255, 0.45)",
  backdropFilter: "blur(25px) saturate(200%)",
  WebkitBackdropFilter: "blur(25px) saturate(200%)",
  borderRadius: "20px",
  border: "1px solid rgba(255, 255, 255, 0.6)",
  boxShadow: "0 10px 30px rgba(0, 0, 0, 0.12), inset 0 0 15px rgba(255, 255, 255, 0.5)",
  display: "flex",
  flexDirection: "column",
  transition: "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)"
}

const compactInnerStyle = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "15px"
}

const actionBtnStyle = {
  width: "36px",
  height: "36px",
  border: 0,
  borderRadius: "12px",
  background: "rgba(255, 255, 255, 0.6)",
  cursor: "pointer",
  fontSize: "18px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  transition: "transform 0.2s"
}

const statusDotStyle = {
  width: "8px",
  height: "8px",
  borderRadius: "50%",
  boxShadow: "0 0 8px rgba(0,0,0,0.1)"
}

const expandedContainerStyle = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  padding: "15px"
}

const headerStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "15px"
}

const titleStyle = {
  fontSize: "10px",
  fontWeight: 800,
  letterSpacing: "1.5px",
  color: "#64748b"
}

const shrinkBtnStyle = {
  background: "none",
  border: "1px solid rgba(0,0,0,0.1)",
  borderRadius: "8px",
  padding: "4px 8px",
  fontSize: "9px",
  fontWeight: 700,
  cursor: "pointer",
  color: "#64748b"
}

const chatAreaStyle = {
  flex: 1,
  overflowY: "auto",
  marginBottom: "12px",
  paddingRight: "5px"
}

const emptyChatStyle = {
  textAlign: "center",
  color: "#94a3b8",
  fontSize: "11px",
  marginTop: "40px",
  fontStyle: "italic"
}

const msgBubbleStyle = {
  display: "inline-block",
  padding: "8px 14px",
  borderRadius: "15px",
  fontSize: "13px",
  lineHeight: "1.5",
  maxWidth: "85%",
  boxShadow: "0 2px 5px rgba(0,0,0,0.02)"
}

const inputContainerStyle = {
  display: "flex",
  gap: "8px"
}

const inputStyle = {
  flex: 1,
  background: "rgba(255, 255, 255, 0.8)",
  border: "1px solid rgba(255, 255, 255, 0.8)",
  borderRadius: "12px",
  padding: "8px 12px",
  fontSize: "13px",
  outline: "none",
  boxShadow: "inset 0 2px 4px rgba(0,0,0,0.02)"
}

const sendBtnStyle = {
  width: "35px",
  height: "35px",
  background: "#3b82f6",
  border: 0,
  borderRadius: "10px",
  color: "#fff",
  fontSize: "18px",
  fontWeight: "bold",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center"
}

const voiceControlsStyle = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  gap: "10px"
}

const ctrlBtnStyle = {
  flex: 1,
  height: "45px",
  border: "1px solid rgba(255, 255, 255, 0.8)",
  borderRadius: "12px",
  fontSize: "11px",
  fontWeight: 800,
  cursor: "pointer",
  boxShadow: "0 4px 10px rgba(0,0,0,0.04)",
  transition: "all 0.2s"
}
