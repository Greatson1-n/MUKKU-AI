import React, { useRef, useEffect } from 'react';
import { ArrowUp, Square, Mic, MicOff, Paperclip, Globe, Brain, X, Image as ImageIcon } from 'lucide-react';

export default function InputArea({
  input,
  setInput,
  onSend,
  onStop,
  streaming,
  webSearch,
  setWebSearch,
  memoryEnabled,
  setMemoryEnabled,
  selectedFile,
  setSelectedFile,
  imageBase64,
  setImageBase64,
  isListening,
  startListening,
  stopListening,
  recognitionSupported,
}) {
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!streaming && (input.trim() || selectedFile || imageBase64)) {
        onSend();
      }
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = () => {
        setImageBase64(reader.result);
        setSelectedFile({ name: file.name, type: 'image' });
      };
      reader.readAsDataURL(file);
    } else {
      setSelectedFile({ file, name: file.name, type: 'doc' });
    }
    e.target.value = '';
  };

  const clearAttachment = () => {
    setSelectedFile(null);
    setImageBase64(null);
  };

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening((transcript) => {
        setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
      });
    }
  };

  const handleFocus = () => {
    // When virtual keyboard opens on Android/mobile, ensure input stays in view
    setTimeout(() => {
      textareaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 300);
  };

  return (
    <div className="input-area-container">
      <div className="input-box-wrapper">
        {/* Attachment preview banner */}
        {(selectedFile || imageBase64) && (
          <div className="attachment-preview-bar">
            {selectedFile?.type === 'image' ? <ImageIcon size={14} /> : <Paperclip size={14} />}
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {selectedFile?.name}
            </span>
            <button
              onClick={clearAttachment}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder="Ask Qwen2.5 3B anything, calculate math, search web, query docs..."
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          disabled={streaming}
        />

        {/* Actions Bar */}
        <div className="input-actions-bar">
          {/* Quick Capability Toggles */}
          <div className="input-toggles">
            <button
              type="button"
              className={`toggle-chip ${webSearch ? 'active' : ''}`}
              onClick={() => setWebSearch(!webSearch)}
              title="Toggle Live Web Search"
            >
              <Globe size={13} />
              <span>Web Search</span>
            </button>

            <button
              type="button"
              className={`toggle-chip ${memoryEnabled ? 'active' : ''}`}
              onClick={() => setMemoryEnabled(!memoryEnabled)}
              title="Toggle Long-term Memory"
            >
              <Brain size={13} />
              <span>Memory</span>
            </button>
          </div>

          {/* Action buttons */}
          <div className="input-buttons">
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              onChange={handleFileChange}
              accept=".pdf,.docx,.txt,.md,.csv,.json,image/*"
            />

            <button
              type="button"
              className="circle-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Attach File or Image"
              disabled={streaming}
            >
              <Paperclip size={17} />
            </button>

            {recognitionSupported && (
              <button
                type="button"
                className={`circle-btn ${isListening ? 'mic-active' : ''}`}
                onClick={handleMicToggle}
                title={isListening ? 'Stop Voice Input' : 'Voice Input (Speech-to-Text)'}
              >
                {isListening ? <MicOff size={17} /> : <Mic size={17} />}
              </button>
            )}

            {streaming ? (
              <button type="button" className="stop-btn" onClick={onStop} title="Stop generation">
                <Square size={16} />
              </button>
            ) : (
              <button
                type="button"
                className="send-btn"
                onClick={onSend}
                disabled={!input.trim() && !selectedFile && !imageBase64}
                title="Send message"
              >
                <ArrowUp size={18} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
