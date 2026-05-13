import { useState, useRef } from "react"

const ACCEPTED = "image/*,.pdf,.txt,.md,.py,.js,.json,.csv"

export default function FileUpload({ onFileReady, onClear }) {
  const [attached, setAttached] = useState(null)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef(null)

  const handleFile = async (file) => {
    if (!file) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append("file", file)
      const host = window.location.hostname || "127.0.0.1"
      const res = await fetch(`http://${host}:8000/upload`, {
        method: "POST",
        body: form,
      })
      const data = await res.json()
      setAttached({ name: file.name, ...data })
      onFileReady({ name: file.name, ...data })
    } catch (err) {
      console.error("Upload failed:", err)
    } finally {
      setUploading(false)
    }
  }

  const clear = () => {
    setAttached(null)
    onClear()
    if (inputRef.current) inputRef.current.value = ""
  }

  const onDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div style={{ position: "relative" }}>
      {attached ? (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          background: "#1E1E2E", border: "1px solid #7C5CBF",
          borderRadius: 8, padding: "6px 10px", fontSize: 12,
          color: "#C2C2CE", maxWidth: 260,
        }}>
          <span style={{ fontSize: 16 }}>
            {attached.type === "image" ? "🖼" : "📄"}
          </span>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {attached.name}
          </span>
          <button
            onClick={clear}
            style={{
              background: "none", border: "none", color: "#555570",
              cursor: "pointer", fontSize: 14, padding: "0 2px",
            }}>✕</button>
        </div>
      ) : (
        <button
          onClick={() => inputRef.current?.click()}
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          title="Attach file or image"
          style={{
            background: "none", border: "1px solid #2A2A3E",
            borderRadius: 8, padding: "8px 10px",
            color: uploading ? "#555570" : "#7A7A8C",
            cursor: uploading ? "wait" : "pointer",
            fontSize: 18, lineHeight: 1,
          }}>
          {uploading ? "⏳" : "📎"}
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        style={{ display: "none" }}
        onChange={(e) => handleFile(e.target.files[0])}
      />
    </div>
  )
}
