import React, { useState } from 'react';
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
  Activity
} from 'lucide-react';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  onRenameConversation,
  ollamaStatus,
  onOpenSettings,
  onOpenMemory,
  onOpenDocuments,
  onOpenAuth,
  currentUser,
}) {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');

  const filtered = conversations.filter((c) =>
    (c.title || 'New Chat').toLowerCase().includes(search.toLowerCase())
  );

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

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-icon">
            <Bot size={20} />
          </div>
          <span>MUKKU.AI</span>
          <span className="brand-badge">Qwen 3B</span>
        </div>
      </div>

      {/* New Chat Button */}
      <button className="new-chat-btn" onClick={onNewChat}>
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
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Conversations List */}
      <div className="conversations-list">
        {filtered.map((c) => {
          const isActive = c.id === currentConversationId;
          const isEditing = editingId === c.id;

          return (
            <div
              key={c.id}
              className={`conversation-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectConversation(c.id)}
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
                    <button className="icon-btn-xs" onClick={(e) => startRename(c, e)} title="Rename chat">
                      <Edit2 size={12} />
                    </button>
                    <button className="icon-btn-xs danger" onClick={(e) => handleDelete(c.id, e)} title="Delete chat">
                      <Trash2 size={12} />
                    </button>
                  </div>
                </>
              )}
            </div>
          );
        })}
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

        <button className="footer-nav-btn" onClick={onOpenDocuments}>
          <FileText size={16} />
          <span>Document Assistant (RAG)</span>
        </button>

        <button className="footer-nav-btn" onClick={onOpenMemory}>
          <Brain size={16} />
          <span>Long-term Memory</span>
        </button>

        <button className="footer-nav-btn" onClick={onOpenSettings}>
          <Settings size={16} />
          <span>Settings & Model Config</span>
        </button>

        <button className="footer-nav-btn" onClick={onOpenAuth}>
          <User size={16} />
          <span>{currentUser?.is_guest ? 'Guest Profile' : currentUser?.username || 'User Profile'}</span>
        </button>
      </div>
    </aside>
  );
}
