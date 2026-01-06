import React, { useState, useRef, useEffect } from "react";
import { api } from "../api.js";

const ChatPage = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: "user", content: input.trim(), id: Date.now() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await api.sendChatMessage({
        content: userMessage.content,
        use_rag: true,
      });

      const assistantContent =
        res.assistant_message?.content ||
        res.result?.answer ||
        res.answer ||
        "No response received";

      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: assistantContent,
          sources: res.sources || [],
          id: Date.now() + 1,
        },
      ]);
    } catch (e) {
      console.error("Chat error:", e);
      let errorMessage = "An error occurred";
      
      if (e.message) {
        try {
          const errorData = JSON.parse(e.message);
          if (errorData.detail === "Not authenticated") {
            errorMessage = "Authentication failed. Please log in again.";
            setTimeout(() => {
              window.location.href = "/login";
            }, 2000);
          } else {
            errorMessage = errorData.detail || errorMessage;
          }
        } catch {
          errorMessage = e.message;
        }
      }

      setError(errorMessage);
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: `Error: ${errorMessage}`,
          isError: true,
          id: Date.now() + 1,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="page-enter" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 4rem)", maxHeight: "800px" }}>
      {/* Header */}
      <div className="fade-in-down" style={{ marginBottom: "var(--spacing-lg)" }}>
        <h1
          style={{
            fontSize: "2rem",
            fontWeight: 700,
            marginBottom: "var(--spacing-sm)",
            color: "var(--text-primary)",
          }}
        >
          Chat Assistant
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          Ask questions about your documents. This uses your configured LLM and RAG pipeline.
        </p>
      </div>

      {/* Messages Container */}
      <div
        className="card"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          marginBottom: "var(--spacing-lg)",
          padding: 0,
        }}
      >
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "var(--spacing-lg)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--spacing-md)",
          }}
        >
          {messages.length === 0 ? (
            <div
              className="fade-in"
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-secondary)",
                textAlign: "center",
              }}
            >
              <div>
                <div style={{ fontSize: "3rem", marginBottom: "var(--spacing-md)", animation: "bounce 2s infinite" }}>💬</div>
                <p style={{ fontSize: "1.125rem", marginBottom: "var(--spacing-sm)" }}>
                  Start a conversation
                </p>
                <p style={{ fontSize: "0.875rem", color: "var(--gray-500)" }}>
                  Ask questions about your documents to get started
                </p>
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div
                key={m.id || i}
                className={`message-enter ${m.role === "user" ? "user" : ""}`}
                style={{
                  display: "flex",
                  gap: "var(--spacing-md)",
                  alignItems: "flex-start",
                  padding: "var(--spacing-md)",
                  borderRadius: "var(--radius-md)",
                  background: m.role === "user" ? "var(--primary)" : "var(--gray-100)",
                  color: m.role === "user" ? "var(--text-inverse)" : "var(--text-primary)",
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "80%",
                  marginLeft: m.role === "user" ? "auto" : 0,
                  marginRight: m.role === "user" ? 0 : "auto",
                  border: m.isError ? "1px solid var(--error)" : "none",
                  animationDelay: `${i * 0.1}s`,
                  transition: "transform var(--transition-base)",
                }}
                onMouseEnter={(e) => {
                  if (!m.isError) {
                    e.currentTarget.style.transform = "scale(1.02)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "scale(1)";
                }}
              >
                <div style={{ minWidth: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {m.role === "user" ? "👤" : "🤖"}
                </div>
                <div style={{ flex: 1, wordBreak: "break-word" }}>
                  <div style={{ fontWeight: 600, marginBottom: "var(--spacing-xs)", fontSize: "0.875rem" }}>
                    {m.role === "user" ? "You" : "Assistant"}
                  </div>
                  <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{m.content}</div>
                  {m.sources && m.sources.length > 0 && (
                    <div
                      style={{
                        marginTop: "var(--spacing-sm)",
                        paddingTop: "var(--spacing-sm)",
                        borderTop: "1px solid rgba(255, 255, 255, 0.2)",
                        fontSize: "0.75rem",
                        opacity: 0.8,
                      }}
                    >
                      <strong>Sources:</strong> {m.sources.length} document(s)
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {loading && (
            <div
              className="slide-in-right"
              style={{
                display: "flex",
                gap: "var(--spacing-md)",
                alignItems: "flex-start",
                padding: "var(--spacing-md)",
                alignSelf: "flex-start",
              }}
            >
              <div style={{ minWidth: "32px", height: "32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                🤖
              </div>
              <div
                className="card"
                style={{
                  padding: "var(--spacing-md)",
                  background: "var(--gray-100)",
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-sm)",
                }}
              >
                <div className="typing-indicator">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
                <span style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>Thinking...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          className="fade-in-down"
          style={{
            padding: "var(--spacing-md)",
            background: "var(--error)",
            color: "var(--text-inverse)",
            borderRadius: "var(--radius-md)",
            marginBottom: "var(--spacing-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--spacing-sm)",
            animation: "shake 0.5s ease-in-out",
          }}
        >
          <style>{`
            @keyframes shake {
              0%, 100% { transform: translateX(0); }
              25% { transform: translateX(-10px); }
              75% { transform: translateX(10px); }
            }
          `}</style>
          <span>⚠️</span>
          <span style={{ flex: 1 }}>{error}</span>
          <button
            onClick={() => setError(null)}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-inverse)",
              cursor: "pointer",
              padding: "var(--spacing-xs)",
              transition: "transform var(--transition-base)",
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = "rotate(90deg)"}
            onMouseLeave={(e) => e.currentTarget.style.transform = "rotate(0deg)"}
          >
            ✕
          </button>
        </div>
      )}

      {/* Input Area */}
      <div
        className="fade-in-up"
        style={{
          display: "flex",
          gap: "var(--spacing-md)",
          alignItems: "flex-end",
          padding: "var(--spacing-md)",
          background: "var(--bg-primary)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-md)",
          transition: "box-shadow var(--transition-base)",
        }}
        onFocus={(e) => e.currentTarget.style.boxShadow = "var(--shadow-lg)"}
        onBlur={(e) => e.currentTarget.style.boxShadow = "var(--shadow-md)"}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents..."
          disabled={loading}
          rows={1}
          style={{
            flex: 1,
            padding: "var(--spacing-md)",
            fontSize: "0.875rem",
            lineHeight: 1.5,
            border: "1px solid var(--gray-300)",
            borderRadius: "var(--radius-md)",
            resize: "none",
            minHeight: "44px",
            maxHeight: "120px",
            fontFamily: "inherit",
            transition: "all var(--transition-base)",
          }}
          onInput={(e) => {
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="btn btn-primary hover-lift"
          style={{
            padding: "var(--spacing-md) var(--spacing-xl)",
            minWidth: "100px",
            height: "44px",
          }}
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
              Sending...
            </>
          ) : (
            "Send"
          )}
        </button>
      </div>
    </div>
  );
};

export default ChatPage;
