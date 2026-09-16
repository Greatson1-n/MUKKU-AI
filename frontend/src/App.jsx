import React, { useState, useEffect, useRef } from 'react';
import { Bot, Trash2, Sliders, Volume2 } from 'lucide-react';
import {
  apiConversations,
  apiOllama,
  apiSettings,
  apiAuth,
  apiDocuments,
  streamChatResponse,
} from './api/client';
import { useSpeech } from './hooks/useSpeech';

import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import MessageItem from './components/MessageItem';
import InputArea from './components/InputArea';
import ToolStatus from './components/ToolStatus';
import SettingsModal from './components/SettingsModal';
import MemoryModal from './components/MemoryModal';
import DocumentModal from './components/DocumentModal';
import AuthModal from './components/AuthModal';

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [currentId, setCurrentId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState('');
  const [activeTool, setActiveTool] = useState(null);
  const [activeCitations, setActiveCitations] = useState(null);

  // Attachment & Toggles
  const [webSearch, setWebSearch] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null);
  const [imageBase64, setImageBase64] = useState(null);

  // App & Ollama Status
  const [ollamaStatus, setOllamaStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);

  // Modals
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMemoryOpen, setIsMemoryOpen] = useState(false);
  const [isDocumentsOpen, setIsDocumentsOpen] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  const abortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);

  const {
    speechSupported,
    recognitionSupported,
    isListening,
    startListening,
    stopListening,
    isSpeaking,
    speak,
    stopSpeaking,
  } = useSpeech();

  // Scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamContent, activeTool]);

  // Initial Load
  useEffect(() => {
    initApp();
    const interval = setInterval(checkOllamaHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Theme application
  useEffect(() => {
    if (settings?.theme) {
      document.documentElement.setAttribute('data-theme', settings.theme);
    }
  }, [settings?.theme]);

  const initApp = async () => {
    try {
      // 1. Auth check
      let user;
      try {
        user = await apiAuth.getMe();
      } catch {
        const guestRes = await apiAuth.getGuestToken();
        user = guestRes.user;
      }
      setCurrentUser(user);

      // 2. Load settings
      const s = await apiSettings.get();
      setSettings(s);
      setWebSearch(s.web_search_enabled || false);
      setMemoryEnabled(s.memory_enabled !== false);

      // 3. Load Ollama Status
      checkOllamaHealth();

      // 4. Load conversations
      loadConversations();
    } catch (e) {
      console.error('App init error:', e);
    }
  };

  const checkOllamaHealth = async () => {
    try {
      const status = await apiOllama.getStatus();
      setOllamaStatus(status);
    } catch (err) {
      setOllamaStatus({ is_online: false, error: err.message });
    }
  };

  const loadConversations = async () => {
    try {
      const list = await apiConversations.list();
      setConversations(list);
      if (list.length > 0 && !currentId) {
        selectConversation(list[0].id);
      }
    } catch (e) {
      console.error('Error loading conversations:', e);
    }
  };

  const selectConversation = async (id) => {
    if (streaming) return;
    setCurrentId(id);
    try {
      const detail = await apiConversations.get(id);
      setMessages(detail.messages || []);
    } catch (e) {
      console.error('Error fetching conversation details:', e);
    }
  };

  const handleNewChat = () => {
    if (streaming) return;
    setCurrentId(null);
    setMessages([]);
    setInput('');
    setSelectedFile(null);
    setImageBase64(null);
    setActiveTool(null);
    setActiveCitations(null);
  };

  const handleRename = async (id, newTitle) => {
    try {
      await apiConversations.update(id, { title: newTitle });
      loadConversations();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await apiConversations.delete(id);
      if (currentId === id) {
        handleNewChat();
      }
      loadConversations();
    } catch (e) {
      console.error(e);
    }
  };

  const handleClearChat = async () => {
    if (!currentId) return;
    if (window.confirm('Clear all messages in this conversation?')) {
      try {
        await apiConversations.clear(currentId);
        setMessages([]);
      } catch (e) {
        console.error(e);
      }
    }
  };

  // SEND MESSAGE
  const handleSend = async (overridePrompt) => {
    const textToSend = overridePrompt || input;
    if (!textToSend.trim() && !selectedFile && !imageBase64) return;

    // Build temporary user message
    const userMsg = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: textToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setStreaming(true);
    setStreamContent('');
    setActiveTool(null);
    setActiveCitations(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let fullTokens = '';
    let toolInfo = null;
    let citationsInfo = null;

    const payload = {
      conversation_id: currentId,
      content: textToSend,
      model: settings?.ollama_model || 'qwen2.5:3b',
      temperature: settings?.temperature ?? 0.7,
      system_prompt: settings?.system_prompt,
      web_search: webSearch,
      memory_enabled: memoryEnabled,
      language: settings?.language || 'en',
      image_base64: imageBase64,
    };

    // If file was attached, upload it first if doc
    if (selectedFile?.type === 'doc') {
      try {
        setActiveTool({ tool: 'document', status: 'Uploading & indexing document...' });
        const uploadedDoc = await apiDocuments.upload(selectedFile.file);
        payload.document_ids = [uploadedDoc.id];
      } catch (err) {
        console.error('Doc upload error:', err);
      }
    }

    // Reset attachments
    setSelectedFile(null);
    setImageBase64(null);

    await streamChatResponse({
      payload,
      signal: controller.signal,
      onToken: (token) => {
        fullTokens += token;
        setStreamContent((prev) => prev + token);
      },
      onToolStart: (tool, status) => {
        setActiveTool({ tool, status });
        toolInfo = { tool, status };
      },
      onToolEnd: (tool, status) => {
        setActiveTool(null);
        if (toolInfo) toolInfo.status = status;
      },
      onCitations: (c) => {
        setActiveCitations(c);
        citationsInfo = c;
      },
      onConversationCreated: (newConvId) => {
        setCurrentId(newConvId);
      },
      onTitleUpdated: (newTitle) => {
        loadConversations();
      },
      onDone: (messageId) => {
        setMessages((prev) => [
          ...prev,
          {
            id: messageId,
            role: 'assistant',
            content: fullTokens,
            tool_calls: toolInfo ? JSON.stringify(toolInfo) : null,
            citations: citationsInfo ? JSON.stringify(citationsInfo) : null,
            created_at: new Date().toISOString(),
          },
        ]);
        setStreaming(false);
        setStreamContent('');
        setActiveTool(null);
        loadConversations();
      },
      onError: (err) => {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content: `⚠️ Error: ${err.message}`,
            created_at: new Date().toISOString(),
          },
        ]);
        setStreaming(false);
        setStreamContent('');
        setActiveTool(null);
      },
    });
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setStreaming(false);
      if (streamContent) {
        setMessages((prev) => [
          ...prev,
          {
            id: `aborted-${Date.now()}`,
            role: 'assistant',
            content: streamContent + '\n\n*(Generation stopped by user)*',
            created_at: new Date().toISOString(),
          },
        ]);
      }
      setStreamContent('');
      setActiveTool(null);
    }
  };

  const handleRegenerate = async () => {
    if (streaming || !currentId) return;

    // Remove last assistant message
    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUser) return;

    setMessages((prev) => prev.slice(0, -1));
    handleSend(lastUser.content);
  };

  const handleEditMessage = async (msgId, newContent) => {
    if (streaming) return;
    // Find message index
    const idx = messages.findIndex((m) => m.id === msgId);
    if (idx === -1) return;

    // Trim messages after this one
    setMessages(messages.slice(0, idx));
    handleSend(newContent);
  };

  const handleDeleteMessage = (msgId) => {
    setMessages((prev) => prev.filter((m) => m.id !== msgId));
  };

  const handleSaveSettings = async (newSettings) => {
    try {
      const updated = await apiSettings.update(newSettings);
      setSettings(updated);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversationId={currentId}
        onSelectConversation={selectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRename}
        ollamaStatus={ollamaStatus}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenMemory={() => setIsMemoryOpen(true)}
        onOpenDocuments={() => setIsDocumentsOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        currentUser={currentUser}
      />

      {/* Main Area */}
      <main className="main-chat">
        {/* Top Nav */}
        <header className="top-nav">
          <div className="nav-left">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '0.92rem' }}>
              <Bot size={18} style={{ color: 'var(--accent-primary)' }} />
              <span>{settings?.ollama_model || 'qwen2.5:3b'}</span>
            </div>
            {activeTool && <ToolStatus tool={activeTool.tool} status={activeTool.status} />}
          </div>

          <div className="nav-right">
            {messages.length > 0 && (
              <button
                className="icon-btn-xs danger"
                onClick={handleClearChat}
                title="Clear conversation"
                style={{ padding: '6px 10px', borderRadius: '6px' }}
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </header>

        {/* Messages list / Welcome Screen */}
        <div className="messages-container">
          {messages.length === 0 && !streaming ? (
            <WelcomeScreen onSelectPrompt={(prompt) => handleSend(prompt)} />
          ) : (
            <>
              {messages.map((m, idx) => (
                <MessageItem
                  key={m.id || idx}
                  message={m}
                  onRegenerate={handleRegenerate}
                  onEdit={handleEditMessage}
                  onDelete={handleDeleteMessage}
                  onSpeak={speak}
                  isSpeaking={isSpeaking}
                  isLastAssistant={idx === messages.length - 1 && m.role === 'assistant'}
                  streaming={streaming}
                />
              ))}

              {/* In-flight streaming message */}
              {streaming && streamContent && (
                <MessageItem
                  message={{
                    id: 'streaming-active',
                    role: 'assistant',
                    content: streamContent,
                    citations: activeCitations,
                  }}
                  streaming={true}
                />
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Bottom Input Area */}
        <InputArea
          input={input}
          setInput={setInput}
          onSend={() => handleSend()}
          onStop={handleStop}
          streaming={streaming}
          webSearch={webSearch}
          setWebSearch={setWebSearch}
          memoryEnabled={memoryEnabled}
          setMemoryEnabled={setMemoryEnabled}
          selectedFile={selectedFile}
          setSelectedFile={setSelectedFile}
          imageBase64={imageBase64}
          setImageBase64={setImageBase64}
          isListening={isListening}
          startListening={startListening}
          stopListening={stopListening}
          recognitionSupported={recognitionSupported}
        />
      </main>

      {/* Modals */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSave={handleSaveSettings}
        ollamaStatus={ollamaStatus}
      />

      <MemoryModal isOpen={isMemoryOpen} onClose={() => setIsMemoryOpen(false)} />

      <DocumentModal isOpen={isDocumentsOpen} onClose={() => setIsDocumentsOpen(false)} />

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        currentUser={currentUser}
        onAuthSuccess={(u) => setCurrentUser(u)}
      />
    </div>
  );
}
