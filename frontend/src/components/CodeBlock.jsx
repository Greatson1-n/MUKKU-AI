import React, { useState, useEffect, useRef } from 'react';
import { Copy, Check } from 'lucide-react';
import Prism from 'prismjs';
// Common language syntaxes
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-c';
import 'prismjs/components/prism-cpp';
import 'prismjs/components/prism-java';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-markup';

export default function CodeBlock({ language = 'text', code = '' }) {
  const [copied, setCopied] = useState(false);
  const codeRef = useRef(null);

  const cleanLang = (language || 'text').toLowerCase().replace('language-', '');

  useEffect(() => {
    if (codeRef.current) {
      Prism.highlightElement(codeRef.current);
    }
  }, [code, cleanLang]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy code:', e);
    }
  };

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span>{cleanLang.toUpperCase()}</span>
        <button className="code-copy-btn" onClick={handleCopy} title="Copy code">
          {copied ? (
            <>
              <Check size={13} style={{ color: '#10b981' }} />
              <span style={{ color: '#10b981' }}>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={13} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="code-block-pre">
        <code ref={codeRef} className={`language-${cleanLang}`}>
          {code}
        </code>
      </pre>
    </div>
  );
}
