import React, { useState } from 'react';
import { X, User, LogIn, UserPlus } from 'lucide-react';
import { apiAuth, setAuthToken } from '../api/client';

export default function AuthModal({ isOpen, onClose, currentUser, onAuthSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const fn = isRegister ? apiAuth.register : apiAuth.login;
      const res = await fn({ username, password });
      setAuthToken(res.access_token);
      onAuthSuccess(res.user);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setAuthToken(null);
    window.location.reload();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={20} style={{ color: 'var(--accent-primary)' }} />
            <h2 className="modal-title">{isRegister ? 'Create Account' : 'User Account'}</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Current status */}
        <div style={{ padding: '10px 14px', background: 'var(--bg-main)', borderRadius: 'var(--radius-sm)', marginBottom: '18px', fontSize: '0.88rem' }}>
          <div>Current session: <strong>{currentUser?.is_guest ? 'Local Guest Mode' : currentUser?.username}</strong></div>
          <p className="form-help">
            {currentUser?.is_guest
              ? 'You are currently using local guest mode. All conversations and memories are stored locally.'
              : 'You are signed into your personal workspace.'}
          </p>
        </div>

        {error && (
          <div style={{ padding: '8px 12px', background: 'rgba(244, 63, 94, 0.15)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: 'var(--radius-sm)', color: '#fb7185', fontSize: '0.82rem', marginBottom: '14px' }}>
            {error}
          </div>
        )}

        {/* Switch tabs */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '18px' }}>
          <button
            type="button"
            className={`toggle-chip ${!isRegister ? 'active' : ''}`}
            onClick={() => setIsRegister(false)}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            <LogIn size={14} /> Sign In
          </button>
          <button
            type="button"
            className={`toggle-chip ${isRegister ? 'active' : ''}`}
            onClick={() => setIsRegister(true)}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            <UserPlus size={14} /> Register
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Username</label>
            <input
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '6px' }} disabled={loading}>
            {loading ? 'Processing...' : isRegister ? 'Register & Login' : 'Sign In'}
          </button>
        </form>

        {!currentUser?.is_guest && (
          <button
            type="button"
            className="btn-secondary"
            style={{ width: '100%', marginTop: '12px', color: 'var(--accent-rose)' }}
            onClick={handleLogout}
          >
            Log Out
          </button>
        )}
      </div>
    </div>
  );
}
