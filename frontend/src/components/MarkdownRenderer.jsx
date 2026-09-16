import React from 'react';
import { marked } from 'marked';
import CodeBlock from './CodeBlock';

marked.setOptions({
  breaks: true,
  gfm: true,
});

export default function MarkdownRenderer({ content = '' }) {
  if (!content) return null;

  // Split content by code blocks: ```lang ... ```
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const elements = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    const textBefore = content.substring(lastIndex, match.index);
    if (textBefore.trim()) {
      elements.push(
        <div
          key={`md-${lastIndex}`}
          dangerouslySetInnerHTML={{ __html: marked.parse(textBefore) }}
        />
      );
    }

    const language = match[1] || 'text';
    const code = match[2].trimEnd();
    elements.push(
      <CodeBlock key={`code-${match.index}`} language={language} code={code} />
    );

    lastIndex = match.index + match[0].length;
  }

  const remainingText = content.substring(lastIndex);
  if (remainingText.trim()) {
    elements.push(
      <div
        key={`md-${lastIndex}`}
        dangerouslySetInnerHTML={{ __html: marked.parse(remainingText) }}
      />
    );
  }

  return <div className="markdown-content">{elements}</div>;
}
