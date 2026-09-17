import React, { useState } from 'react';
import { Bot, User, Copy, Check, RotateCw, Volume2, VolumeX, Edit3, Trash2, Cpu, AlertTriangle, AlertCircle, CloudOff } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';
import Citations from './Citations';

export default function MessageItem({
  message,
  onRegenerate,
  onEdit,
  onDelete,
  onSpeak,
  isSpeaking,
  isLastAssistant,
  streaming,
}) {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content || '');

  const isUser = message.role === 'user';
  const isInterrupted = !isUser && (message.status === 'cancelled' || message.status === 'interrupted' || (message.status === 'streaming' && !streaming));
  const isError = !isUser && message.status === 'error';
  const isOffline = message.sync_status === 'pending_sync';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy message:', e);
    }
  };

  const handleSaveEdit = () => {
    if (editContent.trim() && editContent !== message.content) {
      onEdit(message.id, editContent.trim());
    }
    setIsEditing(false);
  };

  let toolMetadata = null;
  if (message.tool_calls) {
    try {
      toolMetadata = typeof message.tool_calls === 'string' ? JSON.parse(message.tool_calls) : message.tool_calls;
    } catch {}
  }

  let citations = null;
  if (message.citations) {
    try {
      citations = typeof message.citations === 'string' ? JSON.parse(message.citations) : message.citations;
    } catch {}
  }

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      <div className={`message-avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? <User size={18} /> : <Bot size={19} />}
      </div>

      <div className="message-body">
        {/* Offline Queued Status */}
        {isOffline && (
          <div className="status-pill syncing">
            <CloudOff size={11} />
            <span>Saved offline (queued for sync)</span>
          </div>
        )}

        {/* Tool Execution Card (if tool was run for this response) */}
        {!isUser && toolMetadata && (
          <div className="tool-pill-card">
            <Cpu size={13} />
            <span>Used {toolMetadata.tool} {toolMetadata.status ? `(${toolMetadata.status})` : ''}</span>
          </div>
        )}

        <div className="message-bubble">
          {isEditing ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', minWidth: 0, boxSizing: 'border-box' }}>
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="form-textarea"
                rows={3}
                autoFocus
              />
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                <button className="btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => setIsEditing(false)}>
                  Cancel
                </button>
                <button className="btn-primary" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={handleSaveEdit}>
                  Save & Resend
                </button>
              </div>
            </div>
          ) : isUser ? (
            <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
          ) : (
            <>
              {message.content ? (
                <MarkdownRenderer content={message.content} />
              ) : (
                <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No response content</span>
              )}
              {citations && <Citations citations={citations} />}
            </>
          )}

          {/* Interrupted Crash Alert Box */}
          {isInterrupted && (
            <div className="interrupted-alert-box">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertTriangle size={14} />
                <span>Generation was interrupted.</span>
              </div>
              {onRegenerate && (
                <button onClick={() => onRegenerate(message.id)}>
                  <RotateCw size={11} />
                  <span>Regenerate</span>
                </button>
              )}
            </div>
          )}

          {/* Error Alert Box */}
          {isError && (
            <div className="status-pill error" style={{ marginTop: '8px', display: 'flex' }}>
              <AlertCircle size={12} />
              <span>Response encountered an error</span>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="message-actions">
          {message.content && (
            <button className="msg-action-btn" onClick={handleCopy} title="Copy text">
              {copied ? <Check size={13} style={{ color: '#10b981' }} /> : <Copy size={13} />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          )}

          {!isUser && onSpeak && message.content && (
            <button
              className="msg-action-btn"
              onClick={() => onSpeak(message.content)}
              title={isSpeaking ? 'Stop speaking' : 'Read aloud'}
            >
              {isSpeaking ? <VolumeX size={13} style={{ color: '#f43f5e' }} /> : <Volume2 size={13} />}
              <span>{isSpeaking ? 'Stop' : 'Read'}</span>
            </button>
          )}

          {!isUser && (isLastAssistant || isInterrupted) && !streaming && onRegenerate && (
            <button className="msg-action-btn" onClick={() => onRegenerate(message.id)} title="Regenerate response">
              <RotateCw size={13} />
              <span>Regenerate</span>
            </button>
          )}

          {isUser && onEdit && !streaming && (
            <button className="msg-action-btn" onClick={() => setIsEditing(true)} title="Edit message">
              <Edit3 size={13} />
              <span>Edit</span>
            </button>
          )}

          {onDelete && !streaming && (
            <button className="msg-action-btn" onClick={() => onDelete(message.id)} title="Delete message">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
