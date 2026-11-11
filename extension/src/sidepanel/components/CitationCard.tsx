import React, { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { Citation } from '../types';

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation, index }) => {
  const [expanded, setExpanded] = useState(false);

  const handleOpenSource = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (citation.source_url) {
      if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
        chrome.tabs.create({ url: citation.source_url });
      } else {
        window.open(citation.source_url, '_blank', 'noopener,noreferrer');
      }
    }
  };

  const domain = (() => {
    try {
      return new URL(citation.source_url).hostname;
    } catch {
      return citation.source_url;
    }
  })();

  return (
    <div className="text-xs bg-canvas-subtle border border-edge rounded-control overflow-hidden transition-colors hover:border-edge-strong">
      <div
        onClick={() => setExpanded(!expanded)}
        className="p-2 flex items-start justify-between cursor-pointer select-none hover:bg-canvas-elevated"
      >
        <div className="flex items-start space-x-2 flex-1 min-w-0 pr-1.5">
          <span className="flex-shrink-0 px-1 py-0.5 rounded-control bg-teal-subtle text-teal font-mono text-2xs font-medium">
            [{index + 1}]
          </span>
          <div className="min-w-0 flex-1">
            <h4 className="font-medium text-xs text-content-primary truncate leading-tight">
              {citation.page_title || 'Untitled Reference'}
            </h4>
            <div className="flex items-center space-x-1.5 text-2xs text-content-muted mt-0.5 font-mono">
              <span className="truncate max-w-[140px] text-content-secondary">{domain}</span>
              <span>•</span>
              <span>chk {citation.chunk_index}</span>
              {typeof citation.relevance_score === 'number' && (
                <>
                  <span>•</span>
                  <span className="text-teal font-medium">
                    {(citation.relevance_score * 100).toFixed(0)}%
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-0.5 flex-shrink-0">
          <button
            type="button"
            onClick={handleOpenSource}
            title="Open original source"
            className="p-1 rounded-control text-content-muted hover:text-teal hover:bg-canvas transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
          </button>
          <button
            type="button"
            title={expanded ? 'Collapse excerpt' : 'Expand excerpt'}
            className="p-1 rounded-control text-content-muted hover:text-content-primary transition-colors"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-2.5 py-2 border-t border-edge bg-canvas text-content-secondary">
          <p className="text-2xs leading-relaxed italic border-l-2 border-teal pl-2 font-sans whitespace-pre-wrap">
            "{citation.content_excerpt}"
          </p>
          <div className="mt-1.5 flex justify-end">
            <button
              type="button"
              onClick={handleOpenSource}
              className="text-2xs font-mono text-teal hover:underline inline-flex items-center space-x-1"
            >
              <span>source reference</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
