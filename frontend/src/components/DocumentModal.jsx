import React, { useState, useEffect, useRef } from 'react';
import { X, FileText, Upload, Trash2, CheckCircle2, Layers } from 'lucide-react';
import { apiDocuments } from '../api/client';

export default function DocumentModal({ isOpen, onClose }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const docs = await apiDocuments.list();
      setDocuments(docs);
    } catch (e) {
      console.error('Failed to load documents:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadDocuments();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      await apiDocuments.upload(file);
      await loadDocuments();
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this document and its vector embeddings?')) return;
    try {
      await apiDocuments.delete(id);
      loadDocuments();
    } catch (err) {
      console.error(err);
    }
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={20} style={{ color: 'var(--accent-primary)' }} />
            <h2 className="modal-title">Document Assistant (RAG)</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <p className="form-help" style={{ marginBottom: '16px' }}>
          Upload PDF, DOCX, TXT, CSV, or Markdown files. Content is indexed into local vector embeddings using Ollama (<code style={{ color: '#10b981' }}>all-minilm</code>) for instant question-answering with citations.
        </p>

        {/* Upload Button */}
        <div style={{ marginBottom: '20px' }}>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileUpload}
            accept=".pdf,.docx,.txt,.md,.csv,.json"
          />
          <button
            className="new-chat-btn"
            style={{ width: '100%', margin: 0, justifyContent: 'center' }}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            <Upload size={16} />
            <span>{uploading ? 'Parsing & Embedding Document...' : 'Upload Document'}</span>
          </button>
        </div>

        {/* Document List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '350px', overflowY: 'auto' }}>
          {loading ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>Loading documents...</div>
          ) : documents.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
              No documents uploaded yet. Upload a file to test RAG!
            </div>
          ) : (
            documents.map((d) => (
              <div
                key={d.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 14px',
                  background: 'var(--bg-main)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, overflow: 'hidden' }}>
                  <FileText size={18} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 600, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      {d.filename}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', gap: '10px' }}>
                      <span>{formatSize(d.file_size)}</span>
                      <span>•</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                        <Layers size={11} /> {d.chunk_count} vector chunks
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(d.id)}
                  className="icon-btn-xs danger"
                  title="Delete document"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
