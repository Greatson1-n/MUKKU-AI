import React, { useState, useEffect } from 'react';
import { X, Sliders, Check } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose, settings, onSave, ollamaStatus }) {
  const [model, setModel] = useState(settings?.ollama_model || 'qwen2.5:3b');
  const [temperature, setTemperature] = useState(settings?.temperature ?? 0.7);
  const [responseStyle, setResponseStyle] = useState(settings?.response_style || 'balanced');
  const [systemPrompt, setSystemPrompt] = useState(settings?.system_prompt || '');
  const [language, setLanguage] = useState(settings?.language || 'en');
  const [theme, setTheme] = useState(settings?.theme || 'dark');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setModel(settings.ollama_model || 'qwen2.5:3b');
      setTemperature(settings.temperature ?? 0.7);
      setResponseStyle(settings.response_style || 'balanced');
      setSystemPrompt(settings.system_prompt || '');
      setLanguage(settings.language || 'en');
      setTheme(settings.theme || 'dark');
    }
  }, [settings]);

  if (!isOpen) return null;

  const handleStyleChange = (style) => {
    setResponseStyle(style);
    if (style === 'precise') {
      setTemperature(0.2);
    } else if (style === 'balanced') {
      setTemperature(0.7);
    } else if (style === 'creative') {
      setTemperature(1.0);
    } else if (style === 'code') {
      setTemperature(0.1);
    } else if (style === 'concise') {
      setTemperature(0.3);
    }
  };

  const handleSave = () => {
    onSave({
      ollama_model: model,
      temperature,
      response_style: responseStyle,
      system_prompt: systemPrompt,
      language,
      theme,
    });
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sliders size={20} style={{ color: 'var(--accent-primary)' }} />
            <h2 className="modal-title">Settings & Parameters</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Model Selection */}
        <div className="form-group">
          <label className="form-label">Ollama Model</label>
          <select className="form-select" value={model} onChange={(e) => setModel(e.target.value)}>
            {ollamaStatus?.available_models?.length ? (
              ollamaStatus.available_models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))
            ) : (
              <option value="qwen2.5:3b">qwen2.5:3b (default)</option>
            )}
          </select>
          <p className="form-help">Primary reasoning model running locally through Ollama.</p>
        </div>

        {/* Response Style Presets */}
        <div className="form-group">
          <label className="form-label">Response Style Preset</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {[
              { id: 'balanced', label: 'Balanced' },
              { id: 'precise', label: 'Precise (Fact/Math)' },
              { id: 'creative', label: 'Creative' },
              { id: 'code', label: 'Code Specialist' },
              { id: 'concise', label: 'Concise' },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                className={`toggle-chip ${responseStyle === p.id ? 'active' : ''}`}
                onClick={() => handleStyleChange(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Temperature Slider */}
        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Temperature: {temperature}
            </label>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {temperature < 0.4 ? 'Focused & Deterministic' : temperature > 0.8 ? 'Creative & Exploratory' : 'Balanced'}
            </span>
          </div>
          <input
            type="range"
            min="0.0"
            max="1.5"
            step="0.05"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
          />
        </div>

        {/* Multilingual Selector */}
        <div className="form-group">
          <label className="form-label">Response Language</label>
          <select className="form-select" value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English (Default)</option>
            <option value="hi">Hindi (हिंदी)</option>
            <option value="mni">Manipuri / Meiteilon (মৈতৈলোন্ / ꯃꯩꯇꯩꯂꯣꯟ)</option>
            <option value="es">Spanish (Español)</option>
            <option value="fr">French (Français)</option>
            <option value="de">German (Deutsch)</option>
            <option value="bn">Bengali (বাংলা)</option>
          </select>
          <p className="form-help">Model responds in selected language while keeping programming code untouched.</p>
        </div>

        {/* System Prompt Editor */}
        <div className="form-group">
          <label className="form-label">System Instructions</label>
          <textarea
            className="form-textarea"
            rows={5}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Custom instructions for Qwen2.5 3B..."
          />
        </div>

        {/* Theme Toggle */}
        <div className="form-group">
          <label className="form-label">Theme</label>
          <select className="form-select" value={theme} onChange={(e) => setTheme(e.target.value)}>
            <option value="dark">Obsidian Dark (Recommended)</option>
            <option value="light">Light Mode</option>
          </select>
        </div>

        {/* Modal Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSave} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {saved ? <Check size={16} /> : null}
            <span>{saved ? 'Saved!' : 'Save Settings'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
