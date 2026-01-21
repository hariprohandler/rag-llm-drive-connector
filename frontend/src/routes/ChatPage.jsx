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
  const [queryType, setQueryType] = useState("ask"); // "ask" or "file"
  const [sourceFilter, setSourceFilter] = useState("all"); // "all", "document", "zendesk"
  const [databaseConnections, setDatabaseConnections] = useState([]);
  const [selectedDatabaseId, setSelectedDatabaseId] = useState(null);
  const [loadingDatabases, setLoadingDatabases] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [llmConfigs, setLlmConfigs] = useState([]);
  const [selectedLlmId, setSelectedLlmId] = useState(null);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [showHistory, setShowHistory] = useState(true);
  const [showLLMDropdown, setShowLLMDropdown] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeUploadTask, setActiveUploadTask] = useState(null);
  const [taskProgress, setTaskProgress] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const llmDropdownRef = useRef(null);
  const fileInputRef = useRef(null);

  // Load conversations and LLM configs on mount
  useEffect(() => {
    loadConversations();
    loadLLMConfigs();
    loadDatabaseConnections();
  }, []);

  // Load messages when conversation changes
  useEffect(() => {
    if (currentConversationId) {
      loadConversationMessages(currentConversationId);
    } else {
      setMessages([]);
    }
  }, [currentConversationId]);

  // Poll upload task progress
  useEffect(() => {
    if (activeUploadTask) {
      const interval = setInterval(async () => {
        try {
          const task = await api.getIngestionTaskStatus(activeUploadTask);
          setTaskProgress(task);
          
          if (task.status === "completed" || task.status === "failed") {
            clearInterval(interval);
            setActiveUploadTask(null);
            setUploading(false);
            
            // Update existing upload message
            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m.isUploading || m.taskId === activeUploadTask);
              if (msgIndex !== -1) {
                updated[msgIndex] = {
                  ...updated[msgIndex],
                  content: task.status === "completed"
                    ? `✅ Files uploaded successfully! Knowledge base ID: ${task.knowledge_base_id || "N/A"}. You can now ask questions about these documents using RAG Search.`
                    : `❌ File upload failed: ${task.error || "Unknown error"}`,
                  isSystem: true,
                  isUploading: false,
                };
              }
              return updated;
            });
            
            if (task.status === "completed") {
              // Switch to RAG search mode
              setQueryType("file");
            }
          }
        } catch (e) {
          console.error("Error fetching task status:", e);
        }
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [activeUploadTask]);

  // Update upload message when task progress changes
  useEffect(() => {
    if (taskProgress && activeUploadTask) {
      setMessages((prev) => {
        const updated = [...prev];
        const msgIndex = updated.findIndex((m) => m.isUploading || m.taskId === activeUploadTask);
        if (msgIndex !== -1) {
          updated[msgIndex] = {
            ...updated[msgIndex],
            content: taskProgress.status === "running"
              ? `📤 Processing files... ${taskProgress.message || ""}`
              : updated[msgIndex].content,
          };
        }
        return updated;
      });
    }
  }, [taskProgress, activeUploadTask]);

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

  const loadDatabaseConnections = async () => {
    try {
      setLoadingDatabases(true);
      const connections = await api.listDatabaseConnections();
      setDatabaseConnections(connections || []);
      // Set default database (first active connection)
      if (connections && connections.length > 0) {
        const activeConnection = connections.find(c => c.is_active) || connections[0];
        if (activeConnection) {
          setSelectedDatabaseId(activeConnection.id);
        }
      }
    } catch (e) {
      console.error("Error loading database connections:", e);
    } finally {
      setLoadingDatabases(false);
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
    setQueryType("ask"); // Default to "Ask" for new conversations
    // Reset database selection to default (first active connection)
    if (databaseConnections.length > 0) {
      const activeConnection = databaseConnections.find(c => c.is_active) || databaseConnections[0];
      if (activeConnection) {
        setSelectedDatabaseId(activeConnection.id);
      }
    }
    // Keep history visible - only hide when user explicitly clicks hide button
  };

  const selectConversation = async (conversationId) => {
    setCurrentConversationId(conversationId);
    // Keep history visible - only hide when user explicitly clicks hide button
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

    // Create placeholder for streaming response
    const assistantMessageId = Date.now() + 1;
    let assistantMessage = {
      role: "assistant",
      content: "",
      sources: [],
      queryType: queryType,
      id: assistantMessageId,
      isStreaming: true,
    };
    setMessages([...newMessages, assistantMessage]);

    try {
      let conversationId = currentConversationId;
      let sources = [];
      let fullAnswer = "";

      await api.sendChatMessage(
        {
          content: userMessage.content,
          conversation_id: currentConversationId,
          use_rag: queryType === "file",
          llm_config_id: selectedLlmId,
          source_filter: queryType === "file" ? sourceFilter : null,
          database_connection_id: selectedDatabaseId || null,
        },
        (data) => {
          // Handle streaming data
          if (data.type === "token") {
            fullAnswer += data.content;
            // Update the assistant message in real-time
            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
              if (msgIndex !== -1) {
                updated[msgIndex] = {
                  ...updated[msgIndex],
                  content: fullAnswer,
                };
              }
              return updated;
            });
          } else if (data.type === "sources") {
            sources = data.sources || [];
            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
              if (msgIndex !== -1) {
                updated[msgIndex] = {
                  ...updated[msgIndex],
                  sources: sources,
                };
              }
              return updated;
            });
          } else if (data.type === "done") {
            // Final update
            if (data.conversation_id && !conversationId) {
              conversationId = data.conversation_id;
              setCurrentConversationId(conversationId);
              loadConversations();
            }
            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
              if (msgIndex !== -1) {
                updated[msgIndex] = {
                  ...updated[msgIndex],
                  content: data.answer || fullAnswer,
                  sources: data.sources || sources,
                  isStreaming: false,
                };
              }
              return updated;
            });
            setLoading(false);
          } else if (data.type === "error") {
            setError(data.error || "An error occurred");
            setMessages((prev) => {
              const updated = [...prev];
              const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
              if (msgIndex !== -1) {
                updated[msgIndex] = {
                  ...updated[msgIndex],
                  content: `Error: ${data.error || "An error occurred"}`,
                  isError: true,
                  isStreaming: false,
                };
              }
              return updated;
            });
            setLoading(false);
          }
        }
      );

      // Update conversation ID if this was a new conversation
      if (conversationId && !currentConversationId) {
        setCurrentConversationId(conversationId);
        await loadConversations();
      }
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
      setMessages((prev) => {
        const updated = [...prev];
        const msgIndex = updated.findIndex((m) => m.id === assistantMessageId);
        if (msgIndex !== -1) {
          updated[msgIndex] = {
            ...updated[msgIndex],
            content: `Error: ${errorMessage}`,
            isError: true,
            isStreaming: false,
          };
        }
        return updated;
      });
      setLoading(false);
    } finally {
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    setError(null);

    // Add upload started message
    const uploadMessage = {
      id: Date.now(),
      role: "system",
      content: `📤 Uploading ${files.length} file(s)...`,
      isSystem: true,
      isUploading: true,
    };
    setMessages((prev) => [...prev, uploadMessage]);

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));

    try {
      const res = await fetch(
        `${import.meta.env.VITE_BACKEND_BASE_URL || "http://localhost:8000"}/api/ingest/upload`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || "Upload failed");
      }

      const data = await res.json();
      
      if (data.task_id) {
        // Async upload - start polling for progress
        setActiveUploadTask(data.task_id);
        // Update upload message
        setMessages((prev) => {
          const updated = [...prev];
          const msgIndex = updated.findIndex((m) => m.id === uploadMessage.id);
          if (msgIndex !== -1) {
            updated[msgIndex] = {
              ...updated[msgIndex],
              content: `📤 Processing ${files.length} file(s) in background...`,
              taskId: data.task_id,
            };
          }
          return updated;
        });
      } else {
        // Legacy synchronous response (shouldn't happen with new API)
        setUploading(false);
        setMessages((prev) => {
          const updated = [...prev];
          const msgIndex = updated.findIndex((m) => m.id === uploadMessage.id);
          if (msgIndex !== -1) {
            updated[msgIndex] = {
              ...updated[msgIndex],
              content: `✅ Successfully uploaded ${files.length} file(s). Knowledge base ID: ${data.knowledge_base_id || "N/A"}. You can now ask questions about these documents using RAG Search.`,
              isUploading: false,
            };
          }
          return updated;
        });
        setQueryType("file");
      }
    } catch (e) {
      setUploading(false);
      setError(`File upload error: ${e.message}`);
      setMessages((prev) => {
        const updated = [...prev];
        const msgIndex = updated.findIndex((m) => m.id === uploadMessage.id);
        if (msgIndex !== -1) {
          updated[msgIndex] = {
            ...updated[msgIndex],
            content: `❌ File upload failed: ${e.message}`,
            isUploading: false,
          };
        }
        return updated;
      });
    }
  };

  const handleFileInput = (e) => {
    handleFileUpload(e.target.files);
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const getLLMDisplayName = (llmId) => {
    if (!llmId) return "Default (System)";
    const config = llmConfigs.find(c => c.id === llmId);
    if (!config) return "Default (System)";
    const providerNames = {
      openai: "OpenAI",
      gemini: "Gemini",
      anthropic: "Claude",
      custom: "Custom"
    };
    return `${providerNames[config.provider] || config.provider} - ${config.model_name || "default"}`;
  };

  const getLLMProviderIcon = (provider) => {
    switch (provider) {
      case "openai": return "🤖";
      case "gemini": return "💎";
      case "anthropic": return "🧠";
      case "custom": return "⚙️";
      default: return "🔧";
    }
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (llmDropdownRef.current && !llmDropdownRef.current.contains(event.target)) {
        setShowLLMDropdown(false);
      }
    };

    if (showLLMDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showLLMDropdown]);

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
                    background: m.isSystem 
                      ? "var(--primary-light)" 
                      : m.role === "user" 
                        ? "var(--primary)" 
                        : "var(--gray-100)",
                    color: m.isSystem 
                      ? "var(--text-primary)" 
                      : m.role === "user" 
                        ? "var(--text-inverse)" 
                        : "var(--text-primary)",
                    alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                    maxWidth: "80%",
                    marginLeft: m.role === "user" ? "auto" : 0,
                    marginRight: m.role === "user" ? 0 : "auto",
                    border: m.isError 
                      ? "1px solid var(--error)" 
                      : m.isSystem 
                        ? "1px solid var(--primary)" 
                        : "none",
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
                    {m.isSystem ? "🔔" : m.role === "user" ? "👤" : "🤖"}
                  </div>
                  <div style={{ flex: 1, wordBreak: "break-word" }}>
                    <div style={{ fontWeight: 600, marginBottom: "var(--spacing-xs)", fontSize: "0.875rem" }}>
                      {m.isSystem ? "System" : m.role === "user" ? "You" : "Assistant"}
                    </div>
                    <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
                      {m.content}
                      {m.isStreaming && (
                        <span
                          style={{
                            display: "inline-block",
                            width: "8px",
                            height: "16px",
                            background: "currentColor",
                            marginLeft: "2px",
                            animation: "blink 1s infinite",
                          }}
                        >
                          |
                        </span>
                      )}
                    </div>
                    {m.isSystem && (
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
                        <span>🔔</span>
                        <span>System Message</span>
                      </div>
                    )}
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
                    {m.isUploading && taskProgress && (
                      <div
                        style={{
                          marginTop: "var(--spacing-sm)",
                          paddingTop: "var(--spacing-sm)",
                          borderTop: "1px solid rgba(0, 0, 0, 0.1)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--spacing-xs)" }}>
                          <span style={{ fontSize: "0.75rem" }}>{taskProgress.message || "Processing..."}</span>
                          <span style={{ fontSize: "0.75rem", fontWeight: 600 }}>
                            {taskProgress.progress?.toFixed(1) || 0}%
                          </span>
                        </div>
                        <div
                          style={{
                            width: "100%",
                            height: "8px",
                            background: "rgba(0, 0, 0, 0.1)",
                            borderRadius: "var(--radius-full)",
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              width: `${taskProgress.progress || 0}%`,
                              height: "100%",
                              background: taskProgress.status === "failed" ? "var(--error)" : "var(--primary)",
                              transition: "width 0.3s ease",
                            }}
                          />
                        </div>
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
                        <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)", marginBottom: "var(--spacing-xs)" }}>
                          <span>📚</span>
                          <strong>Sources ({m.sources.length}):</strong>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-xs)", marginLeft: "1.5rem" }}>
                          {m.sources.map((source, idx) => {
                            const sourceType = source.metadata?.source || "document";
                            const sourceIcon = sourceType === "zendesk" ? "🎫" : "📄";
                            const sourceName = source.metadata?.file_name || source.metadata?.ticket_id || `Source ${idx + 1}`;
                            return (
                              <div key={idx} style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}>
                                <span>{sourceIcon}</span>
                                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {sourceName}
                                </span>
                              </div>
                            );
                          })}
                        </div>
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
                📄 RAG Search
              </button>
            </div>

            {/* Source Filter - Only show when RAG Search is selected */}
            {queryType === "file" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-xs)",
                  padding: "4px",
                  background: "var(--gray-100)",
                  borderRadius: "var(--radius-md)",
                  width: "fit-content",
                }}
              >
                <button
                  type="button"
                  onClick={() => setSourceFilter("all")}
                  style={{
                    padding: "var(--spacing-xs) var(--spacing-md)",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    transition: "all var(--transition-base)",
                    background: sourceFilter === "all" ? "var(--primary)" : "transparent",
                    color: sourceFilter === "all" ? "var(--text-inverse)" : "var(--text-secondary)",
                    boxShadow: sourceFilter === "all" ? "var(--shadow-sm)" : "none",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--spacing-xs)",
                  }}
                  title="Search all sources"
                >
                  <span>🌐</span>
                  <span>All</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSourceFilter("document")}
                  style={{
                    padding: "var(--spacing-xs) var(--spacing-md)",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    transition: "all var(--transition-base)",
                    background: sourceFilter === "document" ? "var(--primary)" : "transparent",
                    color: sourceFilter === "document" ? "var(--text-inverse)" : "var(--text-secondary)",
                    boxShadow: sourceFilter === "document" ? "var(--shadow-sm)" : "none",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--spacing-xs)",
                  }}
                  title="Search documents only"
                >
                  <span>📄</span>
                  <span>Documents</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSourceFilter("zendesk")}
                  style={{
                    padding: "var(--spacing-xs) var(--spacing-md)",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    transition: "all var(--transition-base)",
                    background: sourceFilter === "zendesk" ? "var(--primary)" : "transparent",
                    color: sourceFilter === "zendesk" ? "var(--text-inverse)" : "var(--text-secondary)",
                    boxShadow: sourceFilter === "zendesk" ? "var(--shadow-sm)" : "none",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--spacing-xs)",
                  }}
                  title="Search Zendesk tickets only"
                >
                  <span>🎫</span>
                  <span>Zendesk</span>
                </button>
              </div>
            )}

            {/* Database Connection Selector - Show when databases are available */}
            {databaseConnections.length > 0 && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-sm)",
                  padding: "4px",
                  background: "var(--gray-100)",
                  borderRadius: "var(--radius-md)",
                  width: "fit-content",
                }}
              >
                <label
                  style={{
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    color: "var(--text-primary)",
                    whiteSpace: "nowrap",
                    paddingLeft: "var(--spacing-xs)",
                  }}
                >
                  Database:
                </label>
                <select
                  value={selectedDatabaseId || ""}
                  onChange={(e) => setSelectedDatabaseId(e.target.value ? parseInt(e.target.value) : null)}
                  style={{
                    padding: "var(--spacing-xs) var(--spacing-md)",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    border: "1px solid var(--gray-300)",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--background)",
                    color: "var(--text-primary)",
                    cursor: "pointer",
                    minWidth: "200px",
                  }}
                  title="Select database for SQL queries"
                >
                  <option value="">Auto-detect</option>
                  {databaseConnections
                    .filter((conn) => conn.is_active)
                    .map((conn) => (
                      <option key={conn.id} value={conn.id}>
                        {conn.db_type === "postgresql" ? "🐘" : conn.db_type === "mysql" ? "🐬" : "💾"} {conn.name} ({conn.db_type.toUpperCase()})
                      </option>
                    ))}
                </select>
              </div>
            )}

            {/* LLM Model Selector - Custom Dropdown */}
            <div 
              ref={llmDropdownRef}
              style={{ 
                position: "relative",
                display: "flex",
                alignItems: "center",
                gap: "var(--spacing-sm)"
              }}
            >
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
              <div style={{ position: "relative" }}>
                <button
                  type="button"
                  onClick={() => setShowLLMDropdown(!showLLMDropdown)}
                  className="hover-lift"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--spacing-sm)",
                    padding: "var(--spacing-xs) var(--spacing-md)",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    border: "1px solid var(--gray-300)",
                    borderRadius: "var(--radius-md)",
                    background: "var(--bg-primary)",
                    color: "var(--text-primary)",
                    cursor: "pointer",
                    minWidth: "220px",
                    justifyContent: "space-between",
                    transition: "all var(--transition-base)",
                    boxShadow: showLLMDropdown ? "var(--shadow-lg)" : "var(--shadow-sm)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)", flex: 1 }}>
                    {selectedLlmId ? (
                      <>
                        <span style={{ fontSize: "1rem" }}>
                          {getLLMProviderIcon(llmConfigs.find(c => c.id === selectedLlmId)?.provider || "")}
                        </span>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {getLLMDisplayName(selectedLlmId)}
                        </span>
                        {llmConfigs.find(c => c.id === selectedLlmId)?.is_default && (
                          <span style={{ fontSize: "0.75rem" }}>⭐</span>
                        )}
                      </>
                    ) : (
                      <>
                        <span style={{ fontSize: "1rem" }}>🔧</span>
                        <span>Default (System)</span>
                      </>
                    )}
                  </div>
                  <span style={{ 
                    fontSize: "0.75rem",
                    transition: "transform var(--transition-base)",
                    transform: showLLMDropdown ? "rotate(180deg)" : "rotate(0deg)"
                  }}>
                    ▼
                  </span>
                </button>

                {/* Dropdown Menu */}
                {showLLMDropdown && (
                  <div
                    className="fade-in-down"
                    style={{
                      position: "absolute",
                      top: "100%",
                      left: 0,
                      right: 0,
                      marginTop: "var(--spacing-xs)",
                      background: "var(--bg-primary)",
                      border: "1px solid var(--gray-300)",
                      borderRadius: "var(--radius-md)",
                      boxShadow: "var(--shadow-lg)",
                      zIndex: 1000,
                      maxHeight: "300px",
                      overflowY: "auto",
                      minWidth: "280px",
                    }}
                  >
                    {/* Default Option */}
                    <div
                      onClick={() => {
                        setSelectedLlmId(null);
                        setShowLLMDropdown(false);
                      }}
                      className="hover-lift"
                      style={{
                        padding: "var(--spacing-sm) var(--spacing-md)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--spacing-sm)",
                        background: selectedLlmId === null ? "var(--primary-light)" : "transparent",
                        borderLeft: selectedLlmId === null ? "3px solid var(--primary)" : "3px solid transparent",
                        transition: "all var(--transition-base)",
                      }}
                      onMouseEnter={(e) => {
                        if (selectedLlmId !== null) {
                          e.currentTarget.style.background = "var(--gray-50)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (selectedLlmId !== null) {
                          e.currentTarget.style.background = "transparent";
                        }
                      }}
                    >
                      <span style={{ fontSize: "1rem" }}>🔧</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>Default (System)</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Use system default LLM</div>
                      </div>
                      {selectedLlmId === null && (
                        <span style={{ color: "var(--primary)", fontSize: "0.875rem" }}>✓</span>
                      )}
                    </div>

                    {/* Divider */}
                    {llmConfigs.length > 0 && (
                      <div style={{ 
                        height: "1px", 
                        background: "var(--gray-200)", 
                        margin: "var(--spacing-xs) 0" 
                      }} />
                    )}

                    {/* LLM Config Options */}
                    {llmConfigs.map((config) => {
                      const isSelected = selectedLlmId === config.id;
                      const providerName = config.provider === "openai" ? "OpenAI" : 
                                         config.provider === "gemini" ? "Gemini" :
                                         config.provider === "anthropic" ? "Claude" :
                                         config.provider === "custom" ? "Custom" : config.provider;
                      
                      return (
                        <div
                          key={config.id}
                          onClick={() => {
                            setSelectedLlmId(config.id);
                            setShowLLMDropdown(false);
                          }}
                          className="hover-lift"
                          style={{
                            padding: "var(--spacing-sm) var(--spacing-md)",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "var(--spacing-sm)",
                            background: isSelected ? "var(--primary-light)" : "transparent",
                            borderLeft: isSelected ? "3px solid var(--primary)" : "3px solid transparent",
                            transition: "all var(--transition-base)",
                            opacity: config.is_active ? 1 : 0.6,
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = "var(--gray-50)";
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = "transparent";
                            }
                          }}
                        >
                          <span style={{ fontSize: "1.25rem" }}>
                            {getLLMProviderIcon(config.provider)}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ 
                              display: "flex", 
                              alignItems: "center", 
                              gap: "var(--spacing-xs)",
                              fontWeight: 500,
                              fontSize: "0.875rem"
                            }}>
                              <span>{providerName}</span>
                              {config.is_default && (
                                <span style={{ 
                                  fontSize: "0.75rem",
                                  padding: "2px var(--spacing-xs)",
                                  background: "var(--warning-light)",
                                  color: "var(--warning-dark)",
                                  borderRadius: "var(--radius-sm)",
                                  fontWeight: 600
                                }}>
                                  ⭐ Default
                                </span>
                              )}
                              {!config.is_active && (
                                <span style={{ 
                                  fontSize: "0.75rem",
                                  padding: "2px var(--spacing-xs)",
                                  background: "var(--gray-200)",
                                  color: "var(--text-secondary)",
                                  borderRadius: "var(--radius-sm)",
                                  fontWeight: 500
                                }}>
                                  Inactive
                                </span>
                              )}
                            </div>
                            <div style={{ 
                              fontSize: "0.75rem", 
                              color: "var(--text-secondary)",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap"
                            }}>
                              {config.model_name || "default"}
                            </div>
                          </div>
                          {isSelected && (
                            <span style={{ color: "var(--primary)", fontSize: "0.875rem" }}>✓</span>
                          )}
                        </div>
                      );
                    })}

                    {/* Empty State */}
                    {llmConfigs.length === 0 && (
                      <div style={{ 
                        padding: "var(--spacing-lg)", 
                        textAlign: "center",
                        color: "var(--text-secondary)",
                        fontSize: "0.875rem"
                      }}>
                        No LLM configurations available
                      </div>
                    )}
                  </div>
                )}
              </div>
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
              disabled={loading || uploading}
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
            <label
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: uploading || loading ? "not-allowed" : "pointer",
                padding: "var(--spacing-md)",
                minWidth: "44px",
                height: "44px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--gray-300)",
                background: uploading || loading ? "var(--gray-100)" : "var(--bg-primary)",
                transition: "all var(--transition-base)",
                opacity: uploading || loading ? 0.6 : 1,
              }}
              title="Upload files"
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileInput}
                disabled={uploading || loading}
                style={{ display: "none" }}
                accept=".pdf,.docx,.doc,.txt,.md,.csv"
              />
              <span style={{ fontSize: "1.25rem" }}>📎</span>
            </label>
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim() || uploading}
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
