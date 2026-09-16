import React from 'react';
import { Bot, Code2, Calculator, FileText, Globe, Languages } from 'lucide-react';

export default function WelcomeScreen({ onSelectPrompt }) {
  const cards = [
    {
      icon: <Code2 size={18} style={{ color: '#38bdf8' }} />,
      title: 'Programming Assistant',
      desc: 'Code generation, debugging, refactoring, and SQL across all major languages.',
      prompt: 'Write a Python FastAPI service with an endpoint that validates and aggregates JSON data.',
    },
    {
      icon: <Calculator size={18} style={{ color: '#10b981' }} />,
      title: 'Accurate Math Calculator',
      desc: 'Offloads complex math to the safe backend AST calculator.',
      prompt: 'Calculate sqrt(1764) + 25 * 4 - 36 / 6',
    },
    {
      icon: <FileText size={18} style={{ color: '#f59e0b' }} />,
      title: 'Document Assistant (RAG)',
      desc: 'Upload PDF, DOCX, TXT, or CSV and query with verified page citations.',
      prompt: 'Summarize the key points and findings from my uploaded document.',
    },
    {
      icon: <Globe size={18} style={{ color: '#06b6d4' }} />,
      title: 'Web Search & Citations',
      desc: 'Search the internet and browse webpages with transparent source links.',
      prompt: 'What are the newest features and architectural changes in Python 3.14?',
    },
    {
      icon: <Languages size={18} style={{ color: '#8b5cf6' }} />,
      title: 'Multilingual Explanations',
      desc: 'Explains concepts in English, Hindi, Manipuri, or Spanish while keeping code intact.',
      prompt: 'Explain how neural networks learn, and provide an example in Python.',
    },
  ];

  return (
    <div className="welcome-screen">
      <div className="welcome-logo">
        <Bot size={34} />
      </div>
      <h1 className="welcome-title">MUKKU.AI</h1>
      <p className="welcome-subtitle">
        Local AI assistant powered by Ollama + Qwen2.5 3B Instruct.
      </p>

      <div className="prompt-grid">
        {cards.map((c, i) => (
          <div key={i} className="prompt-card" onClick={() => onSelectPrompt(c.prompt)}>
            <div className="prompt-card-header">
              {c.icon}
              <span>{c.title}</span>
            </div>
            <div className="prompt-card-desc">{c.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
