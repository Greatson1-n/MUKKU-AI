import React, { useState, useEffect } from 'react';
import { X, Brain, Plus, Trash2, CheckCircle2, Circle } from 'lucide-react';
import { apiMemory } from '../api/client';

export default function MemoryModal({ isOpen, onClose }) {
  const [memories, setMemories] = useState([]);
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('preference');
  const [loading, setLoading] = useState(false);

  const loadMemories = async () => {
    try {
      setLoading(true);
      const data = await apiMemory.list(false);
      setMemories(data);
    } catch (e) {
      console.error('Failed to load memories:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadMemories();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    try {
      await apiMemory.create({ content: newContent.trim(), category: newCategory });
      setNewContent('');
      loadMemories();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleToggle = async (mem) => {
    try {
      await apiMemory.update(mem.id, { is_active: !mem.is_active });
      loadMemories();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiMemory.delete(id);
      loadMemories();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Brain size={20} style={{ color: 'var(--accent-primary)' }} />
            <h2 className="modal-title">Long-term Memory</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <p className="form-help" style={{ marginBottom: '16px' }}>
          MUKKU.AI automatically extracts and stores user preferences and facts so Qwen2.5 3B remembers them across conversations.
        </p>

        {/* Add Memory Form */}
        <form onSubmit={handleAdd} style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. 'I prefer Python for backend and React for UI'"
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
          />
          <select
            className="form-select"
            style={{ width: '130px' }}
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
          >
            <option value="preference">Preference</option>
            <option value="project">Project</option>
            <option value="fact">Fact</option>
          </select>
          <button type="submit" className="btn-primary" style={{ padding: '0 14px' }}>
            <Plus size={16} />
          </button>
        </form>

        {/* Memories List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '350px', overflowY: 'auto' }}>
          {loading ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>Loading memories...</div>
          ) : memories.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
              No memories recorded yet. Start chatting or add one above!
            </div>
          ) : (
            memories.map((m) => (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  background: 'var(--bg-main)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  opacity: m.is_active ? 1 : 0.5,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
                  <button
                    onClick={() => handleToggle(m)}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: m.is_active ? '#10b981' : 'var(--text-dim)' }}
                    title={m.is_active ? 'Active' : 'Disabled'}
                  >
                    {m.is_active ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </button>
                  <span style={{ fontSize: '0.88rem' }}>{m.content}</span>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      color: 'var(--text-dim)',
                      textTransform: 'uppercase',
                    }}
                  >
                    {m.category}
                  </span>
                </div>
                <button
                  onClick={() => handleDelete(m.id)}
                  className="icon-btn-xs danger"
                  title="Delete memory"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
