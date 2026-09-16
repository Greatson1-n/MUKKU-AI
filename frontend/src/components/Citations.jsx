import React from 'react';
import { ExternalLink, BookOpen } from 'lucide-react';

export default function Citations({ citations }) {
  if (!citations || !citations.length) return null;

  return (
    <div className="citations-wrapper">
      {citations.map((c, idx) => (
        <a
          key={idx}
          href={c.url || '#'}
          target={c.url ? '_blank' : '_self'}
          rel="noopener noreferrer"
          className="citation-pill"
          title={c.snippet || c.document_name}
        >
          {c.url ? <ExternalLink size={12} /> : <BookOpen size={12} />}
          <span>
            {c.document_name}
            {c.page_number ? ` — Page ${c.page_number}` : ''}
          </span>
        </a>
      ))}
    </div>
  );
}
