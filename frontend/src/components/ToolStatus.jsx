import React from 'react';
import { Calculator, Globe, FileText, Clock, Eye, Cpu } from 'lucide-react';

export default function ToolStatus({ tool, status }) {
  if (!tool && !status) return null;

  const getIcon = () => {
    switch (tool) {
      case 'calculator':
        return <Calculator size={14} />;
      case 'web_search':
        return <Globe size={14} />;
      case 'document_search':
        return <FileText size={14} />;
      case 'current_time':
        return <Clock size={14} />;
      case 'vision':
        return <Eye size={14} />;
      default:
        return <Cpu size={14} />;
    }
  };

  return (
    <div className="tool-banner">
      {getIcon()}
      <span>{status || `Executing ${tool}...`}</span>
    </div>
  );
}
