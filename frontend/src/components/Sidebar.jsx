import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquarePlus,
  Search,
  Settings,
  Brain,
  FileText,
  Trash2,
  Edit2,
  Check,
  X,
  Bot,
  User,
  Download,
  Upload,
  RotateCcw,
} from 'lucide-react';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  onRenameConversation,
  onDeleteAllConversations,
  onExportAll,
  onExportConversation,
  onImportConversations,
  onSearchChange,
  ollamaStatus,
  onOpenSettings,
  onOpenMemory,
  onOpenDocuments,
  onOpenAuth,
  currentUser,
  isOpen,
  onClose,
}) {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const fileInputRef = useRef(null);

  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleSearchInput = (e) => {
    const val = e.target.value;
    setSearch(val);
    if (onSearchChange) {
      onSearchChange(val);
    }
  };

  const filtered = search.trim()
    ? conversations.filter((c) =>
        (c.title || 'New Chat').toLowerCase().includes(search.toLowerCase())
      )
    : conversations;

  const startRename = (c, e) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title);
  };

  const saveRename = (id, e) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelRename = (e) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const handleDelete = (id, e) => {
    e.stopPropagation();
    if (window.confirm('Delete this conversation?')) {
      onDeleteConversation(id);
    }
  };

  const handleExportSingle = (id, e) => {
    e.stopPropagation();
    if (onExportConversation) {
      onExportConversation(id);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);
        if (onImportConversations) {
          onImportConversations(json);
        }
      } catch (err) {
        alert('Invalid JSON backup file');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-icon">
            <Bot size={20} />
          </div>
          <span>MUKKU.AI</span>
          <span className="brand-badge">Qwen 3B</span>
        </div>
        <button
          className="sidebar-close-mobile-btn"
          onClick={onClose}
          aria-label="Close sidebar"
        >
          <X size={20} />
        </button>
      </div>

      {/* New Chat Button */}
      <button
        className="new-chat-btn"
        onClick={() => {
          onNewChat();
          onClose?.();
        }}
      >
        <MessageSquarePlus size={18} />
        <span>New Chat</span>
      </button>

      {/* Search Input */}
      <div className="search-bar">
        <Search size={14} className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder="Search conversations..."
          value={search}
          onChange={handleSearchInput}
        />
        {search && (
          <button
            className="icon-btn-xs"
            onClick={() => {
              setSearch('');
              if (onSearchChange) onSearchChange('');
            }}
            style={{ marginRight: '6px' }}
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* History Utilities Bar */}
      <div className="sidebar-utils-row">
        <span>History ({conversations.length})</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {onExportAll && conversations.length > 0 && (
            <button
              className="sidebar-util-btn"
              onClick={onExportAll}
              title="Export all conversations as JSON"
            >
              <Download size={12} />
              <span>Export</span>
            </button>
          )}

          {onImportConversations && (
            <>
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept=".json"
                onChange={handleFileChange}
              />
              <button
                className="sidebar-util-btn"
                onClick={() => fileInputRef.current?.click()}
                title="Import conversations from JSON"
              >
                <Upload size={12} />
                <span>Import</span>
              </button>
            </>
          )}

          {onDeleteAllConversations && conversations.length > 0 && (
            <button
              className="sidebar-util-btn danger"
              onClick={onDeleteAllConversations}
              title="Delete all conversations"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Conversations List */}
      <div className="conversations-list">
        {filtered.length === 0 ? (
          <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.82rem' }}>
            {search ? 'No matching conversations' : 'No conversations yet'}
          </div>
        ) : (
          filtered.map((c) => {
            const isActive = c.id === currentConversationId;
            const isEditing = editingId === c.id;

            return (
              <div
                key={c.id}
                className={`conversation-item ${isActive ? 'active' : ''}`}
                onClick={() => {
                  onSelectConversation(c.id);
                  onClose?.();
                }}
              >
                {isEditing ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', width: '100%' }}>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="form-input"
                      style={{ padding: '2px 6px', fontSize: '0.82rem' }}
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveRename(c.id, e);
                        if (e.key === 'Escape') cancelRename(e);
                      }}
                    />
                    <button className="icon-btn-xs" onClick={(e) => saveRename(c.id, e)}>
                      <Check size={13} style={{ color: '#10b981' }} />
                    </button>
                    <button className="icon-btn-xs" onClick={cancelRename}>
                      <X size={13} />
                    </button>
                  </div>
                ) : (
                  <>
                    <span className="conv-title">{c.title || 'Untitled Chat'}</span>
                    <div className="conv-actions">
                      <button
                        className="icon-btn-xs"
                        onClick={(e) => handleExportSingle(c.id, e)}
                        title="Export JSON"
                      >
                        <Download size={11} />
                      </button>
                      <button
                        className="icon-btn-xs"
                        onClick={(e) => startRename(c, e)}
                        title="Rename chat"
                      >
                        <Edit2 size={11} />
                      </button>
                      <button
                        className="icon-btn-xs danger"
                        onClick={(e) => handleDelete(c.id, e)}
                        title="Delete chat"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        {/* Health Status Indicator */}
        <div className={`health-pill ${ollamaStatus?.is_online ? '' : 'offline'}`}>
          <div className="health-dot" />
          <span>
            {ollamaStatus?.is_online
              ? `Ollama Connected · ${ollamaStatus.model_installed ? 'Qwen2.5 Ready' : 'Model Missing'}`
              : 'Ollama Offline'}
          </span>
        </div>

        <button
          className="footer-nav-btn"
          onClick={() => {
            onOpenDocuments();
            onClose?.();
          }}
        >
          <FileText size={16} />
          <span>Document Assistant (RAG)</span>
        </button>

        <button
          className="footer-nav-btn"
          onClick={() => {
            onOpenMemory();
            onClose?.();
          }}
        >
          <Brain size={16} />
          <span>Long-term Memory</span>
        </button>

        <button
          className="footer-nav-btn"
          onClick={() => {
            onOpenSettings();
            onClose?.();
          }}
        >
          <Settings size={16} />
          <span>Settings & Model Config</span>
        </button>

        <button
          className="footer-nav-btn"
          onClick={() => {
            onOpenAuth();
            onClose?.();
          }}
        >
          <User size={16} />
          <span>{currentUser?.is_guest ? 'Guest Profile' : currentUser?.username || 'User Profile'}</span>
        </button>
      </div>
    </aside>
  );
}
