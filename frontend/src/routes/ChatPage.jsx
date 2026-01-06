import React, { useState, useRef, useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { UserContext } from "../App.jsx";

const ChatPage = () => {
  const { setUser } = useContext(UserContext);
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [queryType, setQueryType] = useState("file"); // "ask" or "file"
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [llmConfigs, setLlmConfigs] = useState([]);
  const [selectedLlmId, setSelectedLlmId] = useState(null);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [showHistory, setShowHistory] = useState(true);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Load conversations and LLM configs on mount
  useEffect(() => {
    loadConversations();
    loadLLMConfigs();
  }, []);

  // Load messages when conversation changes
  useEffect(() => {
    if (currentConversationId) {
      loadConversationMessages(currentConversationId);
    } else {
      setMessages([]);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      setLoadingConversations(true);
      const convs = await api.listConversations();
      setConversations(convs || []);
    } catch (e) {
      console.error("Error loading conversations:", e);
    } finally {
      setLoadingConversations(false);
    }
  };

  const loadLLMConfigs = async () => {
    try {
      const configs = await api.listLLMConfigs(false); // Only active configs
      setLlmConfigs(configs || []);
      // Set default LLM (first active or default)
      const defaultConfig = configs.find(c => c.is_default && c.is_active) || configs.find(c => c.is_active);
      if (defaultConfig) {
        setSelectedLlmId(defaultConfig.id);
      }
    } catch (e) {
      console.error("Error loading LLM configs:", e);
    }
  };

  const loadConversationMessages = async (conversationId) => {
    try {
      const conversation = await api.getConversation(conversationId);
      if (conversation && conversation.messages) {
        const formattedMessages = conversation.messages.map(msg => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          sources: msg.message_metadata?.sources || [],
          queryType: msg.message_metadata?.use_rag ? "file" : "ask",
        }));
        setMessages(formattedMessages);
        // Set query type and LLM from conversation
        if (conversation.use_rag !== undefined) {
          setQueryType(conversation.use_rag ? "file" : "ask");
        }
        if (conversation.llm_config_id) {
          setSelectedLlmId(conversation.llm_config_id);
        }
      }
    } catch (e) {
      console.error("Error loading conversation messages:", e);
      setError("Failed to load conversation");
    }
  };

  const createNewConversation = () => {
    setCurrentConversationId(null);
    setMessages([]);
    setQueryType("file");
    setShowHistory(false);
  };

  const selectConversation = async (conversationId) => {
    setCurrentConversationId(conversationId);
    setShowHistory(false);
  };

  const deleteConversation = async (conversationId, e) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this conversation?")) {
      return;
    }
    try {
      await api.deleteConversation(conversationId);
      await loadConversations();
      if (currentConversationId === conversationId) {
        createNewConversation();
      }
    } catch (e) {
      console.error("Error deleting conversation:", e);
      setError("Failed to delete conversation");
    }
  };

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
        conversation_id: currentConversationId,
        use_rag: queryType === "file",
        llm_config_id: selectedLlmId,
      });

      const assistantContent =
        res.assistant_message?.content ||
        res.result?.answer ||
        res.answer ||
        "No response received";

      // Update conversation ID if this was a new conversation
      if (res.conversation_id && !currentConversationId) {
        setCurrentConversationId(res.conversation_id);
        await loadConversations();
      }

      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: assistantContent,
          sources: res.sources || [],
          queryType: queryType,
          id: Date.now() + 1,
        },
      ]);
    } catch (e) {
      console.error("Chat error:", e);
      let errorMessage = "An error occurred";
      
      // Check for authentication errors
      let isAuthError = false;
      if (e.message) {
        try {
          const errorData = JSON.parse(e.message);
          if (errorData.detail === "Not authenticated" || 
              errorData.detail?.includes("authenticated") ||
              errorData.detail === "Could not validate credentials") {
            isAuthError = true;
            errorMessage = "Authentication failed. Please log in again.";
          } else {
            errorMessage = errorData.detail || errorMessage;
          }
        } catch {
          if (e.message.includes("authenticated") || 
              e.message.includes("401") ||
              e.message.includes("Unauthorized")) {
            isAuthError = true;
            errorMessage = "Authentication failed. Please log in again.";
          } else {
            errorMessage = e.message;
          }
        }
      }
      
      if (isAuthError) {
        setUser(null);
        setTimeout(() => {
          navigate("/login", { replace: true });
        }, 1000);
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

  const getLLMDisplayName = (llmId) => {
    if (!llmId) return "Default";
    const config = llmConfigs.find(c => c.id === llmId);
    if (!config) return "Default";
    const providerNames = {
      openai: "OpenAI",
      gemini: "Gemini",
      anthropic: "Claude",
      custom: "Custom"
    };
    return `${providerNames[config.provider] || config.provider} - ${config.model_name || "default"}`;
  };

  return (
    <div className="page-enter" style={{ display: "flex", gap: "var(--spacing-lg)", height: "calc(100vh - 4rem)", maxHeight: "800px" }}>
      {/* Conversation History Sidebar */}
      <div
        className="card fade-in-left"
        style={{
          width: showHistory ? "280px" : "0",
          minWidth: showHistory ? "280px" : "0",
          overflow: "hidden",
          transition: "all var(--transition-base)",
          display: showHistory ? "flex" : "none",
          flexDirection: "column",
          padding: showHistory ? "var(--spacing-md)" : "0",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-md)" }}>
          <h3 style={{ fontSize: "1.125rem", fontWeight: 600 }}>Chat History</h3>
          <button
            onClick={() => setShowHistory(false)}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              fontSize: "1.25rem",
              padding: "var(--spacing-xs)",
            }}
          >
            ✕
          </button>
        </div>
        <button
          onClick={createNewConversation}
          className="btn btn-primary"
          style={{ marginBottom: "var(--spacing-md)", width: "100%" }}
        >
          + New Chat
        </button>
        {loadingConversations ? (
          <div style={{ textAlign: "center", padding: "var(--spacing-xl)" }}>
            <div className="spinner" style={{ width: "1.5rem", height: "1.5rem", margin: "0 auto" }} />
          </div>
        ) : (
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "var(--spacing-xs)" }}>
            {conversations.length === 0 ? (
              <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", textAlign: "center", padding: "var(--spacing-md)" }}>
                No conversations yet
              </p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  style={{
                    padding: "var(--spacing-sm)",
                    borderRadius: "var(--radius-md)",
                    background: currentConversationId === conv.id ? "var(--primary-light)" : "var(--gray-50)",
                    cursor: "pointer",
                    transition: "all var(--transition-base)",
                    border: currentConversationId === conv.id ? "2px solid var(--primary)" : "1px solid transparent",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                  onMouseEnter={(e) => {
                    if (currentConversationId !== conv.id) {
                      e.currentTarget.style.background = "var(--gray-100)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (currentConversationId !== conv.id) {
                      e.currentTarget.style.background = "var(--gray-50)";
                    }
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: "0.875rem", marginBottom: "var(--spacing-xs)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {conv.title || `Chat ${conv.id}`}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      {conv.message_count || 0} messages
                    </div>
                  </div>
                  <button
                    onClick={(e) => deleteConversation(conv.id, e)}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      color: "var(--text-secondary)",
                      padding: "var(--spacing-xs)",
                      fontSize: "0.875rem",
                    }}
                    title="Delete conversation"
                  >
                    🗑️
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Header */}
        <div className="fade-in-down" style={{ marginBottom: "var(--spacing-lg)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
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
              {queryType === "ask"
                ? "Ask general questions directly to the LLM without document search."
                : "Ask questions about your documents using RAG (Retrieval-Augmented Generation)."}
            </p>
          </div>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="btn btn-secondary"
            style={{ padding: "var(--spacing-sm) var(--spacing-md)" }}
          >
            {showHistory ? "Hide" : "Show"} History
          </button>
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
                    {m.queryType && (
                      <div
                        style={{
                          marginTop: "var(--spacing-xs)",
                          fontSize: "0.75rem",
                          opacity: 0.7,
                          display: "flex",
                          alignItems: "center",
                          gap: "var(--spacing-xs)",
                        }}
                      >
                        <span>{m.queryType === "ask" ? "💬" : "📄"}</span>
                        <span>{m.queryType === "ask" ? "Direct LLM Query" : "RAG Query"}</span>
                      </div>
                    )}
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

        {/* Input Area with Integrated Query Type Selector */}
        <div
          className="fade-in-up"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "var(--spacing-sm)",
            padding: "var(--spacing-md)",
            background: "var(--bg-primary)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-md)",
            transition: "box-shadow var(--transition-base)",
          }}
          onFocus={(e) => e.currentTarget.style.boxShadow = "var(--shadow-lg)"}
          onBlur={(e) => e.currentTarget.style.boxShadow = "var(--shadow-md)"}
        >
          {/* Query Type Toggle Buttons and LLM Selector */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--spacing-md)",
              flexWrap: "wrap",
            }}
          >
            {/* Query Type Toggle */}
            <div
              style={{
                display: "flex",
                gap: "var(--spacing-xs)",
                padding: "4px",
                background: "var(--gray-100)",
                borderRadius: "var(--radius-md)",
                width: "fit-content",
              }}
            >
              <button
                type="button"
                onClick={() => setQueryType("ask")}
                style={{
                  padding: "var(--spacing-xs) var(--spacing-md)",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  border: "none",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  transition: "all var(--transition-base)",
                  background: queryType === "ask" ? "var(--primary)" : "transparent",
                  color: queryType === "ask" ? "var(--text-inverse)" : "var(--text-secondary)",
                  boxShadow: queryType === "ask" ? "var(--shadow-sm)" : "none",
                }}
              >
                💬 Ask
              </button>
              <button
                type="button"
                onClick={() => setQueryType("file")}
                style={{
                  padding: "var(--spacing-xs) var(--spacing-md)",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  border: "none",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  transition: "all var(--transition-base)",
                  background: queryType === "file" ? "var(--primary)" : "transparent",
                  color: queryType === "file" ? "var(--text-inverse)" : "var(--text-secondary)",
                  boxShadow: queryType === "file" ? "var(--shadow-sm)" : "none",
                }}
              >
                📄 File Query
              </button>
            </div>

            {/* LLM Model Selector */}
            <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-sm)" }}>
              <label
                style={{
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                }}
              >
                LLM:
              </label>
              <select
                value={selectedLlmId || ""}
                onChange={(e) => setSelectedLlmId(e.target.value ? parseInt(e.target.value) : null)}
                className="input"
                style={{
                  padding: "var(--spacing-xs) var(--spacing-md)",
                  fontSize: "0.875rem",
                  border: "1px solid var(--gray-300)",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-primary)",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  minWidth: "200px",
                }}
              >
                <option value="">Default (System)</option>
                {llmConfigs.map((config) => (
                  <option key={config.id} value={config.id}>
                    {config.is_default ? "⭐ " : ""}
                    {config.provider === "openai" ? "OpenAI" : 
                     config.provider === "gemini" ? "Gemini" :
                     config.provider === "anthropic" ? "Claude" :
                     config.provider === "custom" ? "Custom" : config.provider} - {config.model_name || "default"}
                    {!config.is_active ? " (Inactive)" : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Input Row */}
          <div
            style={{
              display: "flex",
              gap: "var(--spacing-md)",
              alignItems: "flex-end",
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={queryType === "ask" ? "Ask a general question..." : "Ask a question about your documents..."}
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
      </div>
    </div>
  );
};

export default ChatPage;
