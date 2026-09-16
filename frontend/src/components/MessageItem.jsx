import React, { useState } from 'react';
import { Bot, User, Copy, Check, RotateCw, Volume2, VolumeX, Edit3, Trash2, Cpu } from 'lucide-react';
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
  const [editContent, setEditContent] = useState(message.content);

  const isUser = message.role === 'user';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
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
        {/* Tool Execution Card (if tool was run for this response) */}
        {!isUser && toolMetadata && (
          <div className="tool-pill-card">
            <Cpu size={13} />
            <span>Used {toolMetadata.tool} {toolMetadata.status ? `(${toolMetadata.status})` : ''}</span>
          </div>
        )}

        <div className="message-bubble">
          {isEditing ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '300px' }}>
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
              <MarkdownRenderer content={message.content} />
              {citations && <Citations citations={citations} />}
            </>
          )}
        </div>

        {/* Action Buttons */}
        <div className="message-actions">
          <button className="msg-action-btn" onClick={handleCopy} title="Copy text">
            {copied ? <Check size={13} style={{ color: '#10b981' }} /> : <Copy size={13} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          {!isUser && onSpeak && (
            <button
              className="msg-action-btn"
              onClick={() => onSpeak(message.content)}
              title={isSpeaking ? 'Stop speaking' : 'Read aloud'}
            >
              {isSpeaking ? <VolumeX size={13} style={{ color: '#f43f5e' }} /> : <Volume2 size={13} />}
              <span>{isSpeaking ? 'Stop' : 'Read'}</span>
            </button>
          )}

          {!isUser && isLastAssistant && !streaming && onRegenerate && (
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
