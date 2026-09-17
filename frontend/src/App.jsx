import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Bot, Trash2, Sliders, Volume2, Menu, ArrowUp, Loader2 } from 'lucide-react';
import {
  apiConversations,
  apiOllama,
  apiSettings,
  apiAuth,
  apiDocuments,
  streamChatResponse,
} from './api/client';
import {
  cacheConversations,
  getCachedConversations,
  saveCachedConversation,
  deleteCachedConversation,
  clearAllCache,
  cacheMessages,
  getCachedMessages,
  saveCachedMessage,
  deleteCachedMessage,
  enqueueOfflineMessage,
  getOfflineQueue,
  removeOfflineQueueItem,
} from './api/db';
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

  // Pagination
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

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
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const abortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);

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

  // Scroll to bottom helper
  const scrollToBottom = (behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    if (!isLoadingMore) {
      scrollToBottom();
    }
  }, [messages.length, streamContent, activeTool]);

  // Initial Load & Health check
  useEffect(() => {
    initApp();
    const interval = setInterval(checkOllamaHealth, 10000);

    // Sync offline queue when network reconnects
    const handleOnline = () => {
      syncOfflineQueue();
    };
    window.addEventListener('online', handleOnline);

    return () => {
      clearInterval(interval);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  // Theme application
  useEffect(() => {
    if (settings?.theme) {
      document.documentElement.setAttribute('data-theme', settings.theme);
    }
  }, [settings?.theme]);

  const initApp = async () => {
    try {
      // 1. Instantly hydrate from local IndexedDB cache before network finishes
      const cachedConvs = await getCachedConversations();
      if (cachedConvs && cachedConvs.length > 0) {
        setConversations(cachedConvs);
        const savedConvId = localStorage.getItem('mukku_last_conv_id');
        const targetId = cachedConvs.some((c) => c.id === savedConvId) ? savedConvId : cachedConvs[0].id;
        if (targetId) {
          setCurrentId(targetId);
          const cachedMsgs = await getCachedMessages(targetId);
          if (cachedMsgs && cachedMsgs.length > 0) {
            setMessages(cachedMsgs);
          }
        }
      }

      // 2. Auth check
      let user;
      try {
        user = await apiAuth.getMe();
      } catch {
        const guestRes = await apiAuth.getGuestToken();
        user = guestRes.user;
      }
      setCurrentUser(user);

      // 3. Load settings
      const s = await apiSettings.get();
      setSettings(s);
      setWebSearch(s.web_search_enabled || false);
      setMemoryEnabled(s.memory_enabled !== false);

      // 4. Load Ollama Status
      checkOllamaHealth();

      // 5. Load authoritative conversations from server
      await loadConversations();
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

  const loadConversations = async (preserveSelectedId = true) => {
    try {
      const list = await apiConversations.list();
      setConversations(list);
      await cacheConversations(list);

      const savedConvId = localStorage.getItem('mukku_last_conv_id');
      const targetId = preserveSelectedId && savedConvId && list.some((c) => c.id === savedConvId)
        ? savedConvId
        : list.length > 0 ? list[0].id : null;

      if (targetId && targetId !== currentId) {
        selectConversation(targetId);
      } else if (targetId && targetId === currentId) {
        // Refresh messages for current
        fetchMessages(targetId);
      }
    } catch (e) {
      console.error('Error loading conversations:', e);
    }
  };

  const fetchMessages = async (convId) => {
    try {
      const res = await apiConversations.getMessages(convId, { limit: 50 });
      setMessages(res.messages || []);
      setHasMoreMessages(res.has_more || false);
      await cacheMessages(res.messages || []);
    } catch (e) {
      console.error('Error fetching messages:', e);
      // Fallback to local cache if network fails
      const cached = await getCachedMessages(convId);
      if (cached && cached.length > 0) {
        setMessages(cached);
      }
    }
  };

  const selectConversation = async (id) => {
    if (streaming) return;
    setIsMobileSidebarOpen(false);
    setCurrentId(id);
    localStorage.setItem('mukku_last_conv_id', id);

    // Instant local cache display
    const cached = await getCachedMessages(id);
    if (cached && cached.length > 0) {
      setMessages(cached);
    }

    // Server source of truth fetch
    await fetchMessages(id);
  };

  const handleLoadEarlierMessages = async () => {
    if (!currentId || !hasMoreMessages || isLoadingMore || messages.length === 0) return;
    setIsLoadingMore(true);

    try {
      const oldestMessageId = messages[0].id;
      const res = await apiConversations.getMessages(currentId, {
        limit: 50,
        before: oldestMessageId,
      });

      if (res.messages && res.messages.length > 0) {
        setMessages((prev) => [...res.messages, ...prev]);
        setHasMoreMessages(res.has_more || false);
        await cacheMessages(res.messages);
      } else {
        setHasMoreMessages(false);
      }
    } catch (e) {
      console.error('Error loading earlier messages:', e);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleNewChat = () => {
    if (streaming) return;
    setIsMobileSidebarOpen(false);
    setCurrentId(null);
    localStorage.removeItem('mukku_last_conv_id');
    setMessages([]);
    setInput('');
    setSelectedFile(null);
    setImageBase64(null);
    setActiveTool(null);
    setActiveCitations(null);
    setHasMoreMessages(false);
  };

  const handleRename = async (id, newTitle) => {
    try {
      await apiConversations.update(id, { title: newTitle });
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: newTitle, updated_at: new Date().toISOString() } : c))
      );
      await saveCachedConversation({ id, title: newTitle, updated_at: new Date().toISOString() });
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await apiConversations.delete(id);
      await deleteCachedConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentId === id) {
        handleNewChat();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteAllConversations = async () => {
    if (!window.confirm('Are you sure you want to delete ALL conversations? This cannot be undone.')) {
      return;
    }
    try {
      await apiConversations.deleteAll();
      await clearAllCache();
      setConversations([]);
      handleNewChat();
    } catch (e) {
      console.error('Failed to delete all conversations:', e);
    }
  };

  const handleClearChat = async () => {
    if (!currentId) return;
    if (window.confirm('Clear all messages in this conversation?')) {
      try {
        await apiConversations.clear(currentId);
        setMessages([]);
        await deleteCachedConversation(currentId);
      } catch (e) {
        console.error(e);
      }
    }
  };

  const handleDeleteMessage = async (msgId) => {
    // Optimistic UI removal
    setMessages((prev) => prev.filter((m) => m.id !== msgId));
    await deleteCachedMessage(msgId);
    if (currentId) {
      try {
        await apiConversations.deleteMessage(currentId, msgId);
      } catch (e) {
        console.error('Failed to delete message on server:', e);
      }
    }
  };

  // Export / Import
  const handleExportAll = async () => {
    try {
      const data = await apiConversations.exportAll();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `mukku_conversations_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Failed to export conversations: ' + e.message);
    }
  };

  const handleExportConversation = async (id) => {
    try {
      const data = await apiConversations.exportOne(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation_${id}_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Failed to export conversation: ' + e.message);
    }
  };

  const handleImportConversations = async (jsonData) => {
    try {
      let list = [];
      if (Array.isArray(jsonData)) {
        list = jsonData;
      } else if (jsonData && Array.isArray(jsonData.conversations)) {
        list = jsonData.conversations;
      } else {
        throw new Error('Unrecognized JSON import format');
      }

      const res = await apiConversations.importConversations(list);
      alert(`Import complete! Imported ${res.imported_conversations} conversations (${res.imported_messages} messages).`);
      await loadConversations(false);
      if (res.conversation_ids && res.conversation_ids.length > 0) {
        selectConversation(res.conversation_ids[0]);
      }
    } catch (e) {
      alert('Import failed: ' + e.message);
    }
  };

  // Search across conversations and message text
  const handleSearchChange = async (query) => {
    if (!query.trim()) {
      const list = await apiConversations.list();
      setConversations(list);
      return;
    }
    try {
      const results = await apiConversations.search(query);
      setConversations(results);
    } catch {
      // fallback to client filter
    }
  };

  // Offline queue processor
  const syncOfflineQueue = async () => {
    try {
      const queue = await getOfflineQueue();
      if (!queue || !queue.length) return;
      for (const item of queue) {
        try {
          await apiConversations.createMessage(item.conversation_id, {
            role: item.role,
            content: item.content,
            message_id: item.id,
          });
          await removeOfflineQueueItem(item.id);
        } catch {
          // Keep in queue if still failing
          break;
        }
      }
    } catch (e) {
      console.warn('Offline sync error:', e);
    }
  };

  // SEND MESSAGE
  const handleSend = async (overridePrompt) => {
    const textToSend = overridePrompt || input;
    if (!textToSend.trim() && !selectedFile && !imageBase64) return;

    // Generate client-side UUID for idempotency & instant persistence
    const userMsgId = 'msg-' + (window.crypto?.randomUUID ? window.crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).substr(2, 6));

    const userMsg = {
      id: userMsgId,
      conversation_id: currentId,
      role: 'user',
      content: textToSend,
      status: 'completed',
      created_at: new Date().toISOString(),
    };

    // 1. Instantly display in UI
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setStreaming(true);
    setStreamContent('');
    setActiveTool(null);
    setActiveCitations(null);

    // 2. Instantly persist to client IndexedDB cache
    await saveCachedMessage(userMsg);

    // If offline, queue it
    if (!navigator.onLine && currentId) {
      await enqueueOfflineMessage({
        id: userMsgId,
        conversation_id: currentId,
        role: 'user',
        content: textToSend,
      });
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let fullTokens = '';
    let toolInfo = null;
    let citationsInfo = null;
    let activeConvId = currentId;

    const payload = {
      conversation_id: currentId,
      content: textToSend,
      message_id: userMsgId,
      model: settings?.ollama_model || 'qwen2.5:3b',
      temperature: settings?.temperature ?? 0.7,
      system_prompt: settings?.system_prompt,
      web_search: webSearch,
      memory_enabled: memoryEnabled,
      language: settings?.language || 'en',
      image_base64: imageBase64,
    };

    // If document file attached, upload first
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
        activeConvId = newConvId;
        setCurrentId(newConvId);
        localStorage.setItem('mukku_last_conv_id', newConvId);
      },
      onTitleUpdated: (newTitle) => {
        setConversations((prev) =>
          prev.map((c) => (c.id === activeConvId ? { ...c, title: newTitle } : c))
        );
        apiConversations.list().then((fresh) => {
          setConversations(fresh);
          cacheConversations(fresh);
        });
      },
      onDone: async (assistantMsgId, finalStatus) => {
        const assistantMsg = {
          id: assistantMsgId,
          conversation_id: activeConvId,
          role: 'assistant',
          content: fullTokens,
          status: finalStatus || 'completed',
          tool_calls: toolInfo ? JSON.stringify(toolInfo) : null,
          citations: citationsInfo ? JSON.stringify(citationsInfo) : null,
          created_at: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, assistantMsg]);
        await saveCachedMessage(assistantMsg);

        setStreaming(false);
        setStreamContent('');
        setActiveTool(null);

        // Background sync conversation list
        apiConversations.list().then((fresh) => {
          setConversations(fresh);
          cacheConversations(fresh);
        });
      },
      onError: async (err) => {
        const errorMsg = {
          id: `err-${Date.now()}`,
          conversation_id: activeConvId,
          role: 'assistant',
          content: fullTokens ? fullTokens : `⚠️ Error: ${err.message}`,
          status: 'error',
          created_at: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, errorMsg]);
        await saveCachedMessage(errorMsg);

        setStreaming(false);
        setStreamContent('');
        setActiveTool(null);
      },
    });
  };

  const handleStop = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setStreaming(false);
      if (streamContent) {
        const cancelledMsg = {
          id: `aborted-${Date.now()}`,
          conversation_id: currentId,
          role: 'assistant',
          content: streamContent,
          status: 'cancelled',
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, cancelledMsg]);
        await saveCachedMessage(cancelledMsg);
      }
      setStreamContent('');
      setActiveTool(null);
    }
  };

  const handleRegenerate = async (targetMsgId) => {
    if (streaming || !currentId) return;

    let targetIndex = -1;
    if (targetMsgId) {
      targetIndex = messages.findIndex((m) => m.id === targetMsgId);
    } else {
      // Default to last assistant message
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'assistant') {
          targetIndex = i;
          break;
        }
      }
    }

    if (targetIndex === -1) return;

    // Find the preceding user message
    let userMsg = null;
    for (let i = targetIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMsg = messages[i];
        break;
      }
    }

    if (!userMsg) return;

    // Remove the target assistant message from UI and server/cache
    const removedMsg = messages[targetIndex];
    setMessages((prev) => prev.filter((_, idx) => idx !== targetIndex));
    if (removedMsg?.id && !removedMsg.id.startsWith('temp-')) {
      deleteCachedMessage(removedMsg.id);
      apiConversations.deleteMessage(currentId, removedMsg.id).catch(() => {});
    }

    // Trigger re-generation with the user message content
    handleSend(userMsg.content);
  };

  const handleEditMessage = async (msgId, newContent) => {
    if (streaming) return;
    const idx = messages.findIndex((m) => m.id === msgId);
    if (idx === -1) return;

    // Trim messages after this one
    setMessages(messages.slice(0, idx));
    handleSend(newContent);
  };

  const handleSaveSettings = async (newSettings) => {
    try {
      const updated = await apiSettings.update(newSettings);
      setSettings(updated);
    } catch (e) {
      console.error(e);
    }
  };

  const handleAuthSuccess = async (user) => {
    setCurrentUser(user);
    setCurrentId(null);
    localStorage.removeItem('mukku_last_conv_id');
    setMessages([]);
    setInput('');
    await clearAllCache();
    await loadConversations(false);
  };

  return (
    <div className="app-container">
      {/* Mobile Backdrop */}
      {isMobileSidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* Left Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversationId={currentId}
        onSelectConversation={selectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRename}
        onDeleteAllConversations={handleDeleteAllConversations}
        onExportAll={handleExportAll}
        onExportConversation={handleExportConversation}
        onImportConversations={handleImportConversations}
        onSearchChange={handleSearchChange}
        ollamaStatus={ollamaStatus}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenMemory={() => setIsMemoryOpen(true)}
        onOpenDocuments={() => setIsDocumentsOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        currentUser={currentUser}
        isOpen={isMobileSidebarOpen}
        onClose={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Area */}
      <main className="main-chat">
        {/* Top Nav */}
        <header className="top-nav">
          <div className="nav-left">
            <button
              className="mobile-menu-btn"
              onClick={() => setIsMobileSidebarOpen(true)}
              aria-label="Open conversation menu"
              title="Menu"
            >
              <Menu size={20} />
            </button>
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
        <div className="messages-container" ref={messagesContainerRef}>
          {hasMoreMessages && (
            <div className="load-more-container">
              <button
                className="load-more-btn"
                onClick={handleLoadEarlierMessages}
                disabled={isLoadingMore}
              >
                {isLoadingMore ? (
                  <>
                    <Loader2 size={13} className="spin-animate" />
                    <span>Loading earlier messages...</span>
                  </>
                ) : (
                  <>
                    <ArrowUp size={13} />
                    <span>Load earlier messages</span>
                  </>
                )}
              </button>
            </div>
          )}

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
                    status: 'streaming',
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
        onAuthSuccess={handleAuthSuccess}
      />
    </div>
  );
}
